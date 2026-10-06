"""Meta Creator — Instagram account checker (ported from Nova Browser).

Stdlib-only: checks whether Instagram usernames are alive via the public
web_profile_info REST endpoint with an HTML fallback. No login, no cookies,
no browser. Used by the "IG Checker" dashboard page and by the IG Creator
Backup modal to flag damaged accounts.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.request
from urllib.parse import quote

IG_APP_ID = "936619743392459"
REST_TIMEOUT = 10.0
HTML_TIMEOUT = 12.0
REST_TO_HTML_DELAY = 0.5

IG_REST_HEADERS = {
    "x-ig-app-id": IG_APP_ID,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.instagram.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}
IG_HTML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def http_get(url: str, headers: dict, timeout: float) -> tuple:
    """Return (status, body_text). Raises on network failure."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener().open(req, timeout=timeout) as res:
        raw = res.read()
        enc = (res.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        charset = res.headers.get_content_charset() or "utf-8"
        return res.status, raw.decode(charset, errors="replace")


def normalize_instagram_username(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def _parse_social_count(val: str) -> int:
    c = (val or "").strip().replace(",", "").lower()
    try:
        if c.endswith("m"):
            return int(float(c[:-1]) * 1_000_000)
        if c.endswith("k"):
            return int(float(c[:-1]) * 1_000)
        if c.endswith("b"):
            return int(float(c[:-1]) * 1_000_000_000)
        return int(c) or 0
    except Exception:
        return 0


def _balanced_json(text: str, start: int):
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        return None
    return None


def _active_result(username, full_name="", bio="", is_private=False,
                   is_verified=False, pic="", followers=None, following=None,
                   posts=None, details=None) -> dict:
    bad = ("44884218_345707102189036" in pic or "default_profile" in pic
           or "anonymous_profile_pic" in pic or "YW5vbnltb3VzX3Byb2ZpbGVfcGlj" in pic)
    has_pic = bool(pic) and not bad
    msg = "Account is active"
    if is_verified and not is_private:
        msg = "Account is active \u2713 Verified"
    elif is_private:
        msg = "Account is active (private)"
    out = {"username": username, "status": "active", "message": msg}
    if full_name:
        out["fullName"] = full_name
    out["isVerified"] = is_verified
    out["isPrivate"] = is_private
    out["hasProfilePic"] = has_pic
    if has_pic:
        out["profilePicUrl"] = pic
    if followers is not None:
        out["followers"] = followers
    if following is not None:
        out["following"] = following
    if posts is not None:
        out["posts"] = posts
    if bio:
        out["bio"] = bio
    if details:
        out["details"] = details
    return out


def _not_found(username, details="This username does not exist on Instagram") -> dict:
    return {"username": username, "status": "not_found",
            "message": "Account not found", "details": details}


def check_via_rest(username: str):
    headers = dict(IG_REST_HEADERS)
    headers["referer"] = f"https://www.instagram.com/{quote(username)}/"
    try:
        status, body = http_get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={quote(username)}",
            headers, REST_TIMEOUT)
    except Exception:
        return None
    if status == 404:
        return _not_found(username)
    if status in (200, 0):
        try:
            data = json.loads(body)
        except Exception:
            return None
        user = ((data.get("data") or {}).get("user")) if isinstance(data, dict) else None
        if not user:
            return _not_found(username, "This account may have been deleted or deactivated")
        edge = lambda k: (user.get(k) or {}).get("count")
        return _active_result(
            username, full_name=user.get("full_name") or "", bio=user.get("biography") or "",
            is_private=bool(user.get("is_private", False)),
            is_verified=bool(user.get("is_verified", False)),
            pic=user.get("profile_pic_url_hd") or user.get("profile_pic_url") or "",
            followers=edge("edge_followed_by"), following=edge("edge_follow"),
            posts=edge("edge_owner_to_timeline_media"))
    return None


def check_via_html(username: str):
    try:
        status, html = http_get(f"https://www.instagram.com/{quote(username)}/",
                                dict(IG_HTML_HEADERS), HTML_TIMEOUT)
    except Exception:
        return None
    if status == 404:
        return _not_found(username)
    if status != 200:
        return None
    for sig in ("Sorry, this page isn't available",
                "The link you followed may be broken",
                '"logging_page_id":"profilePage_0"',
                '"page_name":"PageNotFound"'):
        if sig in html:
            return _not_found(username, "This account does not exist or has been removed")

    user = None
    pos = 0
    while True:
        idx = html.find('"xig_user_by_igid_v2"', pos)
        if idx == -1:
            break
        brace = html.find("{", idx + len('"xig_user_by_igid_v2"'))
        if brace != -1:
            parsed = _balanced_json(html, brace)
            if parsed and (parsed.get("follower_count") is not None
                           or parsed.get("full_name") is not None):
                user = parsed
                break
        pos = idx + 20
    if not user:
        def grp(pat):
            m = re.search(pat, html)
            return m.group(1) if m else None
        user = {
            "follower_count": int(grp(r'"follower_count":\s*(\d+)') or 0) or None,
            "following_count": int(grp(r'"following_count":\s*(\d+)') or 0) or None,
            "is_verified": (grp(r'"is_verified":\s*(true|false)') == "true")
                           if grp(r'"is_verified":\s*(true|false)') else None,
            "is_private": (grp(r'"is_private":\s*(true|false)') == "true")
                          if grp(r'"is_private":\s*(true|false)') else None,
            "full_name": grp(r'"full_name":\s*"([^"]*)"'),
            "biography": grp(r'"biography":\s*"([^"]*)"'),
            "profile_pic_url": grp(r'"profile_pic_url":\s*"([^"]*)"'),
        }
    if user.get("profile_pic_url"):
        user["profile_pic_url"] = user["profile_pic_url"].replace("\\u0025", "%").replace("\\", "")

    followers, following, posts = user.get("follower_count"), user.get("following_count"), None
    full_name, bio = user.get("full_name") or "", user.get("biography") or ""
    pic = user.get("profile_pic_url") or ""
    desc = ""
    m = re.search(
        r"<meta\s+(?:[^>]*property=[\"']og:description[\"'][^>]*content=[\"']([^\"']+)[\"']"
        r"|[^>]*content=[\"']([^\"']+)[\"'][^>]*property=[\"']og:description[\"']"
        r"|[^>]*name=[\"']description[\"'][^>]*content=[\"']([^\"']+)[\"']"
        r"|[^>]*content=[\"']([^\"']+)[\"'][^>]*name=[\"']description[\"'])",
        html, re.IGNORECASE)
    if m:
        desc = next((g for g in m.groups() if g), "") or ""
    if desc:
        if followers is None:
            fm = re.search(r"([\d.,KMBm]+)\s*Followers", desc, re.IGNORECASE)
            if fm:
                followers = _parse_social_count(fm.group(1))
        if following is None:
            fm = re.search(r"([\d.,KMBm]+)\s*Following", desc, re.IGNORECASE)
            if fm:
                following = _parse_social_count(fm.group(1))
        pm = re.search(r"([\d.,KMBm]+)\s*Posts", desc, re.IGNORECASE)
        if pm:
            posts = _parse_social_count(pm.group(1))

    is_private = user.get("is_private") or False
    is_verified = user.get("is_verified") or False
    if followers is None and following is None and posts is None and not full_name:
        pm = re.search(r'"profilePage_(\d+)"', html)
        if pm and pm.group(1) != "0":
            priv = '"is_private":true' in html
            return _active_result(username, is_private=priv,
                                  details="Stats unavailable (API rate-limited)")
        if f'"username":"{username}"' in html or f'"owner":{{"username":"{username}"' in html:
            return _active_result(username, details="Stats unavailable (API rate-limited)")
        tm = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        title = tm.group(1).strip() if tm else ""
        if title == "Instagram" or "Page Not Found" in title or not desc:
            return _not_found(username)
        return None
    return _active_result(username, full_name=full_name, bio=bio,
                           is_private=is_private, is_verified=is_verified,
                           pic=pic, followers=followers, following=following, posts=posts)


def check_instagram_account(username: str) -> dict:
    clean = normalize_instagram_username(username)
    if not clean:
        return {"username": "", "status": "error", "message": "Empty username"}
    res = check_via_rest(clean)
    if res is not None:
        return res
    time.sleep(REST_TO_HTML_DELAY)
    res = check_via_html(clean)
    if res is not None:
        return res
    return {"username": clean, "status": "blocked", "message": "Unable to check",
            "details": "Instagram rate-limited verification. Please retry in a moment."}


def main(argv) -> int:
    """Batch CLI. `ig_check.py --usernames-json '["a","b"]'` prints one JSON
    object as its LAST stdout line: {"results": [...]} (for runPythonJson)."""
    import argparse
    ap = argparse.ArgumentParser(description="Instagram account checker")
    ap.add_argument("--usernames-json", default="[]",
                    help="JSON array of usernames to check")
    ap.add_argument("--delay-ms", type=int, default=600,
                    help="pause between checks (rate-limit courtesy)")
    ap.add_argument("--ndjson", action="store_true",
                    help="stream one JSON object per line as results arrive "
                         "(for the dashboard live feed) instead of a final summary")
    args = ap.parse_args(argv)
    try:
        names = json.loads(args.usernames_json)
    except Exception:
        names = []
    names = [normalize_instagram_username(n) for n in (names or [])]
    names = [n for n in names if n][:100]
    if args.ndjson:
        sys.stdout.write(json.dumps({"type": "total", "count": len(names)}) + "\n")
        sys.stdout.flush()
        done = 0
        for i, uname in enumerate(names):
            try:
                res = check_instagram_account(uname)
            except Exception as exc:
                res = {"username": uname, "status": "error", "message": str(exc)}
            done += 1
            sys.stdout.write(json.dumps({
                "type": "result", "result": res,
                "progress": {"done": done, "total": len(names)}}) + "\n")
            sys.stdout.flush()
            if i + 1 < len(names):
                time.sleep(max(0, args.delay_ms) / 1000.0)
        sys.stdout.write('{"type": "done"}\n')
        sys.stdout.flush()
        return 0
    results = []
    for i, uname in enumerate(names):
        try:
            results.append(check_instagram_account(uname))
        except Exception as exc:
            results.append({"username": uname, "status": "error", "message": str(exc)})
        if i + 1 < len(names):
            time.sleep(max(0, args.delay_ms) / 1000.0)
    sys.stdout.write(json.dumps({"results": results}))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
