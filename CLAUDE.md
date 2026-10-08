# meta_creator — quick reference
Architecture, invariants and gotchas live in `AGENTS.md` (already loaded). This file only adds commands and no-go zones.

**Purpose**: Meta signup + Instagram + Telegram task-bot automation, shipped as a protected Windows build.
**Stack**: Python 3.14 (`.venv`, playwright, telethon) · zero-dep Node server (`server.js` + `server/`) · vanilla dashboard (`public/`).

## Key dirs
- `core/`, `engine/`, `instagram/` — browser engine (Meta/IG); patch `core/` not `engine/eng_mix_captcha.py`
- `tg/`, `tg_*.py`, `mtproto_*.py`, `run_*_cycle.py` — Telegram bots, task/flow registries, cycle runners
- `server/` — Node routes + orchestrators · `public/js/nova-*.js` — dashboard panels
- `worker/license/` — Cloudflare license Worker · `windows_dist/` — installer/updater
- `tests/`, `test/` — unit tests (`tests/`) and live probes (`test/`, hit real services — don't run casually)

## Commands
- Setup: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Run dashboard: `./run.sh` (or `npm start`; port 3070, auto-moves if busy)
- Worker direct: `.venv/bin/python worker.py ...`
- Tests: `.venv/bin/python -m pytest tests/` · single: `.venv/bin/python -m pytest tests/test_meta_funnel.py::<name>`
- JS syntax check: `node --check server.js`
- Windows build: `python3 build_windows_dist.py` (`--no-protect` readable, `--bots taskly,paygo` subset)
- License Worker: `npm run worker:deploy` (deploy Worker BEFORE shipping a client)

## Never read / touch
- `node_modules/`, `.venv/`, `dist/`, `release/`, `engine/ms-playwright/`, `__pycache__/`
- User/runtime data: `data/`, `store.db`, `data.db`, `accounts.txt*`, `cookies/`, `profiles/`, `telegram_profiles/`, `backups/`, `logs/`, `screens/`, `selfies/`, `license_data/`
- `public/js/tailwind.js` (vendored), `extensions/Captcha/*` (minified bundle)
- Secrets: `.env`, `*.pem`, `worker/license/.signing_key.pem`
