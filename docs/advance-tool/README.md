# Advance Tool ("Meta AI to IG 2FA Pro") — decoded source skeleton (reference copy)

Decoded from `screens/Advance Tool Updated.exe` — 309 MB, PE32+ x86-64, **Nuitka onefile**
(Win target `--onefile`, `KAX` = payload stored uncompressed), Python **3.13**
(`python313.dll`).

The tool names itself `TOOL_NAME = "Meta AI to IG 2FA Pro"`, puts its state in
`%APPDATA%\MetaAIAutomation` (`license.key`, `.hwid.lock`, `saved_mailboxes.json`,
`updated_mail_keys.txt`), and advertises `https://t.me/@toolsadmin_A` /
WhatsApp `+8801722051341` on its activation screen.

## What is here

- `tools/unpack_nuitka_onefile.py` — extracts the onefile payload. Format (from
  `nuitka/build/static_src/OnefileBootstrap.c`): 3-byte header `"KA"` + `X` (raw) or `Y`
  (zstd), then repeated `[name (UTF-16LE, double-NUL terminated)] [uint64 size] [bytes]`,
  terminated by an empty name. No compression here, so nothing had to be brute forced.
- `tools/nuitka_blob.py` — decodes Nuitka's **constants blob** out of `main.dll`
  (tag spec: `nuitka/build/include/nuitka/constants_blob_spec.h`, readers:
  `static_src/HelpersConstantsBlob.c`). Finds the directory by validating the
  `name\0 + uint32 size + data` chain in `.rdata` → 1845 module blobs, then decodes each
  as `uint16 count` + that many tagged values. Emits a structure JSON.
- `tools/nuitka_report.py` — turns that JSON into the two reports below.
- `tools/crack_secrets.py` — unmasks the `*_ENC`/`*_MSK` byte pairs (see below).
- `app_skeleton.txt` — 60 app modules, 1271 code objects: every class and `def` with
  **exact signature and source line number**, grouped by scope.
- `app_strings.txt` — every string literal in those modules, per module.
  **Redacted**: live capability values (vault/license keys, telegram chat id, the two
  Google Apps Script ids, the temp-mail worker API key) are replaced with
  `<REDACTED:…>` markers; see the header comment and "Not copied here" below.
- `app_module_list.txt` — the app's own module list.

Reproduce (payload is not committed — it is 300 MB):

```bash
python3 tools/unpack_nuitka_onefile.py "Advance Tool Updated.exe" -o /tmp/advance-payload
python3 tools/nuitka_blob.py /tmp/advance-payload/main.dll --json /tmp/advance-structure.json
python3 tools/nuitka_report.py /tmp/advance-structure.json \
        --skeleton app_skeleton.txt --strings app_strings.txt
python3 tools/crack_secrets.py /tmp/advance-payload/main.dll <module> [<module> ...]
```

## How much source survives a Nuitka build

There is **no `.pyc` anywhere** — Nuitka compiles Python to C and the code lives in
`main.dll` (145 MB). `pyinstxtractor`/`uncompyle6` are useless here. What *is*
recoverable, and what the skeleton contains:

| Recovered | Detail |
|---|---|
| module tree | all 60 app modules + their original `*.py` paths |
| classes / functions | name, enclosing scope (qualname), **source line number** |
| signatures | full `co_varnames` + arg counts → pos-only / `*args` / kw-only / `**kwargs` |
| annotations | per-argument type dicts (e.g. `{'zoom_percent': int, 'return': bool}`) |
| literals | every string, tuple, dict, default, plus their order |
| imports | module-level import table and cross-module references |

**Not recoverable:** statements and expressions. `if`/`for`/call order are C now. Treat
this as an accurate map plus all the strings, not as runnable source.

## Recovered architecture

```
__main__             launcher — HWID, license, vault, Tk root, GUI wiring
config               master config: backend URLs, worker key, vault keys, mobile-device DB
pipeline_bridge      hook between the engines
master_suite         top-level Tk "suite" shell (hosts the engine tabs)
mail_service_app     standalone mail-service GUI
git_updater          self-update over git/HTTP

instagram_engine/    app_gui, automation_engine, browser_utils, config,
                     mail_services, security, ui_dialogs
meta_engine/         main, gui, browser_automation, browser_utils, email_services,
                     page_actions, extension_manager, fingerprint, licensing,
                     security_guard, updater
sell_engine/         main, config, core/{security,remote_db},
                     services/{browser_engine,mail_apis,telegram_helper},
                     ui/{main_gui,hwid_dialog,terminal}, utils/{file_utils,logger}
combined_engine/     combined_hook, combined_tab, sell_actions, tg_connector
core/                mail_key_manager, mailcow_dialog, mailcow_dynamic,
                     mailcow_imap, network_manager, remote_db, security
utils/               file_utils, logger, mailcow_imap
```

~33,500 source lines in total. Same market as this project: MTProto/Telethon bot
automation with the standard task-button vocabulary in `sell_engine/config.py`
(`📋 Tasks`, `▶️ Start`, `✅ Account registered`, `❌ Cancel`,
`🔥Create Inst (No mail) ($0.0280)`, `send_cookie_instead_of_2fa`) and MTProto
credential scraping regexes in `services/telegram_helper.py`
(`App api_id` / `App api_hash`, `First name|Login|Username|Password|Имя`).

Key spots worth reading, in `app_skeleton.txt`:

- `instagram_engine.automation_engine` — `InstagramAutomationWorker` (line 76) and its
  `_do_single_two_factor_setup` (537, ~500 lines long), `extract_totp_secret_key` (264,
  Windows-clipboard + JS-clipboard + DOM + strict Base32 fallbacks),
  `handle_content_unavailable_and_refresh` (404), `upload_profile_picture` (1065).
- `combined_engine.sell_actions` — `fast_backend_change_username` (48) renames via the
  **direct IG web API** (`/api/v1/web/accounts/edit/`), not the browser; compare
  `30 System/AI` notes on the same trick; `selenium_change_password` (213),
  `selenium_fast_manage_move_out_and_create_password` (422).
- `meta_engine.licensing` — HWID activation UI, legacy key calc, `check_user_access`
  against the Google Sheet backend.
- `sell_engine.core.remote_db` — `query_remote_database`, "device blocked" detection with
  a strict JSON-only check "to completely eliminate false-positive blocks caused by Google
  Cloud error HTML".

## Infrastructure recovered

- Backend is **Google Apps Script + Google Sheets**, not an API.
  `BACKEND_REMOTE_DB_URL` (licensing) and a second `/exec` webhook (logging) are both
  `script.google.com/macros/s/<REDACTED>/exec`. Both script ids are redacted here; they
  are capability URLs.
- Temp-mail / OTP layer: `guerrillamail.com`, `mail.tm`, `mail.gw`, `mail.td`, `mail.cx`,
  `maildrop.cc`, `tempmail.lol`, `tempmail.fish`, `smailpro.com`, `boomlify.com`,
  `app.sonjj.com`, plus a self-hosted **Cloudflare worker**
  `DEFAULT_WORKER_BASE_URL = https://temp-mail.mrakanto510.workers.dev`
  (its API key is a plaintext constant, redacted) and Mailcow IMAP support
  (`core/mailcow_*.py`).
- Fingerprinting: a 4-device mobile UA/webgl DB (Galaxy S24/S22, Pixel 8 Pro, OnePlus 11)
  in `instagram_engine/config.py`, plus `meta_engine/fingerprint.py`.

## Secrets: how they are hidden (and why that does not help)

Sensitive constants are not plaintext. They are stored as byte-literal pairs and rebuilt
at runtime by

```python
_dyn_decrypt_sec(enc_data, mask_data)   # instagram_engine/config.py, docstring:
                                        # "Dynamically reconstructs sensitive secrets in
                                        #  memory at runtime without plaintext strings
                                        #  in code/binary."
```

The scheme is a **per-byte cycled XOR** (`enc[i] ^ mask[i % 16]` → `bytes(...).decode('utf-8')`)
— the only constants the function body needs are `decode` and `('utf-8',)`. `tools/crack_secrets.py`
tries the plausible one-liners and prints whatever comes out readable. Pairs exist in
`config` (`_K_`, master vault key + `/exec` webhook), `sell_engine.config`
(`_BT_` bot token, `_CI_` chat id, `_DB_` webhook) and `instagram_engine.app_gui`
(second vault key).

**The masking does not actually hold.** Decoding the blob shows the vault keys, the chat id,
both Apps Script ids and the worker API key *also* shipped as ordinary plaintext `str`
constants in `core/security.py`, `instagram_engine/security.py`,
`sell_engine/core/security.py`, `instagram_engine/app_gui.py`, `meta_engine/licensing.py` and
`config.py` — the encryption only hides the *duplicate* copies. Lesson for our own
`ai_config`-style constants: a masked pair is safe only if the plaintext is deleted from every
module that ever had it (in this build, only the Telegram **bot token** was genuinely
pair-only). Those redactable values are the masking scheme's one real win, so the scheme is
still worth copying — plus a grep-style leak check before shipping.

## Not copied here (on purpose)

- Any live capability value, whether it was pair-masked or plaintext: the unmasked
  `_BT_` **Telegram bot token** (a third-party live credential), `_CI_` chat id,
  `_K_`/`_ADV` vault + license keys, the two Google Apps Script ids, and the temp-mail
  worker API key. `tools/crack_secrets.py` reproduces the masked ones locally from the exe
  you already have; `app_strings.txt` has the plaintext copies replaced with
  `<REDACTED:…>` markers. Using them against their bots/backend would be unauthorized
  access.
- The 300 MB extraction and the 30 MB `nuitka_structure.json` (regenerate with the commands
  above; intended to live in a scratch dir, not the repo).
- Their test-run artefacts that the exe happens to ship (dev leftovers, see below).

## Also shipped inside the exe (their own leftovers)

Not part of the program — baked in from the author's machine and readable straight out of
the payload: 10 × `instagram_engine/saved_cookies/*.json` with live IG `sessionid`s,
`updated_mail_keys.txt` (mailbox addresses + passwords), `single_outputs/{usernames,
passwords,cookies}.txt`, `accounts.txt` (`username|password|2fa_key|cookie`), and
`failed_accounts.txt` / `fail_meta/` failure logs. Not copied here; they are useful only as
evidence of scale (their failure strings match this project's Meta/IG checkpoints, e.g.
`Can't find account on Instagram`).
