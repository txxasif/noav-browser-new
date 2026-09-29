---
name: meta-creator-ig-devtools
description: >-
  Test and reverse-engineer Instagram and Meta Accounts Center flows (password change,
  2FA setup, email linking) live with 100% engine profile parity using Chrome DevTools MCP.
  Covers dual-tab mail.td OTP capture, React prototype setters, mobile emulation, and
  preventing regression across different bot task pipelines.
triggers:
  - "test ig"
  - "test instagram"
  - "mcp test"
  - "debug accounts center"
  - "change password test"
  - "2fa test"
  - "learn task"
  - "inspect profile"
---

# Instagram & Meta Accounts Center DevTools MCP Testing Runbook

Step-by-step guide for testing Instagram and Meta Accounts Center flows live with **100% engine profile parity ("pi-to-pi")** using `chrome-devtools` MCP.

---

## 0. Fundamental Principles & Pipeline Parity Rule

> [!IMPORTANT]
> **MULTI-TASK PIPELINE NON-INTERFERENCE (CRITICAL)**:
> Different tasks execute steps in different orders:
> 1. **2FA First** (e.g. `cookie_2fa`): 2FA setup triggers the email OTP challenge ("Check your email"). Once solved and 2FA is active, subsequent Password Change opens directly with NO email OTP.
> 2. **Password First** (e.g. Taskly `2fa` flow: `["password", "email_link", "2fa", "register"]`): Changing password triggers the email OTP challenge immediately. Once solved, subsequent 2FA setup opens directly with NO email OTP.
>
> **Any code change or test MUST support both orders.** Never assume an OTP is only for 2FA or only for Password.

---

## 1. Pick an Account from `data/accounts.json`

Check available accounts:
```bash
python3 -c "
import json
with open('data/accounts.json') as f:
    accs = json.load(f)
for a in accs[-5:]:
    print(a.get('id'), a.get('email'), a.get('username'), a.get('profile_dir'))
"
```
Each account record contains:
- `email`: e.g. `3flf9h@nqmo.com`
- `password`: current Meta password
- `mail_tokens`: `tempmail_token` and `tempmail_account_id` for `mail.td`

---

## 2. Profile Synchronization (Pi-to-Pi Fidelity)

Chrome DevTools MCP uses `~/.cache/chrome-devtools-mcp/chrome-profile`. To inspect the exact authenticated session without cookie/session drift:

```bash
# 1. Terminate any running browser holding locks on the profile
pkill -f "chrome-devtools-mcp" || true
pkill -f "/opt/google/chrome/chrome" || true
pkill -f "profiles/" || true

# 2. Link DevTools MCP cache directly to the engine profile
rm -rf ~/.cache/chrome-devtools-mcp/chrome-profile
ln -s /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator/profiles/<profile_id> \
      ~/.cache/chrome-devtools-mcp/chrome-profile

# 3. Clean stale lock symlinks
rm -f /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator/profiles/<profile_id>/Singleton*
```

---

## 3. Mobile Emulation (Android Viewport & UA)

Instagram Accounts Center mobile layout must be emulated:
- **Viewport**: `393x852`, DPR: `3.0`, Touch: `true`, Mobile: `true`
- **User Agent**: `Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36`

In MCP:
```json
// resize_page
{ "pageId": 1, "width": 393, "height": 852 }

// emulate
{
  "pageId": 1,
  "viewport": "393x852x3,mobile,touch",
  "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
}
```

---

## 4. Multi-Tab Architecture: Live Mailbox for OTP

Keep two pages open:
- **Page 1**: Instagram & Accounts Center
- **Page 2**: `https://mail.td/` (Web Mailbox)

### Setting up Page 2 (Mailbox):
1. `new_page(url: "https://mail.td/")`
2. Inject account's `mail_tokens` into `localStorage`:
```javascript
// evaluate_script on Page 2
() => {
  localStorage.setItem("tempmail_token", "<tempmail_token>");
  localStorage.setItem("tempmail_account_id", "<tempmail_account_id>");
  location.reload();
}
```
3. To read OTP code from incoming email (`Authenticate your profile` from `noreply@account.meta.com`):
```javascript
() => {
  const iframe = document.querySelector('iframe');
  const text = (iframe?.contentDocument?.body?.innerText || '') + ' ' + (document.body?.innerText || '');
  const m = text.match(/\b\d{6,8}\b/g);
  return { code: m ? m[0] : null, preview: text.slice(0, 300) };
}
```

---

## 5. In-App Natural UI Click Navigation (No URL Jumps)

> [!WARNING]
> Never jump directly to Accounts Center URLs (e.g. `https://accountscenter.instagram.com/password_and_security/password/change/`). Direct jumps trigger `/accounts/scraping_warning/` or login checkpoints.

Follow natural UI clicks:
1. **Home Feed**: Click profile avatar in bottom nav (`a[href*="/<username>/"]`).
2. **Profile**: Click Settings gear (`a[href*="/accounts/settings/?entrypoint=profile"]`).
3. **Settings**: Click Meta Account card (`a[href*="accountscenter.instagram.com"]`).
4. **Accounts Center Home**: Click `Login and security` (`a[href*="/password_and_security/"]`).

---

## 6. Trap Prevention (Menu & Selector Pitfalls)

Under Accounts Center **Login and security**, the menu items are:
- `Contact info`
- `Change password`
- `Two-factor authentication`
- `Passkey`
- `Where you're logged in`
- `Emails from Meta`
- `Back to Instagram Settings`

### Critical Matching Traps:
- **NEVER use bare `"Meta"` or `:has-text("Meta")`**:
  `div[role="button"]:has-text("Meta")` matches **`Emails from Meta`**! Clicking it opens the "Emails from Meta" audit screen instead of the account row.
- **NEVER use generic `:has-text("Instagram")`**:
  Matches **`Back to Instagram Settings`**, bouncing out of Accounts Center.
- **NEVER assume an Account Picker screen exists**:
  When only one Meta account is attached, clicking `Change password` goes **directly to the form** with an email challenge modal on top. Do not call `_ac_choose_account` while `_challenge_present()` is True!

---

## 7. Solving the Email Challenge & React Input Fill

When Meta presents `"Two Step Verification - Check your email"`:
1. Read the 8-digit OTP from **Page 2** (`mail.td`).
2. Target the input on **Page 1**:
   - Element is `<input type="password" ...>` with accessible name `"Code"`.
3. **React Prototype Setter (Mandatory)**:
   React synthetic events swallow basic `input.value = code`. Use the prototype setter:
```javascript
// evaluate_script on Page 1
(code) => {
  const input = document.querySelector('input[type="password"], input');
  input.focus();
  const proto = HTMLInputElement.prototype;
  const d = Object.getOwnPropertyDescriptor(proto, 'value');
  if (d && d.set) { d.set.call(input, code); } else { input.value = code; }
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  input.dispatchEvent(new Event('blur', { bubbles: true }));
}
```
4. Click `button "Continue"`.
5. The modal closes, revealing the unlocked Change Password or 2FA form.
