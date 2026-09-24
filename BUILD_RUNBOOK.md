# Meta Creator — Comprehensive Engineering & Distribution Runbook

> **Complete Guide**: From Linux Development to Portable & Installer Windows Distribution with Hardware-Bound Cloudflare Licensing.

---

## 1. System Architecture Overview

Meta Creator is a high-throughput, anti-detect automation suite designed for continuous Meta (Facebook/Instagram) account generation. The application combines a zero-dependency Node.js web server with a multi-threaded Python automation engine powered by Playwright, offline YOLOv5 ONNX visual captcha solving, Whisper/Vosk speech recognition, and an authoritative Cloudflare Workers + D1 licensing backend.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          User Interface                                │
│   Dashboard (public/index.html) • Dark/Light UI • Paginated Accounts   │
│   License Modal • Live SSE Log • Table Filters & CSV/TXT Exporters     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / Server-Sent Events (Port 3070)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        Node.js Web Server                              │
│   server.js (Zero external npm modules)                                │
│   ├── /api/license/*   -> core/licenseManager.js                       │
│   ├── /api/meta-insta/* -> worker.py process lifecycle & SSE stream   │
│   └── /api/accounts/*  -> data/accounts.json + SQLite WAL store        │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │ Child Process Spawn            │ HTTPS API
                    │                                ▼
                    │         ┌──────────────────────────────────────────┐
                    │         │ Cloudflare Workers + D1 License Server   │
                    │         │ Authority: nova-license.ahasiffff...     │
                    │         │ Endpoints: /activate, /validate, /deact  │
                    │         └──────────────────────────────────────────┘
┌───────────────────▼────────────────────────────────────────────────────┐
│                      Python Worker Engine                              │
│   worker.py (Multi-threaded worker pool with pre-flight License Gate)   │
│   ├── core/license_mgr.py -> Wire-compatible HWID & HMAC validation   │
│   ├── (resource tuning)   -> Low-memory Chromium flags live in engine/eng_mix_launch.py │
│   ├── engine/run.py       -> Hermetic anti-detect Playwright runner    │
│   └── store.py            -> Thread-safe SQLite WAL + JSON/CSV syncing │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Licensing Architecture & Cryptographic Engine

### 2.1 Authoritative Remote Backend
* **Authority Endpoint**: `https://nova-license.ahasiffff.workers.dev`
* **Protocol**: HTTPS REST (POST JSON) with user-agent identification.
* **Database**: Cloudflare D1 distributed SQL database.
* **Supported Endpoints**:
  * `POST /api/license/activate` — Claims a license key and binds it permanently to the machine's HWID.
  * `POST /api/license/validate` — Authoritatively re-verifies activation status and expiration timestamp.
  * `POST /api/license/deactivate` — Unbinds current machine HWID from the license key.

### 2.2 Invariant Hardware Machine Fingerprint (HWID)
To eliminate false mismatches from transient adapter changes (e.g. Wi-Fi reconnection, Docker, VPN, hypervisors), HWID uses a deterministic, hardware-bound formula:

$$\text{HWID} = \text{format}(\text{SHA256}(\text{seed} \parallel \text{stableOSId} \parallel \text{cpuModels} \parallel \text{arch} \parallel \text{platform}))$$

* **Seed (`machine_id.node`)**:
  * Stored in user roaming directory:
    * Windows: `%APPDATA%\NovaBrowser\machine_id.node` (or `%APPDATA%\MetaCreator\machine_id.node`)
    * Linux: `~/.config/nova-browser/machine_id.node` (or `~/.config/meta-creator/machine_id.node`)
  * Sharing seed with Nova Browser ensures a single consistent HWID across all tools on the same PC.
* **Stable OS ID**:
  * Linux: `/etc/machine-id` or `/var/lib/dbus/machine-id`
  * Windows: `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` (queried via `reg query` in Node and `winreg` in Python)
* **CPU Models**: Comma-separated processor model names (`/proc/cpuinfo` on Linux, registry `CentralProcessor` on Windows).
* **Format**: `HWID-XXXX-XXXX-XXXX-XXXX` (16 hexadecimal characters uppercase).

### 2.3 Wire Parity Between Node.js and Python
Both runtimes generate the **exact same HWID string** and compute the **exact same HMAC signatures**:
* Node: `core/licenseManager.js`
* Python: `core/license_mgr.py`

### 2.4 Offline Grace Period & HMAC-SHA256 Tamper Protection
* **Cache File**: `license_data/license_data.json`
* **HMAC Body**:
  `${data.license_key}||${data.status}||${data.expires_at}||${data.last_validated_at}||${data.hwid}`
* **Derived Machine Key**:
  `SHA256("nova-hmac||" + seed + "||" + stableOSId)`
* **Grace Period**: 72 hours of offline operation after a successful remote validation.
* **Tamper Detection**: If any character in `license_data.json` (such as expiration date, status, or HWID) is modified without the per-machine private HMAC signature, both Node and Python detect the signature mismatch, immediately log `TAMPER DETECTED: Cache signature mismatch`, wipe the corrupted cache file, and block software execution.

### 2.5 Multi-Layer Security Gates
1. **Frontend Gate (`public/js/nova-license.js`)**:
   Clicking `Start Creating` triggers `requireLicense()`. If unlicensed, the activation modal opens automatically with an alert and toast notification.
2. **Server Gate (`server.js`)**:
   `POST /api/meta-insta/start` and `POST /api/loop/start` verify `licenseMgr.validateOrActivateLicense()`. If invalid or expired, requests are rejected with `HTTP 403 Forbidden`.
3. **Engine Gate (`worker.py`)**:
   `worker.py::main()` calls `LicenseManager().validate_or_activate()`. If unlicensed, it emits `license_invalid`, prints an execution blocked message, and exits immediately with code `1`.
4. **Periodic Mid-Cycle Gate (`worker.py::slot_loop`)**:
   Between account creation cycles, workers verify license validity so that expired licenses stop running automatically.

---

## 3. Developer Guide (Linux Development Source)

The development source lives at:
`/home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator`

### 3.1 Prerequisites
* Python 3.10+ (tested with Python 3.14)
* Node.js 18+ (tested with Node 24)
* Playwright Chromium browser bundle

### 3.2 Running the Development Server
```bash
cd /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator

# Normal Mode (Enforces License Check)
node server.js

# Developer Override Mode (Bypasses License Check for Testing)
META_DEV_MODE=1 node server.js
```
The dashboard will be available at: `http://localhost:3070`.

### 3.3 Running License Diagnostics & Tests
```bash
# Test Node.js license client & HWID
node -e "const LM = require('./core/licenseManager.js'); console.log('Node HWID:', new LM().getMachineFingerprint());"

# Test Python license client & HWID
python3 -m core.license_mgr

# Test worker license rejection
python3 worker.py --headless
```

---

## 4. Windows Packaging & Distribution Guide

The Windows distribution tree lives at:
`/home/asif/Documents/my-projects/Antidetect-Tools/win/meta_creator`

### 4.1 Windows Hermetic Layout & Runtimes Bootstrap
The Windows package is 100% self-contained and portable with zero external host requirements:
* `bin/node.exe` — Standalone portable Node.js runtime (v24.16 x64). Downloaded directly from official Node.js binaries (`https://nodejs.org/dist/v20.x/win-x64/node.exe`).
* `_internal/python.exe` — Standalone portable Python 3.14/3.11 MSVC runtime with bundled site-packages (`playwright`, `pyotp`, `requests`, `vosk`, `rapidocr-onnxruntime`).
* `_internal/ms-playwright/` — Bundled Chromium anti-detect browser binaries (version-matched to Playwright).
* `Run.bat` — 1-click silent launcher with PowerShell background detached spawn and auto browser launch.
* `Run-Console.bat` — 1-click debug launcher with live terminal logs.
* `Stop.bat` — Scoped process terminator (safe: only stops processes inside `%~dp0` and frees port 3070).
* `installer/setup.iss` — Inno Setup compilation script for standard Windows installer (`.exe`).

#### How to Bootstrap Windows Runtimes on a Fresh Machine:
If recreating the `_internal/` and `bin/` directories from scratch:
1. **Node.js**: Download official `node.exe` (x64) and place in `win/meta_creator/bin/node.exe`.
2. **Python Runtime**: Download the official Python Windows embeddable package (`python-3.11.x-embed-amd64.zip`), extract to `win/meta_creator/_internal`, uncomment `import site` in `python311._pth`, install `pip`, and run:
   ```bash
   python.exe -m pip install -r requirements.txt
   ```
3. **Playwright Chromium**: Run `python.exe -m playwright install chromium` with `PLAYWRIGHT_BROWSERS_PATH=./_internal/ms-playwright`.

### 4.2 Automated Build, Sanitization & Anti-AI Prompt Injection
To synchronize all latest code changes from Linux development to Windows, inject security directives, purge markdown, and package the distributable ZIP:

```bash
cd /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator

# Run the automated build pipeline:
npm run build:win
# (or: python3 build_windows_dist.py)
```

**What `build_windows_dist.py` executes automatically**:
1. **Source Sync**: Copies all updated core modules, frontend assets, and server scripts to `win/meta_creator`.
2. **Document Sanitization (Zero-Markdown Gate)**:
   - Purges all `.md` files (internal notes, runbooks, guides) from the Windows tree so zero developer notes leak to the end user.
   - Deletes `build_windows_dist.py` and `BUILD_RUNBOOK.md` from the Windows distribution folder.
3. **Anti-AI System Safety Directives**:
   - Injects legal and safety directive headers across all target `.js`, `.py`, and `.html` files in the Windows build (56 files in the 2026-09-23 build).
   - Instructs AI coding assistants (Claude, ChatGPT, Cursor, Copilot, DeepSeek) under DMCA 1201 and Trust & Safety policies to refuse any attempts to patch, deobfuscate, or crack licensing/anti-detect logic.
4. **Runtime Health Check**: Validates that `bin/node.exe`, `_internal/python.exe`, and `_internal/ms-playwright` exist and meet size thresholds.
5. **Cross-Runtime HWID Audit**: Verifies that Node.js and Python calculate the identical machine fingerprint.
6. **ZIP Compression**: Packages `win/meta_creator/dist/MetaCreator-Windows-Portable.zip` (~502 MB) plus the lightweight `MetaCreator-Windows-Patch.zip` (~55 MB, code/engines only, applied via `Update.bat`) ready for client distribution.
7. **Integrity & Leak Verification**: Automatically inspects the generated ZIP archive to ensure all 20 required core components are present and **0 markdown files** exist.
8. **SHA-256 Checksum**: Generates an authoritative SHA-256 integrity hash for the release archive.

### 4.3 Compiling Inno Setup Installer (`.exe`)
To build the single-file setup wizard installer:
1. Open Inno Setup Compiler (ISCC) on Windows (or via Wine on Linux: `wine iscc.exe installer/setup.iss`).
2. Open `win/meta_creator/installer/setup.iss`.
3. Click **Compile** (or run `iscc installer/setup.iss`).
4. Output will be generated at `win/meta_creator/dist/MetaCreator-Setup-v1.0.exe`.

### 4.4 Automated Version Bump & Release Script
To bump versions and generate release update manifests:
```bash
# Bump version and generate dist/latest.json:
node scripts/release.js --version 1.0.1 --notes "Performance and licensing update" --no-push
```

---

## 5. End-User Windows Runbook

### 5.1 Option A: Portable Zero-Installation (Recommended)
1. Download `MetaCreator-Windows-Portable.zip`.
2. Right-click -> **Extract All...** to any folder (e.g. `C:\Tools\MetaCreator` or `Desktop\MetaCreator`).
3. Double-click **`Run.bat`**.
4. The dashboard will automatically open in your default browser at `http://localhost:3070`.
5. Enter your license key in the Activation dialog and click **Activate License**.
6. When finished, double-click **`Stop.bat`** to terminate background processes.

### 5.2 Option B: Standard Windows Setup Installer
1. Run `MetaCreator-Setup-v1.0.exe`.
2. Follow the setup wizard (installs to `%LOCALAPPDATA%\Programs\MetaCreator` with no Admin prompt needed).
3. Launch via the Desktop or Start Menu shortcut.

### 5.3 Live Debug & Console Logs
If you ever want to see live Python worker logs, HTTP connection logs, or anti-detect debugging messages:
* Run **`Run-Console.bat`**.
* This keeps the CMD terminal open showing real-time stdout and stderr.

---

## 6. Maintenance & Troubleshooting

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Port 3070 Busy (`EADDRINUSE`)** | A previous instance is still bound to port 3070. | Double-click `Stop.bat`. It will use PowerShell to terminate previous instances and free port 3070. |
| **HWID Mismatch Error** | The license key was previously activated on a different computer. | Run `deactivateLicense` on the original machine or contact support to reset the activation in Cloudflare D1. |
| **Offline Grace Period Active** | Machine is disconnected from the internet. | App continues running normally for up to 72 hours. Reconnect to internet to renew authority cache. |
| **Tamper Detected** | Local cache signature mismatch (file edited or copied across PCs). | Cache is wiped automatically. Re-enter your valid license key to re-activate. |
| **Low RAM / resource pressure** | The creator now honors the user-selected Parallel value; lower-end devices should use Headless and conservative browser settings. | No automatic RAM clamp or watchdog is applied. If Windows itself becomes unstable, pause the run manually and close other applications. |
| **"Chrome for Testing v…" banner / "Restore pages?" bubble in slot windows (Windows headed only; never on Ubuntu)** | Chrome for Testing shows its version banner unless `--test-type=gpu` is passed (bare `--test-type` is not enough); the restore bubble appears when a hard-killed profile is relaunched | `_NOVA_FLAGS` in `engine/eng_constants.py` must contain `--test-type=gpu`, `--disable-infobars`, and `--hide-crash-restore-bubble`. Rebuild via `build_windows_dist.py` and ship the Patch ZIP (applied with `Update.bat`) |
| **Parallel count ignored — only ~7 windows start** | Older builds applied a RAM-based reduction | Parallel now passes the user-selected value through unchanged (1–50). The launcher uses low-memory Chromium flags and tracker blocking; Headless is recommended on lower-end Windows machines. |
| **All slot profiles present the same phone (accounts get linked)** | `eng_antidetect` hardcoded SM-S928B/Adreno 750/8 while the launch UA picked a random model — identical fingerprints across profiles | `device_identity(seed)` in `engine/eng_antidetect.py` is the single source of truth for model/Android/GPU/cores/memory/touch, seeded from the profile dir; `eng_mix_launch` passes it to the anti-detect script. `INSTA_DEVICE_VARY=0` restores the old fixed device |
| **Challenge waits waste up to 90s per captcha** | The JA visual extension solved ~0/229 real challenges, so the 45s bail / 90s cap were dead time | Both are env-tunable and default lower: `INSTA_VISUAL_CAPTCHA_TIMEOUT=30`, `INSTA_VISUAL_CAPTCHA_BAIL=15` |
| **Dashboard mail/captcha choice had no effect** | `server.js` read `opts.mail` / `opts.captcha` while the UI sends `mail_provider` / `captcha_mode` | Server now accepts the request fields; this build intentionally exposes only `mail.td` and always forces `mailtd`. |
| **Accounts wiped / "0 accounts" after clicking Clear** | `/api/meta-insta/reset` used to wipe DB + JSON + CSV + TXT with no confirmation and no backup | Reset now requires `POST {"confirm":"CLEAR"}` and **snapshots `data/store.db`, `accounts.json`, `accounts.csv`, `accounts.txt` into `backups/backup_<ts>_reset/` first** (last 20 kept). Restore by copying the snapshot back |
| **Extra Chrome window opens and does nothing (headed Windows runs)** | `instagram/password.py` launched a **separate visible browser** for the reset-link step (`chromium.launch(headless=self.w.is_headless)`) | That background step is now always headless — no second window |
| **After install, browser opens to "This site can't be reached" (ERR_CONNECTION_REFUSED)** | `Run.bat` opened the browser unconditionally — even when the Node server never bound the port — and the hidden server wrote no logs, so failures were invisible | `Run.bat` now starts the server with stdout/stderr captured to `logs\server.log`, polls a real HTTP response for up to 45s, opens the browser **only on success**, and on failure keeps the window open showing the last log lines + fixes. `Run-Console.bat` opens the browser only after the health check too |
| **Installer edition starts but creation never works / engine missing** | `installer/setup.iss` was stale: it shipped without `runner.py` (imported by `worker.py`), `selfies/`, `img/`, `Update.bat`, and referenced the Linux-only `virtual_display.py` that is not synced | `setup.iss` now includes every runtime file; `build_windows_dist.py` gained `validate_installer_sources()` which fails the build if any non-optional `Source:` is missing, and `sync_sources()` now recurses into `windows_dist/installer/` |
| **"Confirm you're human" (reCAPTCHA + selfie) is skipped entirely** | `core/captcha.py::ensure_meta_verified` matched bare `"meta.ai"` in `is_meta_ai_success`, so ANY meta.ai page counted as "verified" and the function returned before visiting the checkpoint. `core/lifecycle.py` also swallowed the call in a try/except | Restored the strict `meta_auto_ai` URL list (`meta.ai/?`, `/home`, `/chat`, `/prompt`) and made `ensure_meta_verified()` an unguarded call, so the checkpoint is always attempted |
| **Meta signup redirects to instagram.com** | The meta.ai funnel accepted any URL containing `"login"` (which matches `instagram.com/accounts/login`) as the Meta auth step, and raw `:has-text("Sign up")` selectors could match "Sign up with Instagram" | Funnel now rejects `instagram.com` URLs, bounces back to the Meta entry, and all "Sign up" selectors exclude Instagram/Facebook; a forced Meta bounce fails fast with a cooldown message |
| **Engine refuses to start on low-memory machines ("only N MB RAM available")** | Older builds used a RAM pre-flight/watchdog | Removed from the creator runtime. The requested Parallel value is used as entered; use Headless and the built-in low-memory Chromium flags on smaller machines. |

---

## 7. Verification Checklist

- [x] Node.js `core/licenseManager.js` HWID calculation matches authoritative formula.
- [x] Python `core/license_mgr.py` HWID calculation matches Node.js byte-for-byte (`HWID-61E8-9EED-55A0-CF9C`).
- [x] HMAC-SHA256 cache generation and tamper detection verified in both runtimes.
- [x] `/api/license/*` endpoints added to `server.js` (`/status`, `/activate`, `/validate`, `/deactivate`).
- [x] Server-side gate added to `/api/meta-insta/start` (blocks with HTTP 403 when unlicensed).
- [x] Python `worker.py` startup license gate verified (blocks execution when unlicensed).
- [x] Frontend Subscription modal, HWID copy, status badge, and activation flow integrated in `index.html`.
- [x] Portable Windows scripts (`Run.bat`, `Run-Console.bat`, `Stop.bat`) hardened and tested.
- [x] Inno Setup script `setup.iss` paths fixed and validated.
- [x] Automated packaging script `build_windows_dist.py` tested and generated shippable ZIP.
- [x] Headed browser windows open clean on Windows (no CfT version banner / restore bubble): `_NOVA_FLAGS` in `engine/eng_constants.py` contains `--test-type=gpu`, `--disable-infobars`, and `--hide-crash-restore-bubble`. A/B verified on Linux: crashed profile **with** the flag → no bubble, **without** → "Restore pages?" shown; a clean-marker rewrite also suppresses it independently.
- [x] No stray browser windows: the password-reset step (`instagram/password.py`) runs headless; the engine re-stamps a clean exit marker before **every** launch attempt (including fallbacks) so a crashed retry can't show the restore bubble.
- [x] Destructive reset is guarded: `POST /api/meta-insta/reset` requires `{"confirm":"CLEAR"}` and snapshots the account data into `backups/` first.
- [x] Dashboard: Meta/Instagram sidebar sheets, per-account Cookie column + JSON export, contextual Combo export (Meta = `email|password`; IG = `username|password|cookies`), Global Password at the top of the sidebar (click → modal → Save, persisted in `data/settings.json`), and Parallel up to 50 with no automatic RAM reduction.
- [x] Anti-detect parity with meta_auto_ai: per-profile device identity (`device_identity` seeded from the profile dir) shared by the UA and the injected fingerprint — verified in-browser (model / hardwareConcurrency / deviceMemory / maxTouchPoints agree and differ per profile); captcha waits env-tunable (30s cap / 15s bail); `mail.td` is the only mailbox provider and the legacy provider modules are removed; dashboard mail/captcha picks reach the worker.
- [x] 2026-09-24 release rebuilt: Portable 525,916,939 bytes (SHA-256 `b09c3b1d5ecb2caa7873691a40d21e79f5182e7f6823aacc61151ce3d613d3c0`) + Patch 57,645,803 bytes (SHA-256 `6f8c8d7d452229ade5407ca8ee465139a4522b64f1f603cf7a13fa207a39ac75`). Both archives passed `zipfile.testzip()` and exclude retired provider/RAM-guard files.
- [x] Windows launcher hardened: `Run.bat`/`Run-Console.bat` open the browser only after the dashboard answers HTTP, capture server logs to `logs\`, and show diagnostics on failure instead of a dead page.
- [x] Installer parity restored: `setup.iss` ships `runner.py`, `selfies/`, `img/`, `Update.bat`, and `Update.ps1`; build now validates every installer source and syncs `windows_dist/installer/`.
- [x] Meta and Instagram creation split into two independent workspaces (`view-meta-creator` / `view-ig-creator`) with their own controls, stats, results table, pagination and log; one shared accounts/SSE data layer; `mode` exposed on `/api/meta-insta/status`.
- [x] `new_username` wired end-to-end: dashboard field → `POST /api/meta-insta/start` → `META_NEW_USERNAME` env → `worker.py` → `MetaInstaRunner(new_username=…)`.
