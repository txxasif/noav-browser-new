# PayGo IG Pool Drain & Auto-Mining Architecture

## 1. Overview
The **PayGo IG Pool Drain** pipeline drains pre-created Instagram accounts from `data/accounts.json` / `store.db` directly into **PayGoBot** without launching Chromium or completing manual browser onboarding.

Unlike standard browser-based task cycles that require 60–90 seconds per account, the Pool Drain cycle operates entirely over **MTProto** and **direct Instagram Web API calls**, achieving sub-6-second cycle times.

---

## 2. Key Components

### 2.1 Fast Direct Web API Renamer
* **Implementation:** `change_ig_username_fast(cookie_str, target_username, ua=None)` in `run_cookie_cycle.py`.
* **Endpoint:** `POST https://www.instagram.com/api/v1/web/accounts/edit/`
* **Mechanism:**
  - Extracts `csrftoken` and `sessionid` from the claimed pool account's cookie string.
  - Sends a direct HTTP URL-encoded request with `username: target_username`.
  - Instagram instantly validates availability and saves the new username in **~0.4s** (`{"status": "ok"}`).
  - If an account is checkpointed or suspended, it is flagged as dead in `store.db` and the runner smoothly claims the next candidate.

### 2.2 Pool Drain Runner (`_run_pool_drain_cycle`)
* **File:** `run_cookie_cycle.py`
* **Workflow:**
  1. Checks for available IG Creator accounts in `store.count_ig_creator_accounts()`.
  2. Leases a Telegram MTProto profile from `tg_manager`.
  3. Enforces profile pacing (at least 8.0s between task starts on the same account).
  4. Navigates to PayGo's task menu (`bot.choose_task("📱 Create Inst (Cookies)")`).
  5. Presses `▶️ Start` and parses the bot's required `login` username.
  6. Claims an account from the pool and renames it via `change_ig_username_fast` to match PayGo's target `login`.
  7. Submits the updated cookie string to PayGo (`bot.submit_cookie()`).
  8. Confirms registration (`bot.mark_registered()`).
  9. Consumes and permanently deletes the account from `store.db` to prevent double-spending.
  10. Emits `account_submitted` event (earning +$0.02) and releases the Telegram profile.

### 2.3 Auto-Mining & Preemption Orchestrator
* **File:** `server/paygo-orchestrator.js`
* **Background Loop:** Runs every 10 seconds in the Node server.
* **Zero-Contention Clock Tracking:**
  - When other bots (e.g. Taskly or FastPay) are actively running, the orchestrator **never touches MTProto sessions or spawns Python** to avoid SQLite file locking.
  - It tracks seconds remaining until the top of the hour (`:00`) using JavaScript system clock (`waitSec`).
* **Preemption:**
  - When `waitSec <= 10`, it snapshots the running bot configuration (`savedJob`).
  - Gracefully stops the active bot and waits 2.5s for session cleanup.
  - Launches PayGo Pool Drain at full parallel concurrency to capture hourly stock.
* **Auto-Restoration:**
  - When PayGo runs out of stock (`0/5700` or `"This hour's limit is reached"`), the worker halts.
  - The orchestrator detects loop completion, waits 3 seconds, and automatically relaunches the previous bot (`savedJob`).

### 2.4 Ultra-Light MTProto Probe
* **File:** `tg_paygo_probe.py`
* **Behavior:**
  - Runs with `timeout=0.0` non-blocking lease acquisition.
  - If any worker is using profiles, the probe safely aborts immediately.
  - When idle, reads the `Available this hour: X/5700` counter and reports stock and wait time in milliseconds.

---

## 3. Concurrency & Protection Safeguards
1. **Startup Stagger:** Coupled slots stagger launch by `1.5s/slot` (`worker.py`), preventing concurrent API spikes to Telegram.
2. **Profile Pacing:** Telegram profiles enforce an 8.0-second cooldown between task creations.
3. **Hourly Limit Detection:** `choose_task` and `start_task` in `mtproto_bot.py` parse limit notices (`"limit is reached"`, `"available this hour: 0/"`) and immediately halt all slots via `_stop.set()`.
4. **Code Protection:** Compiles to sourceless `.pyc` (Python 3.14) and obfuscates backend and frontend JavaScript.
