> **Ported from `meta_auto_ai/docs/` (2026-09-27).** Paths rewritten
> `meta_auto_ai` → `meta_creator`. Engine/IG/TG-Web code is byte-identical
> across the two repos, so all DOM flows apply as-is. Differences to keep in
> mind: single-file `server.js` (no `server/lib/`), no `mem_guard.py` /
> nitro / Coinsta here, dashboard default port **3070**, TG pool is
> MTProto-first (`data/tg_sessions/`, headless — no TG browser tab).
>
> ---

# DevTools Inspection Runbook (live-page debugging)

How to drive the `chrome-devtools` MCP browser as a stand-in for the
automation's headed Chromium when debugging the Meta/IG funnel. Refer an agent
here for any "inspect meta.ai / auth.meta.com live" task.

## 1. Mirror the tools' mobile profile

The automation launches headed Chromium with a mobile profile
(`engine/eng_mix_launch.py`: SM-S928B, Android 14, 393x852, DPR 3, touch).
Replicate page-level fingerprint in DevTools:

- `emulate(pageId, viewport="393x852x3,mobile,touch", userAgent="Mozilla/5.0
  (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko)
  Chrome/124.0.0.0 Mobile Safari/537.36")`
- Known gap (do NOT "fix" code to match): UA override leaves
  `navigator.platform` as `Linux x86_64`; the tools' antidetect script
  (`engine/eng_antidetect.py`) spoofs `Linux armv8l` + client hints on top.
- `user_data_dir` (`profiles/insta_<slot>_<ts>`) can NEVER attach here:
  separate browser instance + Chromium profile lock + per-run ephemeral dirs.
  Mirror fingerprint only; inject session cookies if logged-in state is needed.

## 2. Core loop (always use fresh snapshots — uids expire)

1. `list_pages` → note the `pageId`.
2. `navigate_page(pageId, type=url, url)` — use apex `https://meta.ai/` for the
   "Where should we start?" variant, `https://www.meta.ai/` for the other.
3. `wait_for(pageId, text=[...])` for the expected marker.
4. `take_snapshot(pageId)` → `click(pageId, uid)` / `fill(pageId, uid, value)`.
5. `take_screenshot(pageId)` to see what a11y hides (iframes, challenge art).

## 3. Booking the funnel (verified 2026-09-17)

`meta.ai/` modal Sign up → `auth.meta.com` "Use mobile number or email" →
email Continue → Get started (Month/Day/Year listbox comboboxes + password,
Next disabled until valid) → details (suggested username, optional name,
avatar picker, Confirm) → `Code` box → checkpoint or `meta.ai/` home.

> Verified 2026-09-28 (mobile SM-S928B profile): desktop `meta.ai/` gates
> behind "Welcome to Meta AI" → Continue (mobile skips it); the email-step
> input is now `type=text autocomplete=username inputmode=email`; a live
> run ended at `www.meta.ai/?error=Token exchange failed` (account created,
> OIDC hop flopped → log in with the new creds).

- Listbox combobox: `click` combobox uid → `take_snapshot` shows
  `[role=option]` uids → `click` option uid.
- Temp inbox: `new_page(url="https://mail.td/", background=true)` → read
  address via `evaluate_script` (`document.body.innerText`); open the Meta row
  (two clicks: row, then viewer), code is in the `message` iframe —
  re-snapshot exposes it as StaticText.
- Avatar/selfie: `upload_file(pageId, uid=<picker button uid>, filePaths=
  ["/abs/path/selfie.png"])` — paths must be local to the browser machine.
- fbsbx reCAPTCHA frames are cross-origin: invisible to page DOM queries, use
  snapshot uids; image challenges are human-only — switch to audio
  ("Get an audio challenge") per engine order, never solve image grids here.
- Success signature: `meta.ai/` home, "Where should we start?", composer,
  NO sign-in modal. Failure landing to expect: `?error=Token exchange failed`
  (account exists, OIDC hop flopped → log in with the new creds).

## 4. Useful evaluate snippets (waitForStableDom=false for reads)

- Buttons: dump `button,a,input,[role=button]` with text/aria/href/visible.
- Frames: `[...document.querySelectorAll('iframe')].map(f=>f.src)` (note §3
  fbsbx caveat).
- Mail text incl. iframes: concatenate `body.innerText` +
  `f.contentDocument.body.innerText`; code regex `/\b(\d{6})\b/`.
- Env check: `navigator.userAgent / platform / maxTouchPoints /
  innerWidth×innerHeight / devicePixelRatio`.

## 5. Instagram Mobile Onboarding & Accounts Center Testing

For full engine-profile parity testing (cold sync, 2FA key extraction, and unified password change), see:
- Full profile testing guide: [`docs/devtools-profile-testing.md`](./devtools-profile-testing.md)
- Obsidian Master Runbook: `01 Projects/MetaAuto AI/Instagram Mobile Onboarding & Accounts Center Runbook.md`

### Key Invariants for Instagram Testing via DevTools:
1. **Never jump directly to Accounts Center URLs** (`/password_and_security/...`): Triggers `/accounts/scraping_warning/`. Always route through UI clicks:
   `Home Feed` → `Profile (a[href*="/<username>/"])` → `Options Gear (a[href*="/accounts/settings/?entrypoint=profile"])` → `Meta Account Link` → `Login and security`.
2. **Handle "No Instagram profile found"**: Fresh Meta accounts trigger this dialog on `/accounts/login/`. Click `View Meta account details for...` to launch the handle creation wizard.
3. **Keep Mail.td Alive on Tab 1**: Modifying password or 2FA triggers `"Two Step Verification - Check your email"`. Extract the 8-digit OTP from the `"Authenticate your profile"` email.
4. **Scrape 2FA Key**: Extract the 16-character Base32 secret from the setup dialog, compute the TOTP with `.venv/bin/python -c "import pyotp; print(pyotp.TOTP('<SECRET>').now())"`, and confirm.
