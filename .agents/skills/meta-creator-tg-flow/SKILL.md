---
name: meta-creator-tg-flow
description: >-
  Add or change a Telegram task-bot integration in the meta_creator repo the DATA
  way: a new bot, a new task, or a different step sequence (some tasks skip the
  password change, some need only 2FA with no extra email, some add a cookie).
  Use when the user says a bot gained a new task, a task's steps changed, "learn
  this task", "add a bot/task/step", "run a cycle", "start N creators", or when a
  bot's live menu has drifted from the registry. Covers tg_tasks / tg_flows /
  tg_steps / tg/bots / ai_config + the NFKC and build-whitelist traps.
triggers:
  - "new task"
  - "add a task"
  - "add a bot"
  - "changed steps"
  - "learn this task"
  - "explore the bot"
  - "run a cycle"
  - "run creators"
  - "task menu changed"
---

# meta_creator — Telegram bot / task / step integration

Everything about a TG task bot is **data in a registry**, not code. Learn the bot
first, then edit ONE registry. This skill is the runbook.

Repo root: `~/Documents/my-projects/Antidetect-Tools/lin/meta_creator` (Linux dev).
Windows build target: `../../win/meta_creator` (produced by `build_windows_dist.py`).

---

## 0. The four registries (know these)

| File | Owns | Edit when |
|---|---|---|
| `tg_steps.py` | **STEPS** — every atom of work (`ig_join`, `2fa`, `password`, `extra_email`, `register`, `cookie_export`, `submit_cookie`, …) with label/side/needs/optional/doc | a genuinely NEW kind of step appears |
| `tg_flows.py` | **FLOWS** — ordered step lists per flow (`2fa`, `cookie`) + `resolve_steps(bot, task)` | a new flow, or the DEFAULT order changes |
| `tg_tasks.py` | **TASKS** per bot — `label`, `flow`, `price`, exact `path` (button chain), optional `steps`/`skip` | a task is added / removed / renamed / its path changes |
| `tg/bots/<id>.py` | bot descriptor — `kind`, `runner`, `gate`, `flows`, `tasks`, `creates_accounts`, `balance` | a NEW bot is added |

Supporting: `ai_config.TG_BOTS[<bot>]` (username, peer_id, `required_channels`,
`language`, `tasks`, `task_aliases`) and `public/js/nova-tg.js` `BOT_META` (the
dashboard dropdown).

---

## 1. ALWAYS learn the bot live first (MTProto, never guess)

```bash
cd <repo>
.venv/bin/python - <<'PY'
import asyncio, sys; sys.path.insert(0,'.')
from mtproto_bot import _api_credentials, session_file
from tg.common import last_message, click_text
def b(m): return [x.text for r in (getattr(m,'buttons',None) or []) for x in r]
def t(m): return (getattr(m,'text','') or '')
async def main():
    from telethon import TelegramClient
    aid,ah=_api_credentials()
    c=TelegramClient(session_file('tg_4'), aid, ah); await c.connect()
    ent=await c.get_entity('<bot_username>')
    await c.send_message(ent,'/start'); await asyncio.sleep(4)
    print(t(await last_message(c,ent))); print(b(await last_message(c,ent)))
    await c.disconnect()
asyncio.run(main())
PY
```

Then walk each menu level with `click_text(c, ent, "<button text>")`.

**TRAps — read these, they have each cost a real debug cycle:**

- **The LAST-message trap.** Some bots answer a task-select with **two** messages
  (creds first, then a prompt). `last_message()` shows only the second. Dump
  `get_messages(ent, limit=4)` and read oldest→newest before concluding anything.
  (This is exactly how FastPay2025_bot was wrongly called "payout-only".)
- **NFKC.** Menus often use Unicode math-bold (`𝗧𝗮𝘀𝗸`, `𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺`, `𝗖𝗼𝗻𝗳𝗶𝗿𝗺`).
  Plain `.lower()` matches NOTHING. All matching goes through
  `tg_tasks.normalize()`; never compare with bare `.lower()`.
- **Reply vs inline buttons.** Reply-keyboard buttons have `data=None` → send their
  text. Inline buttons have `data=<bytes>` → `.click()`. Creds usually arrive with
  an inline `Refresh` whose callback is a useful tell.

---

## 2. Add / change a TASK (the common case)

1. Learn the exact button path (section 1).
2. Edit `tg_tasks.TASKS[bot]`: add/rename the entry with `label`, `flow`,
   `price`, and the `path` (each level `{"all":[...], "none":[...]}`).
3. Add an alias in `ai_config.TG_BOTS[bot]["task_aliases"]` if the dashboard name
   differs from the button.
4. Add it to `public/js/nova-tg.js` `BOT_META[bot].tasks`.

**Different steps for this task** — no code change, use `skip` or an explicit list:

```python
INST_2FA: {"label": "📱 Create Inst (2FA)", "flow": "2fa",
           "skip": ["extra_email"],          # this task has no extra-email step
           "path": [ {"all": ["task"]}, {"all": ["create inst", "2fa"]} ]},
```

Verify:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from tg_flows import resolve_steps, validate_steps
print(resolve_steps('taskly','📱 Create Inst (2FA)'))
print(validate_steps('taskly','📱 Create Inst (2FA)') or 'OK')"
```

---

## 3. Add a STEP (new atom of work)

1. Add an entry to `tg_steps.STEPS` (label, `side`, `needs`, `optional`, `doc`).
2. Add it to the flow's `steps` list in `tg_flows.FLOWS`.
3. Implement the callable in the runner (`tg_coupled` for `2fa`,
   `run_cookie_cycle` for `cookie`) and gate the block with
   `if "<step>" in _flow_steps:`.
4. If a NEW root module is created, list it in `build_windows_dist.py`
   `SYNC_ROOT_FILES` — unlisted modules **silently do not ship** (invariant 4).

The runner pattern (already how `cookie` works — copy it):

```python
for step in steps_of(flow):
    fn = _STEPS.get(step)
    if fn is None: raise RuntimeError(f"flow '{flow}': step '{step}' has no implementation")
    fn(ctx)
```

---

## 4. Add a BOT

1. `ai_config.TG_BOTS[<id>]` — username, `peer_id`, `required_channels`,
   `language`, `tasks`, `task_aliases`.
2. `tg_tasks.TASKS[<id>]` — the tasks it offers + paths.
3. `tg/bots/<id>.py` — `register({...})` descriptor.
4. `public/js/nova-tg.js` `BOT_META[<id>]`.
5. `ai_config` gate: if the bot requires channels, use `gate: "channels_language"`
   and drive it with `tg.common.gate_bot` (join → Verify → language).
6. `ALL_BOTS` in `build_windows_dist.py` (so `--bots` can select it).

Assignment sanity check — never cross-bot remap: a task a bot does not offer must
**refuse**, never substitute (that burned money on wrong jobs).

---

## 5. Verify ONE cycle before running many

```bash
# one coupled 2fa cycle (Taskly/FastPay):
.venv/bin/python test/test_03_tg_coupled_once.py --tg-bot <bot> --task "<task>"
# one cookie cycle:
.venv/bin/python run_cookie_cycle.py --once     # see its --help for args
# read-only health monitor (never kills the run):
.venv/bin/python test/run_monitor.py --log logs/latest_telegram.log --stall 120
```

**Never kill a run to unstick it** — a kill drops Chromium's `sessionid` and every
later Accounts-Center step fails. Let it close cleanly. If you must kill, kill by
**PID** (`pkill -f pattern` self-matches your own shell).

## 6. Run N creators continuously

```bash
curl -s -X POST http://127.0.0.1:3070/api/tg/start -H 'Content-Type: application/json' \
  -d '{"concurrency":6,"target":0,"headless":true,"tg_task":"<task>","tg_bot":"<bot>","add_email":false}'
# stop:  curl -s -X POST http://127.0.0.1:3070/api/tg/stop -d '{}'
```

`target:0` = run until stopped. Watch the log via SSE at `/api/meta-insta/events`
or `tail -f logs/latest_telegram.log`. The engine emits `__EVENT__{json}` lines.

---

## 7. Build a subset for Windows

```bash
python build_windows_dist.py --bots fastpay        # ONLY fastpay ships
python build_windows_dist.py --bots taskly,paygo   # two bots
python build_windows_dist.py --no-protect          # readable dev build
```

`--bots` ships only `tg/bots/<id>.py`, **deletes excluded bots' `.py`/`.pyc`**, and
writes `tg/enabled_bots.json` (the dashboard + API honour it). Verified: it does
not check for other bots in required-in-zip, and the loader tolerates missing
modules.

---

## 8. Non-negotiable invariants (see AGENTS.md)

- **Never** raw `MtprotoTasklyBot`/Telethon-sync calls on the browser thread —
  unawaited coroutines fail silently (invariant 19). Bot commands run on the
  `MtprotoPooledBot` owner thread; balance probes in their own thread.
- Same browser session for Meta + IG; never open a second browser.
- `core/` wins over `engine/` for captcha.
- New root modules → `build_windows_dist.py` lists (invariant 4).
- Never ship user data (`data/tg_accounts.json`, `data/tg_sessions/`, …).
