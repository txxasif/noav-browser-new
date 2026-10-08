"""instagram/ig_page_api.py — Instagram web API calls made FROM INSIDE the live
browser tab (``page.evaluate(fetch(...))``).

Why: the same calls from Python ``requests`` get Instagram's HTML shell
(HTTP 200, ``<link data-default-icon=…``) because the TLS fingerprint and web
headers are not a browser's. Run inside the tab they carry the real Chromium
fingerprint, the real cookies and the real session — they are indistinguishable
from the site's own XHRs.

Every function takes the Playwright ``page`` (already on instagram.com) and
returns plain values; none raises except :class:`PageApiDead`, which means the
session itself is dead/challenged (login_required / checkpoint / challenge).
"""
from __future__ import annotations

import base64
import io
import json
import random
import time

IG_WEB_APP_ID = "1217981644879628"   # the app id Instagram's own page sends (seen in the follow trace)

_DEAD = ("login_required", "checkpoint_required", "challenge_required", "user_has_logged_out")


class PageApiDead(Exception):
    """Instagram says the session is logged out / challenged."""


_JS_FETCH = """async (a) => {
  const csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  let claim = '0';
  try { claim = sessionStorage.getItem('www-claim-v2') || '0'; } catch (e) {}
  const h = Object.assign({
    'X-CSRFToken': csrf, 'X-IG-App-ID': a.appId, 'X-ASBD-ID': '359341',
    'X-IG-WWW-Claim': claim, 'X-Instagram-AJAX': '1',
    'X-Requested-With': 'XMLHttpRequest', 'Accept': '*/*'
  }, a.headers || {});
  let body;
  if (a.b64) {
    const bin = atob(a.b64); const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    if (a.formField) {
      const fd = new FormData();
      fd.append(a.formField, new Blob([u], {type: a.mime || 'image/jpeg'}), a.fileName || 'file.jpg');
      body = fd;
    } else { body = u; }
  } else if (a.form) {
    body = new URLSearchParams(a.form).toString();
    h['Content-Type'] = 'application/x-www-form-urlencoded';
  }
  try {
    const r = await fetch(a.url, {method: a.method || 'POST', headers: h, body: body,
                                  credentials: 'include'});
    const t = await r.text();
    return {status: r.status, text: t.slice(0, 4000)};
  } catch (e) { return {status: 0, text: 'fetch error: ' + e}; }
}"""


def _call(page, url: str, *, method="POST", form=None, headers=None, b64=None,
          form_field=None, mime=None, file_name=None) -> tuple:
    """-> (ok, json_or_{}, detail). Raises PageApiDead on a dead session."""
    res = page.evaluate(_JS_FETCH, {
        "url": url, "method": method, "form": form, "headers": headers or {},
        "b64": b64, "formField": form_field, "mime": mime, "fileName": file_name,
        "appId": IG_WEB_APP_ID})
    status, text = int(res.get("status") or 0), str(res.get("text") or "")
    if text.lstrip().startswith("<"):
        return False, {}, f"HTML shell (HTTP {status}) — request not accepted as a web XHR"
    try:
        js = json.loads(text)
    except Exception:
        return False, {}, f"HTTP {status} non-JSON: {text[:80]}"
    low = (str(js.get("message", "")) + str(js.get("error_type", ""))).lower()
    if any(k in low for k in _DEAD):
        raise PageApiDead(low.strip() or "session dead")
    if status == 200 and js.get("status") != "fail":
        return True, js, "ok"
    return False, js, str(js.get("message") or f"HTTP {status}")[:120]


def pk_of(page, username: str, log=None) -> str:
    """username -> user id. The target list is fixed, so the saved id cache
    (data/ig_follow_pks.json, shared with ig_api) is used first — the live
    lookup (web_profile_info) is rate-limited and fails for brand-new accounts."""
    u = username.lstrip("@")
    try:
        from instagram.ig_api import _load_pk_cache, _save_pk_cache
        cache = _load_pk_cache()
        if cache.get(u):
            return str(cache[u])
    except Exception:
        cache = None
    ok, js, why = _call(page, "/api/v1/users/web_profile_info/?username=" + u, method="GET")
    pk = ""
    try:
        pk = str(js["data"]["user"]["id"]) if ok else ""
    except Exception:
        pk = ""
    if pk and cache is not None:
        cache[u] = pk
        try:
            _save_pk_cache()
        except Exception:
            pass
    elif not pk and log:
        log(f"[👥][page-api] lookup {u} failed: {why}")
    return pk


def follow(page, pk: str) -> tuple:
    ok, js, why = _call(page, f"/api/v1/friendships/create/{pk}/", form={
        "container_module": "profile", "user_id": pk})
    if ok and (js.get("friendship_status") or {}).get("following") is False \
            and not (js.get("friendship_status") or {}).get("outgoing_request"):
        return False, "not persisted"
    return ok, why


def follow_targets(page, usernames, need: int, log, *, delay=(6.0, 14.0)) -> int:
    """Follow up to ``need`` of ``usernames``; returns how many persisted.
    Raises PageApiDead on a dead session. A soft failure on one target moves on
    to the next (up to two misses in a row, then it stops)."""
    done = misses = 0
    for u in usernames:
        if done >= need or misses >= 2:
            break
        pk = pk_of(page, u, log)
        if not pk:
            log(f"[👥][page-api] {u}: not resolvable — skipping.")
            misses += 1
            continue
        time.sleep(random.uniform(1.5, 3.5))          # "look at the profile" beat
        ok, why = follow(page, pk)
        if ok:
            done += 1
            misses = 0
            log(f"[👥][page-api] Followed @{u} ({done}/{need}).")
            time.sleep(random.uniform(*delay))
        else:
            misses += 1
            log(f"[👥][page-api] @{u} follow failed: {why}")
    return done


def _jpeg(path: str) -> tuple:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue(), im.width, im.height


def set_bio(page, text: str) -> tuple:
    """Bio via the web edit form (read current fields, change biography)."""
    ok, js, why = _call(page, "/api/v1/accounts/edit/web_form_data/", method="GET")
    if ok:
        fd = js.get("form_data") or {}
        form = {k: ("" if v is None else str(v)) for k, v in {
            "first_name": fd.get("first_name"), "email": fd.get("email"),
            "username": fd.get("username"), "phone_number": fd.get("phone_number"),
            "biography": text, "external_url": fd.get("external_url"),
            "chaining_enabled": "on" if fd.get("chaining_enabled") else "",
        }.items()}
        ok, _js, why = _call(page, "/api/v1/web/accounts/edit/", form=form)
        if ok:
            return True, "ok (web edit)"
    ok2, _js, why2 = _call(page, "/api/v1/accounts/set_biography/", form={"raw_text": text})
    return ok2, ("ok (set_biography)" if ok2 else f"{why}; {why2}")


def set_avatar(page, path: str) -> tuple:
    data, _w, _h = _jpeg(path)
    ok, _js, why = _call(page, "/api/v1/web/accounts/web_change_profile_picture/",
                         b64=base64.b64encode(data).decode(), form_field="profile_pic",
                         mime="image/jpeg", file_name="profile_pic.jpg")
    return ok, why


def post_photo(page, path: str, caption: str = "") -> tuple:
    data, w, h = _jpeg(path)
    upload_id = str(int(time.time() * 1000))
    res = page.evaluate(_JS_FETCH, {
        "url": "/rupload_igphoto/fb_uploader_" + upload_id, "method": "POST",
        "b64": base64.b64encode(data).decode(), "appId": IG_WEB_APP_ID,
        "headers": {
            "X-Entity-Type": "image/jpeg", "X-Entity-Name": "fb_uploader_" + upload_id,
            "X-Entity-Length": str(len(data)), "Offset": "0",
            "X-Instagram-Rupload-Params": json.dumps({
                "media_type": 1, "upload_id": upload_id,
                "upload_media_height": h, "upload_media_width": w}),
            "Content-Type": "image/jpeg"}})
    if int(res.get("status") or 0) != 200:
        return False, f"upload HTTP {res.get('status')}: {str(res.get('text'))[:80]}"
    time.sleep(random.uniform(2.0, 4.0))
    ok, _js, why = _call(page, "/api/v1/media/configure/", form={
        "upload_id": upload_id, "caption": caption or "", "usertags": "",
        "custom_accessibility_caption": "", "retry_timeout": ""})
    return ok, why
