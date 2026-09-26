<!-- BEGIN:framework-agent-rules -->
# ⚠️ meta_creator — Framework & Agent Guidelines

- **Stack**: Python 3.14 (`playwright`, `telethon`, `pyotp`) + zero-dependency Node server (`server.js`) + vanilla dashboard (`public/`).
- **Engine**: `MetaInstaRunner` in `core/` — Meta signup + Instagram login/link/join in the **same browser session**.
- **Product**: commercial Windows distribution (`build_windows_dist.py` → Portable + Patch ZIP), hardware-bound Cloudflare licensing.
- **Relationship to `meta_auto_ai`**: sibling project. The **Meta/IG half is byte-identical** (`core/captcha.py`, `instagram/helpers.py`, `login.py`, `join.py`, `password.py`, `engine/eng_mix_ig.py`). TG Classic was ported *from* `meta_auto_ai` and is **additive**.

# 🔒 Core Invariants

1. **Same session** — Meta and Instagram run in one browser context. The Instagram tab is `runner.insta_page`. Never open a second browser.

2. **`core/` wins over `engine/`** — `MetaInstaRunner` inherits `core.CaptchaMixin`, **not** `engine.EngineCaptchaMixin`. `engine/eng_mix_captcha.py` is a **dead duplicate** still carrying the old lying `[VERIFIED]` log — patch `core/captcha.py`.

3. **Module-level globals MUST precede the `__main__` call.** As a *script*, `main()` runs before any assignment below it; as an *import* the whole module body runs first. This asymmetry hid a `NameError` through several test rounds (`IG_WALL_SPLIT`). Every ported global belongs **above** `if __name__ == "__main__":`.

4. **Build whitelist** — `build_windows_dist.py` `SYNC_DIRS`/`SYNC_ROOT_FILES` are a **whitelist**. A new root module or package that is not listed **silently does not ship**, and `required_in_zip` cannot catch it (it only validates listed files). **Add new files there.**

5. **Exclusions must be path-specific, never basename.** A bare `"telegram.py"` entry in the zip loops dropped `core/telegram.py` (the `TgMixin`) — present in the tree, passing validation, absent from the zip. Use `file == "X" and root == ROOT_WIN`.

6. **Offline-first assets.** The Windows target may have no internet. Anything from a CDN renders broken there. Tailwind is **vendored** at `public/js/tailwind.js` with `corePlugins: { preflight: false }` **and no `forms` plugin** — both are required:
   - `preflight: false` — Preflight is a global reset that clobbers `styles.css`
   - no `forms` plugin — it restyles every `<input>` regardless of preflight (observed: Parallel/Target rendered as **empty white boxes**)
   Font Awesome is **still CDN** — vendor before shipping offline.

7. **Runtime deps must be installed into the shipped interpreter.** `ensure_python_deps()` in the build installs `telethon`/`pyaes`/`rsa` into `_internal/Lib/site-packages`. It only works because they are **pure Python**; a compiled dep would need Windows wheels (`pip download --platform win_amd64`).

8. **No `__pycache__` in the artifact.** Stale `.pyc` caused a false `NameError` during testing. The build excludes it; verify `0` entries in the zip.

9. **Per-engine slots, not one global.** `engineSlots = { metainsta, tg }` in `server.js`. `setEngine()` **must be called at the handler entry from the pathname**, not inside route blocks — a status read that ran before its own start-block set it reported whichever slot the *previous* request left active. `reapDeadEngine()` self-heals a stale handle (`exitCode !== null`).

10. **Meta/IG/TG are NOT resource-independent.** They share Chromium, the RAM budget, and `data/accounts.json`. The slots fix *labelling*, not contention. `meta_auto_ai` shares its `telegram` engine slot deliberately.

11. **TG pool enable/disable** — `tg_accounts.acquire()` skips `enabled is False`. `set_enabled()` **refuses while leased** (disabling mid-task would let a second worker lease the same profile and corrupt both sessions). `remove()` raises on an unknown id.

12. **Two-phase data parity** — write `data/accounts.json`, `data/accounts.csv`, `accounts.txt`.

13. **Never ship user data.** `data/tg_accounts.json`, `data/tg_mtproto.json`, `data/tg_sessions/`, `telegram_profiles/` must be **absent** from the ZIP.

14. **UI/UX directive** — `30 System/AI/UI_UX_DESIGN_SYSTEM.md` is authoritative. Applied: **4-tier dark depth** (`#090C10` shell → `#0D1117` canvas → `#12171F` panels → `#161B22` overlay — never flat black, never inverted), **`:focus-visible` 2px + 2px offset**, **`prefers-reduced-motion`**, **AA 4.5:1** text and **3:1** borders. Not yet done: emoji→SVG icons, the 3-tier token hierarchy, Radix primitives.

15. **Reuse the shared primitives.** The TG panel uses `btn btn-primary` / `btn btn-danger` (`fa-play`/`fa-stop`, **exactly one visible** — Start when idle, Stop when running), `panel-header` + `log-container`, and the `.switch` component. Do not invent per-panel button styles.

# 📚 Knowledge Base

Project memory lives in Obsidian at **`01 Projects/Meta Creator/`**:

| Note | Scope |
|---|---|
| `Meta Creator — Architecture, Windows Packaging & Security Specification.md` | Master blueprint, licensing, HWID, the TG Classic port, all fixes + verification status |
| `Windows Build & Release Playbook.md` | Build pipeline, the three shipping bugs, offline assets, release checklist |
| `Competitor Analysis — sell-toolnew.md` | Competitor teardown |

UI/UX governance: `30 System/AI/UI_UX_DESIGN_SYSTEM.md` + `10 Maps/UI & UX Design Intelligence MOC.md`.

# ⚠️ Known open issues

- **No `meta → ig → tg` cycle has ever completed** (Linux or Windows). TG-side code is verified by inspection + one script-run reaching `No Telegram profile is logged in`.
- **Teardown race** — `Page.wait_for_timeout: Target page, context or browser has been closed` (8×) is a *secondary* error from cleanup closing the browser mid-poll; it overwrites the true error and corrupts failure data. **Fix this first.**
- **88% phone wall** — 235/267 STRICT-stops are `Mobile number required`. Untouched by any TG work. If the log shows `[⏱️] Meta provisioned — accountId=…` and *then* the wall, the race hypothesis is disproven; the fix is a non-temp mail domain.
- `warm_pool.py` is the highest-risk import (mutable browser state — see `meta_auto_ai` invariant 36).
<!-- END:framework-agent-rules -->
