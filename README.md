# noav-browser-new

> Meta Creator — dedicated anti-detect creation engine and Windows distribution tooling.

A high-performance, standalone tool focused purely on **Meta Account Creation & Verification**. Built on top of the battle-tested anti-detect engine with offline reCAPTCHA solving, biometric selfie checkpoint bypass, temporary mailbox dispatch, and a reactive dashboard with real-time slot monitoring, pagination, and CSV export.

---

## ⚡ Features

- **Same Anti-Detect Core**: Samsung Galaxy S24 Ultra Android mobile profile emulation, custom fingerprint spoofing, and realistic interaction speeds.
- **Two Independent Workspaces**: **Meta Creator** (Meta-only accounts) and **Instagram Creator** (Meta account → Instagram join) are separate pages, each with its own controls, stats, results table, pagination and live engine log.
- **Fast Mailbox Dispatch**: Browser-backed `mail.td` inbox with REST API code polling.
- **Offline & Autonomous Captchas**:
  - Offline Faster-Whisper / Vosk Audio STT reCAPTCHA solver.
  - Headless Visual AI extension support via Chromium.
  - Biometric selfie upload piercing shadow DOM with CDP fallback.
- **Multi-Worker Concurrency**:
  - Run 1 to 10 concurrent browser slots in a continuous creation loop.
  - Headless or visible desktop mode.
  - Target account batches (e.g. create 20 accounts and stop, or infinite loop).
- **Full UI Pagination & Controls**:
  - Page size dropdown (10, 25, 50, 100 accounts per page).
  - Instant live search & multi-column sorting (Name, Email, Password, Username, DOB, Date).
  - One-click copy for credentials, show/hide passwords.
  - Bulk select & bulk delete.
  - Direct CSV Export (`/api/export`).
- **Data Parity & Reliability**:
  - SQLite WAL mode database (`data/store.db`).
  - Automatic synchronization with `data/accounts.json`, `data/accounts.csv`, and `accounts.txt`.
  - Process group isolation (prevents zombie or orphaned Chromium processes).
  - No automatic RAM-guard clamp: the selected Parallel value is used as entered (up to the UI/CLI limit of 50).

---

## 🚀 Quick Start

### 1. Launch Dashboard
```bash
cd /home/asif/Documents/my-projects/Antidetect-Tools/lin/meta_creator
./run.sh
```
Open the URL printed by `./run.sh` (normally **http://localhost:3070**; if that port is occupied by the Windows VM/QEMU forward, the launcher automatically selects the next free port).

### 2. Run via CLI (Headless or Scripted)
```bash
# Run 2 concurrent slots in headless mode
.venv/bin/python worker.py --concurrency 2 --headless

# Create exactly 10 accounts and exit
.venv/bin/python worker.py --concurrency 3 --target 10 --headless

# Run with visible browser windows and 5s delay
.venv/bin/python worker.py --concurrency 1 --delay 5
```

---

## 📁 Directory Structure

```
meta_creator/
├── engine/              # Anti-detect engine, launch parameters, captcha, models
├── core/                # Lifecycle, signup wizard, mail.td mailbox mixin, base
├── extensions/          # Visual AI Captcha browser extension
├── public/              # Web dashboard frontend
│   ├── index.html       # Sidebar + Meta/Instagram workspace mounts, shared modals
│   ├── js/
│   │   ├── nova-core.js        # Shared helpers, theme, nav, modals, toasts
│   │   ├── nova-license.js     # Activation flow + license gate
│   │   └── nova-meta-insta.js  # Workspace factory (Meta + Instagram)
│   └── styles.css       # Clean dark/light theme styling
├── data/
│   ├── store.db         # High-performance SQLite WAL database
│   ├── accounts.json    # JSON accounts sheet
│   └── accounts.csv     # Exportable CSV file
├── server.js            # Zero-dependency Node.js server (Port 3070)
├── worker.py            # Multi-worker loop engine (CLI / Background)
├── ai_config.py         # App configuration & URL registry
├── db.py & store.py     # Thread-safe SQLite store with auto-sync
├── engine/              # Low-memory Chromium launch/resource tuning
├── selfie.png           # Biometric verification selfie
└── run.sh / start.sh    # Launcher scripts
```

---

## 🌐 API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/status` | `GET` | Health check, engine loop status, total count |
| `/api/accounts` | `GET` | Return all created accounts as JSON |
| `/api/export` | `GET` | Download `meta_accounts.csv` |
| `/api/events` | `GET` | Server-Sent Events (SSE) live updates |
| `/api/loop/start` | `POST` | Start worker loop (`concurrency`, `headless`, `target`, `delay`) |
| `/api/loop/stop` | `POST` | Stop active worker loop |
| `/api/delete` | `POST` | Delete single account by ID |
| `/api/accounts/delete_many` | `POST` | Bulk delete accounts |
| `/api/accounts/reset` | `POST` | Reset accounts database |

---

## 🪟 Windows checkout and Git push

The project can be maintained from Windows PowerShell. Use the bundled Git distribution or Git for Windows; do not use the `echo ... >>` form from a POSIX shell when the line begins with `#`, because PowerShell treats `#` as a comment.

```powershell
Set-Location C:\path\to\meta_creator

git init
git add .
git status --short
git config user.name "txxasif"
git config user.email "txxasif@users.noreply.github.com"
git commit -m "Initial commit"
git branch -M main

# Use this when origin already exists; `git remote add` fails in that case.
git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin git@github.com:dxh-amj/nova_browser_new.git
} else {
    git remote set-url origin git@github.com:dxh-amj/nova_browser_new.git
}

ssh -T git@github.com
git push -u origin main
```

If `git push` reports `Permission denied (publickey)`, sign in to GitHub, add the public key from `%USERPROFILE%\.ssh\id_ed25519.pub` under **Settings → SSH and GPG keys**, and run `ssh -T git@github.com` again. If the remote already has commits, use `git pull --rebase origin main` before pushing; do not use `--force` unless the remote history is intentionally being replaced.

Runtime accounts, cookies, browser profiles, license data, databases, screenshots, and local build outputs are excluded by `.gitignore`. Keep those files out of any GitHub commit.
