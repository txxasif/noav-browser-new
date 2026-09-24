#!/usr/bin/env python3
"""Measure local Chromium startup cost for isolated vs shared contexts.

This is a development-only benchmark. It never contacts Meta, Google, CAPTCHA,
or any account service. Run it on the target Windows machine before choosing a
10–20 slot deployment target.

Examples:
    python benchmarks/browser_context_benchmark.py --counts 1,5,10
    python benchmarks/browser_context_benchmark.py --counts 10,20 --headed
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # optional development dependency
    psutil = None


def _rss_mb() -> float | None:
    if psutil is None:
        return None
    try:
        process = psutil.Process()
        processes = [process]
        processes.extend(process.children(recursive=True))
        total = 0
        for item in processes:
            try:
                total += item.memory_info().rss
            except Exception:
                pass
        return round(total / (1024 * 1024), 1)
    except Exception:
        return None


def _counts(value: str) -> list[int]:
    result: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            result.append(max(1, int(part)))
    if not result:
        raise argparse.ArgumentTypeError("at least one context count is required")
    return result


def _launch_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    launch_args = [
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-accelerated-2d-canvas",
        "--disable-background-networking",
        "--renderer-process-limit=3",
    ]
    kwargs: dict[str, Any] = {
        "headless": not args.headed,
        "args": launch_args,
    }
    if args.executable:
        kwargs["executable_path"] = args.executable
    return kwargs


def _run_one(playwright: Any, count: int, mode: str, args: argparse.Namespace) -> dict[str, Any]:
    root = tempfile.mkdtemp(prefix=f"meta-creator-bench-{mode}-")
    contexts = []
    browser = None
    started = time.perf_counter()
    try:
        if mode == "shared":
            browser = playwright.chromium.launch(**_launch_kwargs(args))
            for _ in range(count):
                contexts.append(browser.new_context())
        else:
            for index in range(count):
                user_data_dir = os.path.join(root, f"profile-{index}")
                contexts.append(
                    playwright.chromium.launch_persistent_context(
                        user_data_dir,
                        **_launch_kwargs(args),
                    )
                )
        launch_ms = round((time.perf_counter() - started) * 1000, 1)
        for context in contexts:
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            page.goto("data:text/html,<title>Meta Creator benchmark</title><body>ok</body>")
        ready_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "mode": mode,
            "contexts": count,
            "launch_ms": launch_ms,
            "ready_ms": ready_ms,
            "rss_mb": _rss_mb(),
        }
    finally:
        for context in reversed(contexts):
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=_counts, default=[1, 5, 10])
    parser.add_argument("--modes", choices=("separate", "shared", "both"), default="both")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--executable", default="")
    args = parser.parse_args()
    counts = args.counts if isinstance(args.counts, list) else _counts(str(args.counts))
    modes = ("separate", "shared") if args.modes == "both" else (args.modes,)

    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as playwright:
        for count in counts:
            for mode in modes:
                results.append(_run_one(playwright, count, mode, args))

    print(json.dumps({
        "python": sys.version,
        "platform": sys.platform,
        "psutil_available": psutil is not None,
        "results": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
