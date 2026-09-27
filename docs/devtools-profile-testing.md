> **Ported from `meta_auto_ai/docs/` (2026-09-27).** Paths rewritten
> `meta_auto_ai` → `meta_creator`. Engine/IG/TG-Web code is byte-identical
> across the two repos, so all DOM flows apply as-is. Differences to keep in
> mind: single-file `server.js` (no `server/lib/`), no `mem_guard.py` /
> nitro / Coinsta here, dashboard default port **3070**, TG pool is
> MTProto-first (`data/tg_sessions/`, headless — no TG browser tab).
>
> ---

# Chrome DevTools MCP Live Profile Testing Runbook

This guide explains how to drive the `chrome-devtools` MCP browser with **100% profile parity** ("pi-to-pi" fidelity) to debug and reverse-engineer the Meta + Instagram automation pipeline without black-box script failures.

---

## 1. Why Profile Parity Matters
The automation engine (`engine/run.py` and `runner.py`) uses a persistent Chromium context (`profiles/<slot_id>_<timestamp>`). This directory holds:
- Pinned device fingerprint (`device.json`).
- Meta, Facebook, and Instagram session cookies (`Default/Network/Cookies`).
- Web mailbox tokens for `mail.td` in localStorage (`Default/Local Storage/leveldb`).

When testing with Chrome DevTools MCP, simply visiting `https://www.instagram.com/` in an empty profile fails because the Meta SSO cookies and mailbox tokens are missing. By synchronizing the engine profile into DevTools MCP's cache, you gain live, interactive inspection of the **exact authenticated session**.

---

## 2. Mandatory Pi-to-Pi Profile Synchronization (FORCED)

> [!IMPORTANT]
> **MANDATORY PI-TO-PI SYM-LINK**:
> Do NOT copy profiles. Copying introduces credential drift, stale cookies, and desynchronized localStorage.
> Always point `chrome-devtools-mcp` directly at the live engine profile directory via symlink:
> Zero drift: every cookie, session token, and mailbox credential written by DevTools MCP or the engine lands in the single true source of truth.

```bash
# 1. Terminate any running browser holding locks on the profile
pkill -f "chrome-devtools-mcp" || true
pkill -f "/opt/google/chrome/chrome" || true
pkill -f "profiles/" || true

# 2. Confirm no live lock holder on the engine profile
.venv/bin/python -c "import warm_pool; print(warm_pool.lock_holder_alive('profiles/<id>'))"

# 3. Force-link DevTools MCP cache directly to the live engine profile
rm -rf ~/.cache/chrome-devtools-mcp/chrome-profile
ln -s /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator/profiles/<id> \
      ~/.cache/chrome-devtools-mcp/chrome-profile

# 4. Remove stale lock symlinks inside the profile if a crash occurred
rm -f /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator/profiles/<id>/Singleton*
```

---

## 3. Mobile Display Emulation Setup

The engine runs with a mobile Android profile. Replicate it immediately upon
connecting via DevTools MCP — this is the EXACT device used pi-to-pi in the
2026-09-18 dance (matches `eng_mix_launch.py` mobile defaults):

- **Model:** `SM-S928B` (pinned per account in `device.json`)
- **OS:** Android 14 · **Viewport:** `393x852` · **DPR:** `3.0` · **Touch:** on, mobile
- **UA:** `Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36`

```json
// 1. Resize viewport
{
  "ServerName": "chrome-devtools",
  "ToolName": "resize_page",
  "Arguments": { "pageId": 1, "width": 393, "height": 852 }
}

// 2. Set mobile device emulation (apply AFTER navigate, BEFORE reading DOM)
{
  "ServerName": "chrome-devtools",
  "ToolName": "emulate",
  "Arguments": {
    "pageId": 1,
    "viewport": "393x852x3,mobile,touch",
    "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
  }
}
```

> **Fidelity boundary (honest):** session + storage + viewport + UA + touch +
> DPR replicate pi-to-pi. NOT replicated: the JS fingerprint-spoof layer
> (`Linux armv8l` platform, Qualcomm Adreno 750 WebGL masking, Client Hints
> brands), the reCAPTCHA extension, and launch flags (window tile, ozone).
> Consequence: DOM structure and click flows are identical; fraud scoring is
> not. So fraud-sensitive steps (Meta signup, captcha) always run in the real
> tool browser — MCP takes over only post-auth. Layout mode is decided at
> page load: navigate FIRST, then emulate, then read (emulating a loaded
> desktop page does not re-trigger responsive layout; reload if needed).

---

## 4. Multi-Tab Architecture: Keeping Email Session Live

Always maintain two tabs in DevTools MCP:

### Tab 1 (Page 1): Web Mailbox (`https://mail.td/`)
Keep this tab open at all times. If the inbox doesn't show the account email immediately, inject the saved tokens from `data/sessions/<id>.json`:
```javascript
// evaluate_script on Page 1
() => {
  localStorage.setItem("tempmail_token", "<JWT_TOKEN>");
  localStorage.setItem("tempmail_account_id", "<ACCOUNT_UUID>");
  location.reload();
}
```
To check for new emails dynamically:
```javascript
() => {
  const iframe = document.querySelector('iframe');
  return {
    subject: document.querySelector('.subject')?.innerText,
    code: (iframe?.contentDocument?.body?.innerText || document.body.innerText).match(/\d{6,8}/)?.[0]
  };
}
```

### Tab 2 (Page 2): Instagram & Accounts Center
Open via `new_page` with url `https://www.instagram.com/accounts/login/` and apply mobile emulation.

---

## 5. Step-by-Step UI Click Navigation (No URL Jumps)

> **CRITICAL**: Never navigate directly to Accounts Center URLs (e.g. `/password_and_security/password/change/`).
> Direct jumps trigger Instagram's bot protection challenge: `/accounts/scraping_warning/` ("We suspect automated behavior on your account").

Follow the natural in-app UI click route:
1. **From Home Feed**: Click profile picture link in bottom navigation (`a[href*="/<username>/"]`).
2. **From Profile Screen**: Click Options gear icon at top-left `(16, 10)`:
   `a[href*="/accounts/settings/?entrypoint=profile"]`.
3. **From Settings Menu**: Click top Meta card:
   `a[href*="accountscenter.instagram.com"]`.
4. **From Accounts Center**: Click `a[href*="/password_and_security/"]`.

---

## 6. Security Gate & 2FA Extraction Recipes

### Email Security Checkpoint Intercept
When modifying password or 2FA, Meta presents `"Two Step Verification - Check your email"`.

> **Verified order (MCP, 2026-09-20): do 2FA FIRST, then password.**
> 2FA setup (`Get started`) triggers this email OTP; **changing the password
> while 2FA is already ON opens the Change-password form directly — no email
> re-auth.** The old order (password before 2FA) forced an unsolved email OTP
> and wedged. Coupled order:
> `ig_2fa_begin → ig_2fa_confirm → ig_set_password → [extra email] → mark_registered`.
1. Call `select_page(pageId: 1)` to switch to Mail.td.
2. Read 8-digit OTP from `"Authenticate your profile"` email.
3. Call `select_page(pageId: 2)` to return to Accounts Center.
4. Enter code into `textbox "Code"` and click `button "Continue"`.

### 2FA Secret Key Scrape & TOTP Verification
On the QR code screen:
1. Scrape the manual key text: e.g. `RAPQ K7VM RJF7 3CDC`.
2. Strip spaces to obtain the 16-character Base32 secret: `RAPQK7VMRJF73CDC`.
3. Compute the current 6-digit TOTP in terminal:
   ```bash
   .venv/bin/python -c "import pyotp; print(pyotp.TOTP('RAPQK7VMRJF73CDC').now())"
   ```
4. Click `button "Enter code"`, fill the 6-digit code into `textbox "Enter code"`, and click `button "Next"`.
5. Retrieve backup recovery codes from `button "backup codes"`.

---

## 7. Verified End-to-End Workflow (Pi-to-Pi, Single Taskly Task)

Manually executed and verified on profile `test_meta_20260919_003458`
(device pinned at creation, preserved on every resume):

- **Pi-to-Pi profile is required.** The profile created by
  `test/test_01_meta_only.py` is the single source of truth for the whole
  run: Meta cookies, Instagram `sessionid`, and `mail.td` tokens all live in
  `profiles/<id>/`. Never copy it; point tooling at it.
- **MCP role split used:** chrome-devtools MCP owns the Pi-to-Pi profile
  (`~/.cache/chrome-devtools-mcp/chrome-profile` symlink) for IG + mail tabs;
  Playwright MCP owns `telegram_profiles/tg_1` (`--user-data-dir`) for the
  Taskly bot tab. The two Chromiums run concurrently on different profiles —
  no `SingletonLock` fight. Merging TG IndexedDB into the Pi-to-Pi profile
  was attempted and does NOT restore the TG session (foreign origin storage
  is ignored); keep the profiles separate.
- **Email session must be persisted and restored.** `storage_state` only
  serializes `localStorage` for origins visited in that context session, so a
  re-dump must `goto` `https://mail.td/` (and IG home) before dumping, or the
  `tempmail_*` keys silently drop out of the session file. Verified live:
  same inbox + messages visible after engine close → MCP browser relaunch.
- **One Meta → one Instagram for the Taskly test.** Manual join path that
  works: IG login → "No Instagram profile found" → Meta card → name →
  suggested username → NTP opt-in "Allow and continue" → "I agree" →
  onboarding Skips. No second account, no account switching.
- **Taskly adaptation, bot name FIRST:** start task → copy First/Login/Password from bot → AC display name → AC username → AC password (+email OTP) → AC 2FA → send key → bot code → confirm → "Account Registered". Bot task window is ~8 minutes; key + confirm inside it. Mobile edit page has NO Name/Username fields — AC only.
- **Hard limits discovered:** display name is capped at two changes per
  14 days (script-driven renames burn the quota; afterwards the name is
  frozen and a task's required first name cannot be applied — likelihood of
  review rejection). Direct URL jumps to Accounts Center or profile pages
  trigger `/accounts/scraping_warning/` or `/challenge/` ("unusual login");
  always navigate via in-app UI clicks, and clear challenges with
  "This Was Me" instead of working around them. Fresh-context logins (e.g.
  headless checks) also trigger the unusual-login challenge — avoid them
  during a live run.
- **Session restoration behavior:** `resume_session` restores IG cookies plus
  IG + `mail.td` localStorage; pipeline parking (`dump_ig_storage_state`)
  is IG-only and drops mail tokens, so submit-time email challenges depend
  on the full test-style dump. After the task, records carry
  `status=Submitted`, `instagram_username`, `tg_submitted=1`,
  `tg_account=tg_1`; final session file holds `sessionid` + IG/mail origins.

## 8. Manual Single-Task Ledger (exact MCP tool calls, no secrets)

Profile `test_meta_20260919_003458`, bot task `Create Inst (No mail)` on
`tg_1`. Every browser step below is one MCP tool call; pauses between
mutations are deliberate (anti-automation pacing).

1. `playwright.browser_navigate(mail.td)` → snapshot shows creation inbox
   (restart proof #1: same inbox after engine close).
2. `playwright.browser_tabs(new, IG login)` → fill email+password →
   `browser_click(Log in)` → "No Instagram profile found" dialog →
   click Meta card → "Allow and continue" → NTA URL renders
   "Page isn't available" (dead end on desktop layout — switch to DevTools).
3. `opencode.json`: playwright `+ --user-data-dir <pi-to-pi>` → `opencode
   reload` → mail tab confirms same inbox (restart proof #2).
4. DevTools: `new_page(mail.td)` (tab 2), `new_page(IG login)` (tab 3) →
   `resize_page(393x852)` + `emulate(viewport UA)` → `fill_form` creds →
   `click(Log in)` → `wait_for` (20s+, slow point) → "No profile" dialog →
   `click(View Meta account details)` → name screen → `fill(name)` →
   `click(Next)` → username screen (suggested login available) →
   `click(Next)` → NTP opt-in `click(Allow and continue)` → terms
   `click(I agree)` → Loading 45s+ (slow point) → `/accounts/registered/`
   → dismiss save-login → onboarding Skips ×4 → home feed, logged in.
5. Profile-URL jump → `/accounts/scraping_warning/` (soft, Dismiss) →
   redirects home. Lesson: UI clicks only from here on.
6. `submit_one.py` (script, killed after): adapted name+username, failed
   password ("form not found"), failed 2FA ("entry not found"), cancelled
   task, released lease. Takeover goes fully manual.
7. TG leg: `playwright` config → `--user-data-dir telegram_profiles/tg_1`
   → `browser_navigate(web.telegram.org/a/)` (session live) → open
   Taskly Bot → `browser_click(Show bot keyboard)` → `browser_click(Tasks)`
   → reveal keyboard → `browser_click(🔥 Create Inst (No mail))` → task
   card → `browser_click(▶ Start)` → read First/Login/Password via
   `browser_evaluate(innerText)`.
8. IG leg (DevTools): profile → Edit profile → mobile page has NO
   Name/Username inputs (Website only — mis-fill reverted) → profile →
   Options → settings → Meta card → AC overview → Profiles →
   `s31rrg Instagram` → Name form: value burned twice already →
   save attempt → alert "can't change name… twice within 14 days"
   (quota burned by script) → Back → Username form → clear →
   fill task login ("valid") → Done → verified persisted.
9. AC `password_and_security` → Change password → email OTP challenge →
   mail tab: open `Authenticate your profile` → regex 8-digit code →
   fill Code → Continue → 3-field form → fill current/new/new →
   submit → dialog closes, no error (verified next day via fresh-login
   checkpoint = credentials correct).
   > ⚠️ **Superseded 2026-09-20:** this ledger changed the password *before*
   > 2FA. The verified, safer order is **2FA first** (which is what triggers the
   > email OTP) **then** Change password (no email re-auth with 2FA ON). See §6.
10. Fresh-login checks from a blank profile trigger "Unusual login"
    challenge → confirmed "This Was Me" in DevTools (lesson: no
    parallel verification logins mid-run).
11. AC `two_factor` → Get started → Authentication app (pre-checked) →
    Continue → QR + grouped key → `evaluate(innerText)` key scrape →
    Playwright composer `browser_type(key, submit)` → bot returns
    one-time code + "confirm registration" → reveal keyboard →
    `browser_click(✅ Account registered)` → "report received, please
    wait" (review ~64 min). Task window Start→cancel ≈ 8 min: send the
    2FA key and confirm inside it.
12. Second task round (new creds): username re-changed, password
    re-changed, same 2FA key re-sent (2FA already on), registered again
    — all inside the window. Records → Submitted; session re-dumped
    (warm origins first); both profiles unlocked; playwright config
    reverted to temp profile.

## 9. Expected vs Actual (This Run)

| Expected | Actual |
|---|---|
| Same email session after restart | Confirmed in two MCP browsers |
| One Meta + one IG, single Taskly task | Done; report accepted ("received, please wait"), review ~64 min |
| Name/username/password per bot creds | Username + password applied and verified; **name frozen** (2-change cap burned earlier) |
| 2FA via bot key round-trip | 2FA enabled, key sent, bot code received, registration confirmed |
| No scraping warnings | Soft `scraping_warning` on direct profile URL (dismissed); `challenge` after headless logins (confirmed "was me") |
| chrome-devtools stable | Required orphan-Chrome cleanup after MCP reload (stale `SingletonLock` holder blocks reconnect) |

---

## 10. Audit findings & fixes (2026-09-19) — code-synced

Everything below is implemented in the repo; this section is the "why".

### 10.1 Every Playwright entrypoint must point at the bundled browser
`worker.py`, `tg_login.py`, `open_session.py`, `test/test_01`, `test_02`,
`test_e2e_devtools.py` all call `run._point_playwright_at_browsers()`. Without it
Playwright looks in the empty `~/.cache/ms-playwright` and the engine **silently
falls back to system Chrome** — different fingerprint and far slower
(measured DOB 36s→5s, Meta email 30s→8s). Standalone launchers (Scan QR / Open)
fail entirely without it ("can't open/connect TG").
> MCP note: the MCP chrome uses `~/.cache/chrome-devtools-mcp/chrome-profile`.
> Killing it is required to free a profile before launching another browser on
> the same dir; re-point it with a symlink per §2.

### 10.2 mail.td REST OTP (list vs detail)
`engine/eng_mix_mail.py::_mailtd_api_code`:
- `GET /api/accounts/{id}/messages?page=1` → **metadata only** (id/sender/subject/preview).
- `GET /api/accounts/{id}/messages/{mid}` → **`html_body`** with the code.
- `Authorization: Bearer <tempmail_token>`, fetched from the live mail page (Cloudflare).
- HTML tag-strip + entity-unescape, poll 1.5s (**free limit 1 req/s**), heartbeats.
- Limits: 40 MB/inbox, messages deleted after 1h, mailbox creation = proof-of-work.
Parsing the list alone was the "can't grab the OTP" bug (code arrived, parser
returned None forever). Measured fetch now **~1s**.

### 10.3 Instagram dead-ends abort
Bare chooser (profile named after the email local part + "Use another profile"
/ "Create new account") and `/accounts/login` bounces → `_is_ig_dead_end_chooser()`
→ `IGDeadEnd`. Wired in `instagram/login.py` (before "Continue"),
`instagram/join.py` (`ig_click_meta_card` loop — was spinning 90s — and
`ig_dismiss_onboarding`), `instagram/identity.py`. Propagated so the browser
closes and the slot retries.

### 10.4 Accounts Center batching (4 → 2 navigations)
`instagram/password.py::_ac_in_section()` treats a section sub-page as "already
there": name+username share `/profiles/`; password+2FA share
`/password_and_security/` (steps Back to the root from a sub-page). Reduces
hydration cost and scraping-warning exposure.

### 10.5 No blind sleeps on interactive screens
Password post-OTP (`_form_open()` poll), 2FA entry, and 2FA code submit poll at
500–700 ms. `ig_2fa_confirm` verifies the input value landed (React can swallow
`fill`) before pressing Enter — otherwise the code "doesn't submit".

### 10.6 Watchdog caveat
`/tmp/opencode/watchdog.sh LOG STALL cmd…` kills a silent step after STALL
seconds. **A kill loses Chrome cookies** — `sessionid` disappears and later AC
steps fail ("AC entry failed: IG session dead"). Let runs finish / close cleanly.

### 10.7 Measured IG-half timings
resume 8.5s · login 9.4s · Meta card 5.1s · join 29.4s · onboarding 19.7s → ~72s.
Meta-only run: 4m38s total (OTP 1s, DOB 2s, no selfie re-attempts).

### 10.8 AC overlay wedge + no spurious step-Back (round 4, 2026-09-19)
The email step left the **Contact-information overlay** open
(`accountscenter.instagram.com/youraccount/contact_points?is_from_dialog=true`);
the next `_ac_section("/password_and_security/")` searched for the section row
*inside that overlay*, missed twice, and hard-failed `AC section unreachable`
(run #2 log; user screenshot confirmed the overlay still open).

- **Fix:** `instagram/password.py::_ac_leave_subpage()` closes/backs any open AC
  overlay/sub-page to the AC home list **before** searching for the next section.
  Home detection requires **≥2 visible** section titles — the AC home rows stay
  in the DOM behind the overlay, so `count()` alone false-positived, and the
  first version returned `True` without closing anything. Verified with
  `test/ac_dom_probe.py` (overlay URL → `accountscenter.instagram.com/`, then
  `_ac_section(password)` reached).
- **Fix:** step Back to the section root **only from a genuine sub-page**
  (`if not cur_path.rstrip("/").endswith("/" + clean_path)`). The old check
  compared the full URL to the bare path fragment, so it was always true and
  clicked Back even from the root — dropping to the AC home after every password
  change (run #3 `13:58:49`). Verified with `test/ac_stay_probe.py`
  (`stayed_on_section=True`).

### 10.9 Never close the 2FA section (round 4)
`_dismiss_extra_protection_upsell` closed the **2FA page itself**: its
`Get started` guard used `button:has-text(...)`, but IG renders that control as
`div[role=button]`, so it fell through to clicking the page X — bouncing out to
`/password_and_security/` and forcing a duplicate 2FA entry (run #4
`14:12:18` dismiss → `14:12:22` "2FA bounced out").
**Fix:** refuse to dismiss when `two_factor` is in the URL, and detect the intro
via `get_by_text("Get started")`.

### 10.10 Change-password toast poll (round 4)
The success wait polled at a **2000 ms** granularity, forcing ≥2 s (often 4–6 s)
of dead wait after submit (run #4 `14:12:06` → `14:12:14`). Now polls at 500 ms.

### 10.11 Submit gate (round 4)
The coupled cycle did `runner.tg_submitted = bot.mark_registered()` and then
`ok = True` **unconditionally**, so an unconfirmed registration was still saved
as `Submitted`. **Fix:** retry the register tap once, then raise — never record a
false `Submitted`. The other call sites already gate on the return
(`tg_worker.py:347`, `core/lifecycle.py:412`).

## 11. Password-form React swallow + the reject point (2026-09-21)

- **Change-password fields swallow `fill`.** Live: filling the 2FA "Enter code"
  box left **Next disabled**, and the AC Change-password fields only took with the
  native setter + `input`/`change`/`blur`. `_clean_fill` now verifies
  `input_value()` and re-injects via `_react_set_value`; `ig_set_password` asserts
  `[0]=current(old)`, `[1]=new`, `[2]=new` **before** submit. Without this the
  submit is a no-op → `reason=not_confirmed`.
- **Reject point = `__coig_login`.** A fresh IG account driven straight into
  settings/AC can bounce `/accounts/settings/` → `/accounts/login/?next=…&__coig_login=1`;
  the API returns `{"require_login":true,"message":"Please wait a few minutes before you try again."}`.
  The one-tap saved-account chooser does **not** recover it. It is velocity-driven
  (a second fresh account minutes later was fine) — back off, don't retry.
- **Desktop view** (no emulation) renders the desktop web app: 500×797, DPR 1,
  UA `X11; Linux x86_64`, `ontouchstart` false, left nav rail + top nav. Mobile
  (393×852 DPR3 touch) is the tested path; desktop changes every selector and the
  Telegram Web `/a/` layout, so it is a refactor, not a drop-in.

## 12. Smart AC entry & recovery (2026-09-21 round 2)

- **Back-out onboarding + follow warm-up** — ported from `meta_creator`: the
  `/accounts/registered/` cards are exited with the **top-left Back** button
  (never Skip), then `ig_follow_suggested()` follows ~2 suggested profiles on
  the feed before the first AC navigation. Replaces the removed feed-scroll
  settle (`INSTA_AC_SETTLE_SECS`). Env: `INSTA_FOLLOW_AFTER_LOGIN=0`,
  `INSTA_FOLLOW_COUNT`.
- **No Reload on AC routes** — `_recover_something_went_wrong` takes the Way Out
  directly on `/accounts/settings`/`accountscenter` (the Reload landed on
  `/accounts/scraping_warning/` and dropped the session → chooser → dead end).
- **Chooser re-login** — `_chooser_relogin` clicks Continue → fills the owned
  password → verifies `sessionid`; fallback "Use another profile" → full login.
  Wired before `IGDeadEnd` in the AC phase only.
- **Pipeline-wide cooldown** — any throttle hit (`__coig_login`, `require_login`,
  `please wait a few minutes`, `rendered blank`, …) pauses **all** coupled slots.
- **Dashboard** — `GET /api/diag/reasons` + live "Failure Reasons" panel.
- **Stuck browsers close in BOTH modes** — strict failures force-close in headed
  mode too; retention is opt-in via `INSPECT_KEEP_VISIBLE=1` (cap
  `INSPECT_BROWSER_CAP`, default 6). The `STRICT stop` log and the
  `held_open`/`closed` slot event now report the TRUE outcome.
- **Risky-contact-point gate** — `_is_email_risky_screen()` +
  `ig_fix_risky_contactpoint()` handle IG's *"Your email may not be secure"*
  (`/accounts/update_risky_contactpoint/`, no Skip) by adding a fresh email;
  else the cycle dead-ends with `email_risky_contactpoint` (a throttle marker).

