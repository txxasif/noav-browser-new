# TG Bot — FastPay 2025 (Instagram 2FA)

> Also kept as a knowledge-base note in Obsidian:
> `01 Projects/Meta Creator/TG Tasks/TG Bot — FastPay 2025 (Instagram 2FA).md`.
> This is the repo-side copy (relative paths, no wikilinks).

> **It IS a task issuer.** Selecting its task sends **`Username` + `Password`**,
> then asks for the account's **2FA key** and pays **৳3.0 ≈ $0.024** on Confirm.
> It runs the **same create flow as Taskly's `Create Inst (2FA)`**.
> Verified live end-to-end **2026-09-28**.

- **Username:** `@FastPay2025_bot` (peer id `8628150338`)
- **Kind:** `mtproto+web` · `creates_accounts: True` · `balance: True`
- **Task:** `Instagram 2FA | ৳3.0 | $0.024`
- **Flow:** `2fa` → runner `tg_coupled`

> **Correction.** First documented as *payout-only ("creates nothing")* — wrong,
> an artefact of reading **only the newest message**. On task select the bot
> sends **two** messages; the creds one comes first.

---

## 1. Gate (once per Telegram account)

`/start` → join `t.me/FastPyOfficial` + `t.me/FastPayOfficial2026` → `Verify` →
select **English**. Idempotent via `tg.common.gate_bot`.

```bash
.venv/bin/python tg_join_bot.py --bot FastPay2025_bot            # bare /start
.venv/bin/python tg_join_bot.py --bot FastPay2025_bot --gate     # full gate
```

## 2. Menu path

```
𝗧𝗮𝘀𝗸  →  𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺  →  Instagram 2FA | ৳3.0 | $0.024
```

`𝗙𝗮𝗰𝗲𝗯𝗼𝗼𝗸` category is empty; `𝗜 𝗮𝗺 𝗡𝗲𝘄` is a YouTube guide on creating IG accounts.

## 3. Task contract (two messages on select)

```
BOT:  📋 Task: 𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺 2𝗙𝗔
      👤 Username: `virginia_howardzau_47203`
      🔒 Password: `FASTPAY%27`
      [𝗥𝗲𝗳𝗿𝗲𝘀𝗵]                     ← rerolls the pair (callback lt_refresh_fake_data)

BOT:  👇 Please send the 2FA Key below: 🔑        [Cancel ❌]
```

| Step | Bot says | We do |
|---|---|---|
| 1 | *"Please send the 2FA Key below:"* | send the account's base32 `twofa_secret` |
| 2 | *"2FA Code: NNNNNN"* | bot generates the TOTP itself |
| 3 | *"Please select an option below:"* | press **`Confirm`** |
| 4 | *"🎉 Task Completed Successfully!"* (`Pending Balance: ৳3.0`) | record Submitted |

**No first name** — `mtproto_bot._random_first_name()` supplies one.

## 4. Flow (shared with Taskly 2FA)

`tg_flows.FLOWS["2fa"]` → `["email_link", "2fa", "password", "extra_email", "register"]`,
runner `tg_coupled`:

1. **Meta** signup.
2. **TG** — lease → gate → `choose_task` → bot sends **Username/Password**.
3. **IG (same browser)** — login → create Meta card → join with the bot username → follow ~2.
4. **Accounts Center** — 2FA setup → `submit_2fa_key` → code → `Confirm`.
5. **Password** — change to the bot's `Password`.
6. **Extra email** — if the toggle is on (like Taskly).
7. **Register** — `mark_registered()` gate; never records a false Submitted.

## 5. Code touchpoints

| File | Role |
|---|---|
| `tg_tasks.py` | `TASKS["fastpay"][fastpay_ig_2fa]` — flow **`2fa`**, price `0.024`, path `Task→Instagram→Instagram 2FA`; `normalize()` = **NFKC** |
| `tg_flows.py` | FastPay reuses the `2fa` flow |
| `ai_config.py` | `TG_BOTS["fastpay"]` |
| `tg/bots/fastpay.py` | `kind: mtproto+web`, `creates_accounts: True` |
| `mtproto_bot.py` | `_start_task_fastpay()`, `_parse_creds` accepts `Username:`, `_random_first_name()`, NFKC matching |
| `tg_fastpay.py` | standalone payout CLI |
| `server.js` | `tg_bot` accepts `fastpay`; `tg_submitted_fastpay` KPI |
| `public/js/nova-tg.js` | FastPay page = TG Classic create page (`data-bot="fastpay"`) |

## 6. Dashboard

Sidebar **Telegram → FastPay Bot** opens the **TG Classic create page** scoped to
FastPay (`data-view="view-tg-classic" data-bot="fastpay"`) — same KPIs and
Creator Settings as Taskly/PayGo. The standalone payout page
(`nova-fastpay.js`) is no longer loaded (file kept); payout is the
`tg_fastpay.py` CLI.

## 7. Build & shipping

- Selectable with `--bots taskly,paygo,fastpay` (`ALL_BOTS`); excluded bots'
  `.py`/`.pyc` are deleted and `tg/enabled_bots.json` hides the rest.
- `tg_fastpay.py`, `tg_join_bot.py`, `tg_manager_cli.py`, `tg/` must stay in
  `build_windows_dist.py` lists (invariant 4).

## 8. Open issues / notes

- **The "payout-only" trap:** reading only the newest message misses the creds.
- **NFKC is mandatory** — `𝗧𝗮𝘀𝗸`/`𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺`/`𝗖𝗼𝗻𝗳𝗶𝗿𝗺`.
- **Protected (Windows) build not smoke-tested** for the FastPay create path.
