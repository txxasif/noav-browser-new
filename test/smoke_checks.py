#!/usr/bin/env python3
"""smoke_checks.py — offline regression suite for the meta_creator fixes.

Ported from meta_auto_ai/test/smoke_checks.py. Runs every check that does NOT
need a real Meta/IG/TG account:
  * syntax/compile of Python, Node, shell
  * run_monitor exit codes (0 submitted / 2 stall / 4 dead-end / 5 vanished)
  * tg_fingerprint determinism + distinctness + LIVE injection
  * AC guards: _ac_pw_form_open, _dismiss_extra_protection_upsell
  * engine slots: setEngine/reapDeadEngine per-slot labelling (server.js)
  * run.sh: busy-port move-off, and SIGTERM teardown with no leftovers

Deliberate divergences from meta_auto_ai (do NOT "fix" these back):
  * NO server/lib/util.js Engine here — server.js is a single file with
    per-engine slots (engineSlots/setEngine/reapDeadEngine). The killTree /
    killOrphans / exclusive-lock / engine_lock_test.js checks do not apply.
  * NO mem_guard.py — it is a forbidden provider file in the Windows build
    (build_windows_dist.py purges it). The memory_guard check is replaced by
    a guard asserting it stays absent.
  * NO nitro/ / coinsta_* — TG Classic + Meta/IG only. test_redroid.py,
    test/coinsta/ and test/engine_lock_test.js were NOT ported.

Usage:
    .venv/bin/python test/smoke_checks.py            # all checks
    .venv/bin/python test/smoke_checks.py --quick    # skip browser/port checks
Exit code 0 = all pass, 1 = at least one failure.
"""
from __future__ import annotations

import builtins
import glob
import json
import os
import shutil
import signal
import subprocess
import symtable
import sys
import time

AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_DIR not in sys.path:
    sys.path.insert(0, AI_DIR)
try:
    from ai_config import run as _engine_run
    _engine_run._point_playwright_at_browsers()
except Exception:
    pass

PY = os.path.join(AI_DIR, ".venv", "bin", "python")
if not os.path.isfile(PY):
    PY = sys.executable
TMP = "/tmp/opencode/smoke_creator"
os.makedirs(TMP, exist_ok=True)

RESULTS: list[tuple[str, bool, str]] = []


def check(name):
    def deco(fn):
        def run():
            try:
                ok, detail = fn()
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            RESULTS.append((name, ok, detail))
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
        run.__name__ = name
        # Expose the raw checker too, so a single check can be called directly
        # (and unit-proven) without going through the RESULTS collector.
        run.checker = fn
        return run
    return deco


# --------------------------------------------------------------------------- #
@check("compile_python")
def _compile_python():
    files = (glob.glob("*.py") + glob.glob("core/*.py") + glob.glob("engine/*.py")
             + glob.glob("instagram/*.py") + glob.glob("pipelines/**/*.py", recursive=True)
             + glob.glob("test/*.py") + glob.glob("tests/*.py"))
    bad = []
    for f in sorted(set(files)):
        r = subprocess.run([PY, "-m", "py_compile", f], capture_output=True, text=True)
        if r.returncode:
            bad.append(f)
    return (not bad, "all compile" if not bad else f"failed: {bad}")


@check("undefined_names")
def _undefined_names():
    """No name may be used before it is bound in the module.

    Uses stdlib ``symtable`` (no extra dependency): for every scope, any
    symbol marked global-and-implicit that is not bound anywhere in the module
    is reported. Known pre-existing offenders are allow-listed by file so this
    gate never goes stale.
    """
    allow = {
        # Pre-existing at HEAD (vendored engine slice + lazy imports).
        # Listed so a NEW offender still fails the gate.
        "engine/eng_mix_audio.py": {"_WHISPER_LOCK"},
        "engine/eng_mix_ig.py": {"datetime", "HERE"},
        "engine/run.py": {"_SHARED_WHISPER_MODEL"},
    }
    files = (glob.glob("*.py") + glob.glob("core/*.py")
             + glob.glob("instagram/*.py") + glob.glob("pipelines/**/*.py", recursive=True)
             + glob.glob("test/*.py") + glob.glob("tests/*.py"))
    # Builtins are legitimately "global and never assigned"; so are the
    # conditional/lazy imports a module may reach at call time. Only names that
    # are referenced, never bound, and are not builtins are real bugs.
    known = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__",
                                   "__spec__", "__loader__", "__builtins__", "__debug__",
                                   "__path__", "__all__", "__annotations__"}
    bad = []
    for f in sorted(set(files)):
        try:
            src = open(f, encoding="utf-8").read()
            top = symtable.symtable(src, f, "exec")
        except (OSError, SyntaxError):
            continue
        defined = {s.get_name() for s in top.get_symbols()}

        def walk(tbl, seen):
            for sym in tbl.get_symbols():
                name = sym.get_name()
                if (sym.is_global() and not sym.is_assigned()
                        and name not in defined and name not in seen):
                    seen.add(name)
            for child in tbl.get_children():
                walk(child, seen)
        seen = set()
        walk(top, seen)
        for name in sorted(seen - known - allow.get(f, set())):
            bad.append(f"{f}:{name}")
    return (not bad, "no undefined names" if not bad else f"{len(bad)}: {bad[:8]}")


@check("headless_parity")
def _headless_parity():
    """Headless must run the SAME captcha solver as visible, or fail loudly.

    The Visual AI extension is a Manifest V3 extension: at runtime it exists
    only as a service worker. The headless shell cannot load it, so a headless
    run could silently continue on the weaker Audio STT solver.
    ``_verify_headless_parity`` now refuses to start in that case.

    This proves the discriminator still works AND that headless is currently on
    the good path: with channel="chromium" the worker MUST be alive.
    """
    try:
        from ai_config import run as _engine_run
        _engine_run._point_playwright_at_browsers()
    except Exception:
        pass
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return (True, f"skipped (no playwright: {exc})")
    ext = os.path.join(AI_DIR, "extensions", "Captcha")
    if not os.path.isdir(ext):
        return (True, "skipped (no extensions/Captcha dir)")

    def worker_alive(channel):
        d = os.path.join(TMP, f"parity_{channel or 'none'}")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        with sync_playwright() as pw:
            kw = dict(user_data_dir=d, headless=True,
                      args=["--no-sandbox", f"--load-extension={ext}",
                            f"--disable-extensions-except={ext}"])
            if channel:
                kw["channel"] = channel
            ctx = pw.chromium.launch_persistent_context(**kw)
            try:
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    pg.goto("about:blank", timeout=15000)
                except Exception:
                    pass
                end = time.time() + 12
                while time.time() < end:
                    try:
                        if ctx.service_workers:
                            return True
                    except Exception:
                        pass
                    time.sleep(0.5)
                return False
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass

    good = worker_alive("chromium")
    try:
        bad = worker_alive(None)
    except Exception:
        bad = False
    # The gate only means something if it DISCRIMINATES: new-headless must load
    # the extension and the plain headless shell must not.
    discriminating = good and not bad
    ok = discriminating and good
    return (ok, f"chromium_worker={good} shell_worker={bad} "
                f"headless_parity={'OK' if good else 'DEGRADED'}")


@check("syntax_node_shell")
def _syntax():
    bad = []
    # Single-file server (no server/ dir in meta_creator).
    r = subprocess.run(["node", "--check", "server.js"], capture_output=True, text=True)
    if r.returncode:
        bad.append("server.js")
    r = subprocess.run(["bash", "-n", "run.sh"], capture_output=True, text=True)
    if r.returncode:
        bad.append("run.sh")
    return (not bad, "ok" if not bad else f"failed: {bad}")


@check("monitor_exit_codes")
def _monitor_exit_codes():
    def run_case(events, expect, stall="30", pid=None):
        log = os.path.join(TMP, f"mon_{expect}.log")
        open(log, "w").close()
        cmd = [PY, os.path.join(AI_DIR, "test", "run_monitor.py"), "--log", log,
               "--stall", stall, "--heartbeat", "5"]
        if pid:
            cmd += ["--pid", str(pid)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(1.2)
        with open(log, "a") as fh:
            for ev in events:
                fh.write("__EVENT__" + json.dumps(ev) + "\n")
        try:
            rc = proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = -1
        return rc

    # case 5 (process vanished): watch a pid, then reap it so it truly vanishes
    # (a zombie still answers kill -0, so the harness MUST wait()).
    sleeper = subprocess.Popen(["sleep", "30"])
    log5 = os.path.join(TMP, "mon_5.log"); open(log5, "w").close()
    m5 = subprocess.Popen([PY, os.path.join(AI_DIR, "test", "run_monitor.py"),
                           "--log", log5, "--stall", "30", "--heartbeat", "5",
                           "--pid", str(sleeper.pid)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.2)
    sleeper.terminate(); sleeper.wait()
    try:
        rc5 = m5.wait(timeout=20)
    except subprocess.TimeoutExpired:
        m5.kill(); rc5 = -1
    got = {
        0: run_case([{"type": "slot_event", "slot_id": "x", "status": "submitted", "detail": "ok"}], 0),
        4: run_case([{"type": "log", "slot_id": "x", "message": "What's your mobile number? phone wall"}], 4),
        5: rc5,
    }
    # code 2 (stall) needs a very short stall
    log = os.path.join(TMP, "mon_2.log"); open(log, "w").close()
    proc = subprocess.Popen([PY, os.path.join(AI_DIR, "test", "run_monitor.py"),
                             "--log", log, "--stall", "3", "--heartbeat", "3"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        got[2] = proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill(); got[2] = -1
    ok = all(got[k] == k for k in got)
    return (ok, f"exit codes {got} (want 0/2/4/5)")


@check("tg_fingerprint_logic")
def _fingerprint_logic():
    sys.path.insert(0, AI_DIR)
    from tg_fingerprint import for_profile
    ids = [for_profile(f"tg_{i}") for i in range(1, 9)]
    distinct = len({(d["ua"], d["screen"], d["hw"], d["webgl_renderer"]) for d in ids})
    stable = for_profile("tg_1") == for_profile("tg_1")
    ok = stable and distinct == 8
    return (ok, f"stable={stable} distinct_identities={distinct}/8")


@check("tg_fingerprint_live")
def _fingerprint_live():
    # Self-sufficient: must not depend on an earlier check having inserted
    # AI_DIR into sys.path (reordering the list once broke this with
    # "No module named 'ai_config'").
    if AI_DIR not in sys.path:
        sys.path.insert(0, AI_DIR)
    from ai_config import run
    try:
        run._point_playwright_at_browsers()
    except Exception:
        pass
    from tg_fingerprint import for_profile, launch_kwargs, apply_to_context
    from playwright.sync_api import sync_playwright
    d = os.path.join(TMP, "proftest", "tg_1")
    shutil.rmtree(os.path.join(TMP, "proftest"), ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    ident = for_profile(d)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            d, headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"], **launch_kwargs(ident))
        apply_to_context(ctx, ident)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("about:blank")
        got = pg.evaluate("""() => { const c=document.createElement('canvas').getContext('webgl');
            const g=c&&c.getExtension('WEBGL_debug_renderer_info');
            return {platform:navigator.platform, hw:navigator.hardwareConcurrency, webdriver:navigator.webdriver,
                    ua:navigator.userAgent, renderer:g?c.getParameter(g.UNMASKED_RENDERER_WEBGL):null}; }""")
        ctx.close()
    ok = (got["platform"] == ident["platform"] and got["hw"] == ident["hw"]
          and got["webdriver"] is None and got["ua"] == ident["ua"]
          and got["renderer"] == ident["webgl_renderer"])
    return (ok, f"platform={got['platform']} hw={got['hw']} webdriver={got['webdriver']}")


@check("ac_guards")
def _ac_guards():
    sys.path.insert(0, AI_DIR)
    # The AC code is split: re-auth guards live in IgAcReauthMixin and the
    # navigation helpers in IgAcNavMixin. This check exercises both, so the
    # stub composes them the same way InstagramFlowMixin does.
    from instagram.ac_reauth import IgAcReauthMixin
    from instagram.ac_nav import IgAcNavMixin

    class FakeLoc:
        def __init__(self, n=0, vis=False):
            self.n, self.vis, self.clicked = n, vis, False
        def count(self):
            return self.n
        @property
        def first(self):
            return self
        def is_visible(self):
            return self.vis
        def click(self, **k):
            self.clicked = True

    class FakePage:
        def __init__(self, body, url, gs_vis=False, pw_count=0):
            self.body, self.url = body, url
            self.close = FakeLoc(1, True)
            self.gs = FakeLoc(1 if gs_vis else 0, gs_vis)
            self.pwc = pw_count
        def inner_text(self, *a):
            return self.body
        def get_by_text(self, *a, **k):
            return self.gs
        def locator(self, sel, *a, **k):
            if "Close" in sel:
                return self.close
            if "password" in sel:
                return FakeLoc(self.pwc)
            return self.gs
        def wait_for_timeout(self, *a):
            pass
        def keyboard(self):
            import types
            return types.SimpleNamespace(press=lambda *a, **k: None)

    class Stub(IgAcReauthMixin, IgAcNavMixin):
        def log(self, m):
            pass
        def _visible(self, p, role, name):
            return object() if (name == "Current password" and p.pwc >= 2) else None

    s = Stub()
    HEAD = "Set up extra protection for your Meta Account"
    # 2FA page must NOT be dismissed
    p1 = FakePage(HEAD, "https://accountscenter.instagram.com/password_and_security/two_factor/", gs_vis=True)
    r1 = s._dismiss_extra_protection_upsell(p1)
    # real upsell (X only, not two_factor) MUST be dismissed
    p2 = FakePage(HEAD, "https://accountscenter.instagram.com/password_and_security/")
    r2 = s._dismiss_extra_protection_upsell(p2)
    # form guard: 3 password inputs => change-password form
    f_open = s._ac_pw_form_open(FakePage("Current password New password", "x", pw_count=3))
    f_prompt = s._ac_pw_form_open(FakePage("Enter your password", "x", pw_count=1))
    ok = (r1 is False and p1.close.clicked is False
          and r2 is True and p2.close.clicked is True
          and f_open is True and f_prompt is False)
    return (ok, f"2fa_dismiss={r1} upsell_dismiss={r2} form_open={f_open} prompt={f_prompt}")


@check("engine_slots")
def _engine_slots():
    """Per-pipeline slots in the Node backend (AGENTS.md invariant 9).

    meta_creator has no server/lib/util.js Engine: server/context.js keeps
    ``engineSlots = { metainsta, tg }`` and ``setEngine()`` must be called at
    the server.js handler entry from the pathname, with ``reapDeadEngine()``
    self-healing a stale handle (exitCode !== null). This asserts the shape
    survives future edits (server.js + server/*.js are scanned together).
    """
    import glob as _glob
    try:
        files = [os.path.join(AI_DIR, "server.js")] + sorted(
            _glob.glob(os.path.join(AI_DIR, "server", "*.js")))
        src = ""
        for f in files:
            try:
                src += open(f, encoding="utf-8").read() + "\n"
            except OSError:
                pass
        if not src.strip():
            return (False, "no server JS found")
    except OSError as exc:
        return (False, f"cannot read server JS: {exc}")
    has_slots = "engineSlots" in src and "metainsta" in src
    has_set = "function setEngine" in src or "setEngine(" in src
    has_reap = "reapDeadEngine" in src and "exitCode" in src
    # setEngine must be driven by the request pathname at the handler entry,
    # not buried inside per-route blocks (the stale-slot labelling bug).
    entry_call = "setEngine(pathname" in src or "pathname.indexOf('/api/tg/')" in src
    ok = has_slots and has_set and has_reap and entry_call
    return (ok, f"slots={has_slots} setEngine={has_set} reap={has_reap} entry={entry_call}")


@check("submit_gates")
def _submit_gates():
    """AC section path aliases + bot-reply verdict (email/submit gating fixes)."""
    sys.path.insert(0, AI_DIR)
    # _ac_in_section lives on IgAcNavMixin after the AC split.
    from instagram.ac_nav import IgAcNavMixin as P
    from tg_bot import classify_report_reply as verdict

    aliases_ok = (
        P._ac_in_section("/account_overview/contact_points", "personal_info/contact_points")
        and P._ac_in_section("/youraccount/contact_points", "personal_info/contact_points")
        and P._ac_in_section("/personal_info/contact_points", "personal_info/contact_points")
        and P._ac_in_section("/account_overview/contact_points/", "personal_info/contact_points")
        and not P._ac_in_section("/account_overview", "personal_info/contact_points")
        and P._ac_in_section("/password_and_security/password/change", "password_and_security")
        and not P._ac_in_section("/account_overview/contact_points", "password_and_security")
    )
    # The real rejection text contains "registered" — must classify as rejected,
    # not accepted (the old false positive).
    reject_body = ("❌ Report rejected. Reason: Your report was rejected because the "
                   "Instagram account was registered without an email address.")
    verdicts_ok = (
        verdict(reject_body) == "rejected"
        and verdict("✅ Report has been received. Thank you!") == "accepted"
        and verdict("Report has been accepted") == "accepted"
        and verdict("") == "unknown"
    )
    ok = aliases_ok and verdicts_ok
    return (ok, f"aliases={aliases_ok} verdicts={verdicts_ok}")


@check("no_mem_guard")
def _no_mem_guard():
    """mem_guard.py must stay OUT of meta_creator (Windows-build invariant).

    build_windows_dist.py treats it as a forbidden provider file and fails
    the release if it leaks into the ZIP. The TG warm pool is count-capped
    (TG_WARM_MAX) instead; close_inspectors on the pooled bots is the
    shedding path.
    """
    forbidden = os.path.join(AI_DIR, "mem_guard.py")
    absent = not os.path.exists(forbidden)
    try:
        sys.path.insert(0, AI_DIR)
        import pipelines.telegram.tg_worker as tw
        has_shed = callable(getattr(tw, "close_inspectors", None))
    except Exception:
        has_shed = False
    ok = absent and has_shed
    return (ok, f"mem_guard_absent={absent} tg_worker.close_inspectors={has_shed}")


@check("runsh_port_move")
def _runsh_move():
    """run.sh moves off a busy default port instead of stacking a 2nd server.

    meta_creator's run.sh takes no port arg: with PORT unset it probes 3070
    (QEMU-forward collision) then 3080+. With PORT set it respects it. This
    asserts the move-off branch exists and is wired to server.js.
    """
    try:
        src = open(os.path.join(AI_DIR, "run.sh"), encoding="utf-8").read()
    except OSError as exc:
        return (False, f"cannot read run.sh: {exc}")
    move = "using $PORT" in src and "PORT=3080" in src
    already = "already running" in src
    launch = "exec node server.js" in src
    ok = move and already and launch
    return (ok, f"move_off={move} already_running={already} exec_server={launch}")


def _port_pid(port: str):
    """PID of the process listening on *port* (via ss), or None.

    run.sh ends in ``exec node server.js`` with a relative argv, so a
    ``pgrep -f meta_creator/server.js`` pattern never matches. Matching the
    listener by port is exact and immune to argv shape — and to other
    projects' servers running at the same time.
    """
    import re
    try:
        r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    for line in (r.stdout or "").splitlines():
        if f":{port} " not in line and not line.strip().endswith(f":{port}"):
            continue
        m = re.search(r"pid=(\d+)", line)
        if m:
            return int(m.group(1))
    return None


@check("runsh_teardown")
def _runsh_teardown():
    # pre-clean any stale listener on the test port so the check is deterministic
    old = _port_pid("3099")
    if old:
        subprocess.run(["kill", "-9", str(old)], capture_output=True)
    time.sleep(0.5)
    port = "3099"
    log = os.path.join(TMP, "runsh.log"); open(log, "w").close()
    env = dict(os.environ, NO_OPEN="1", PORT=port)
    proc = subprocess.Popen(["./run.sh"], stdout=open(log, "w"), stderr=subprocess.STDOUT, env=env)
    time.sleep(3.5)
    pid = _port_pid(port)
    listening = pid is not None
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
    gone = False
    for _ in range(16):  # server exits shortly after SIGTERM
        time.sleep(0.5)
        if _port_pid(port) is None:
            gone = True
            break
    listening_after = _port_pid(port) is not None
    ok = listening and gone and not listening_after
    return (ok, f"pid={pid} listening={listening} gone={gone} listening_after={listening_after}")


def main():
    quick = "--quick" in sys.argv
    checks = [_compile_python, _undefined_names, _headless_parity, _syntax, _monitor_exit_codes,
              _fingerprint_logic, _ac_guards,
              _engine_slots, _submit_gates,
              _no_mem_guard, _runsh_move, _runsh_teardown]
    if not quick:
        checks.insert(4, _fingerprint_live)
    print(f"=== smoke_checks ({'quick' if quick else 'full'}) ===", flush=True)
    for c in checks:
        c()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n=== {passed}/{len(RESULTS)} passed ===", flush=True)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL {name}: {detail}", flush=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
