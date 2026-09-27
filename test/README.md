# Meta Creator — Test & DevTools DOM Learning Suite

Ported from `meta_auto_ai/test/`. A dedicated testing framework to create
**isolated Meta accounts**, persist full browser session states, and reverse-engineer modern
**Instagram DOM patterns** (login, password sync/change, and 2FA) via Chrome DevTools Protocol (CDP).

> `tests/` (plural) holds the small unittest regression files.
> `test/` (singular, this dir) holds the live end-to-end + DevTools suite.
> `test/` is dev-only: `build_windows_dist.py` never syncs it and the ZIP
> walk prunes it, so nothing here ships to Windows.

---

## Directory Structure

```
test/
├── test_01_meta_only.py          # Step 1: Creates ONLY Meta account & saves complete session/credentials
├── test_02_ig_devtools_learn.py   # Step 2: Resumes session, interacts via DevTools/CDP, maps DOM patterns
├── test_03_tg_coupled_once.py     # Step 3: ONE coupled Meta -> TG -> IG cycle, timed (no retry burn)
├── devtools_client.py            # Inspector helper: captures screenshots, accessibility trees, & interactive DOM dumps
├── run_monitor.py                # Read-only run-health monitor (exit 0/2/3/4/5/6) — never kills a run
├── smoke_checks.py               # Offline regression suite (adapted — see below)
├── ac_dom_probe.py               # Diagnostic: direct-URL Accounts Center DOM probe
├── ac_reauth_probe.py            # Diagnostic: re-auth guard probe
├── ac_stay_probe.py              # Diagnostic: AC section-stay probe
├── ig_ac_wedge_check.py          # Repro: Contact-information overlay wedge
├── ig_add_email_probe.py         # Diagnostic: extra-email step probe
├── latest_credentials.json       # Auto-generated credentials and storage state paths
└── artifacts/                    # Auto-generated step screenshots, DOM JSON summaries, and learning reports
```

---

## Quick Start

### 1. Create Meta Account Only
Creates a Meta account without touching Instagram. Persists cookies, `localStorage`, email, and password.

```bash
.venv/bin/python test/test_01_meta_only.py [--mail mailtd] [--cdp 9222]
```

- When completed, the credentials and session file path are saved into `test/latest_credentials.json`.
- The browser stays open for DevTools inspection (or pass `--close` to shut down after saving).

### 2. DevTools Instagram DOM Learning & Inspection
Loads the persisted session and walks through Instagram login, password change, and 2FA step-by-step:

```bash
# Run all steps (Login -> Password Change -> 2FA):
.venv/bin/python test/test_02_ig_devtools_learn.py

# Or run specific stages:
.venv/bin/python test/test_02_ig_devtools_learn.py --step login
.venv/bin/python test/test_02_ig_devtools_learn.py --step password
.venv/bin/python test/test_02_ig_devtools_learn.py --step twofa
```

### 3. One coupled TG cycle (no retry burn)
Runs exactly one `run_tg_coupled_cycle` and exits — unlike
`worker.py --coupled --target 1`, it never mints a second Meta account:

```bash
.venv/bin/python test/test_03_tg_coupled_once.py [--tg-bot taskly|paygo|both] [--headless]
```

Note: TG accounts here are MTProto (`data/tg_sessions/*.session`, headless
Telethon) — there is no TG browser window to watch. The Meta/IG half runs
visible by default.

### 4. Attaching Real Chrome DevTools
The Meta/IG scripts launch Chromium with `--remote-debugging-port=9222`. You can inspect the live browser at any time:
1. Open Google Chrome on your desktop.
2. Navigate to `chrome://inspect`.
3. Under **Devices**, ensure `localhost:9222` is in **Configure...**.
4. Click **Inspect** next to the active Meta/Instagram tab.

See `docs/devtools-profile-testing.md` + `docs/devtools-inspection.md` for the
full MCP runbooks (pi-to-pi profile symlink, mobile emulation, tab model).

### 5. Viewing Artifacts & Learning Reports
All DOM summaries and screenshots are saved in `test/artifacts/`:
- Screenshots: `test/artifacts/*_<step>.png`
- Interactive Element Dumps: `test/artifacts/*_<step>_summary.json`
- Learning Report: `test/artifacts/learning_report.md`

### 6. Offline regression gate

```bash
.venv/bin/python test/smoke_checks.py --quick   # no browser/port checks
.venv/bin/python test/smoke_checks.py           # full (needs browsers + free ports 3099)
```

---

## Port notes (vs `meta_auto_ai/test/`)

- `test_01`, `test_02`, `test_03`, `devtools_client`, `run_monitor` and all
  `*_probe` / `*_check` files are byte-identical — every import
  (`worker.AISlotWorker`, `runner.MetaInstaRunner`, `engine.eng_constants`,
  `instagram.ac_*`, `pipelines.telegram.tg_worker`, `tg_bot`, `store`)
  resolves in this repo.
- `smoke_checks.py` is **adapted**: `server/lib/util.js` Engine checks
  (`_killTree` / `killOrphans` / exclusive lock / `engine_lock_test.js`) are
  replaced by an `engine_slots` shape check (single-file `server.js` with
  `engineSlots`/`setEngine`/`reapDeadEngine`); `memory_guard` is replaced by
  `no_mem_guard` (`mem_guard.py` is a forbidden file in the Windows build);
  `run.sh` checks match the PORT-env + auto-move-off-3070 launcher.
- **NOT ported** (no counterpart in this repo — do not copy back):
  `test_redroid.py`, `test/coinsta/`, `test/engine_lock_test.js`
  (nitro / Coinsta / `server/lib` Engine exist only in `meta_auto_ai`).
