#!/usr/bin/env python3
"""Multi-Insta Engine — Extracted from multi_insta.exe.

Pure Selenium engine with multi_insta.exe's exact profile, cookie injection,
and DOM JavaScript follow execution. Supports testing directly on account cookies
and updating the database (status='Created', followed=N).
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import db
import store

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    print("[ERROR] selenium is required. Install via: pip install selenium")
    sys.exit(1)


def _extract_session_id(cookie_string: str) -> Optional[str]:
    """Extract clean sessionid from a cookie header or bare value."""
    raw = str(cookie_string or "").strip()
    if not raw:
        return None
    if "sessionid=" in raw:
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith("sessionid="):
                return part.split("sessionid=", 1)[1].strip()
    return raw if len(raw) > 10 else None


def _create_driver(headless: bool = False, w: int = 550, h: int = 750):
    """Launch Chrome or Edge matching multi_insta.exe's exact CLI flags."""
    is_windows = platform.system().lower() == "windows"
    driver = None

    # On Windows, multi_insta.exe prefers Edge if available
    if is_windows:
        try:
            from selenium.webdriver.edge.options import Options as EdgeOptions
            options = EdgeOptions()
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            if headless:
                options.add_argument("--headless=new")
            driver = webdriver.Edge(options=options)
        except Exception:
            driver = None

    if driver is None:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if headless:
            options.add_argument("--headless=new")
        driver = webdriver.Chrome(options=options)

    try:
        driver.set_window_size(w, h)
    except Exception:
        pass
    return driver


def run_multi_insta_follow(
    cookie_string: str,
    target_follows: int = 5,
    target_url: str = "https://accountscenter.instagram.com/profiles/",
    headless: bool = False,
    account_id: Optional[str] = None,
    log_fn: Optional[callable] = None,
) -> Tuple[int, str]:
    """Run the exact multi_insta.exe follow loop on an account's session.

    Returns (followed_count, updated_cookie_str).
    If account_id is supplied, updates database record with followed count and cookies.
    """
    def log(msg: str):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    session_id = _extract_session_id(cookie_string)
    if not session_id:
        log("[ERROR] Invalid cookie format: no sessionid found!")
        return 0, cookie_string

    driver = None
    followed_count = 0
    updated_cookie_str = cookie_string

    try:
        log(f"[INFO] Launching multi_insta engine (headless={headless}, target={target_follows})...")
        driver = _create_driver(headless=headless, w=470, h=520)

        # 1. Open root domain to allow cookie domain attachment
        driver.get("https://www.instagram.com/")
        time.sleep(0.5)

        # 2. Inject ONLY sessionid (multi_insta parity — fresh CSRF issued on load)
        cookie = {
            "name": "sessionid",
            "value": session_id,
            "domain": ".instagram.com",
            "path": "/",
        }
        driver.add_cookie(cookie)

        # 3. Open explore/people
        log("[INFO] Navigating to https://www.instagram.com/explore/people/...")
        driver.get("https://www.instagram.com/explore/people/")

        log("[INFO] Waiting for follow buttons to load...")
        xpath = "//button[descendant::div[text()='Follow' or text()='Follow Back'] or text()='Follow' or text()='Follow Back']"
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except Exception:
            pass

        log(f"[INFO] Following up to {target_follows} users securely...")
        attempts = 0
        max_attempts = max(target_follows * 5, 25)

        blocked = False
        while followed_count < target_follows and attempts < max_attempts and not blocked:
            attempts += 1
            buttons = driver.find_elements(By.XPATH, xpath)
            if not buttons:
                buttons = driver.find_elements(By.TAG_NAME, "button")

            for btn in buttons:
                if followed_count >= target_follows:
                    break
                try:
                    if btn.get_attribute("data-followed"):
                        continue
                    btn_text = btn.text.strip().lower()
                    if "follow" in btn_text and "following" not in btn_text and "requested" not in btn_text:
                        driver.execute_script("arguments[0].setAttribute('data-followed', '1'); arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", btn)
                        time.sleep(0.3)
                        body_text = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
                        if "failed to load" in body_text:
                            log(f"[❌] 'Failed to Load' toast detected after {followed_count} follows! Account is blocked.")
                            blocked = True
                            break
                        if "try again later" in body_text or "action blocked" in body_text:
                            log(f"[❌] Action Block detected after {followed_count} follows!")
                            blocked = True
                            break
                        followed_count += 1
                        log(f"[INFO] Followed user {followed_count}/{target_follows} successfully")
                        time.sleep(0.3)
                except Exception:
                    pass

            if followed_count < target_follows:
                try:
                    driver.execute_script("window.scrollBy(0, 350);")
                except Exception:
                    pass
                time.sleep(0.4)

        log(f"[INFO] Follow loop complete: {followed_count}/{target_follows}. Navigating to target URL: {target_url}")
        driver.get(target_url)
        time.sleep(1.0)

        # Collect fresh cookies
        try:
            cookies = driver.get_cookies()
            if cookies:
                updated_cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name"))
        except Exception:
            pass

        log(f"[SUCCESS] Multi-Insta engine completed {followed_count} follows!")

    except Exception as e:
        log(f"[ERROR] Engine exception: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    # Store updates in database if account_id is provided
    if account_id and followed_count > 0:
        try:
            updates = {
                "followed": followed_count,
                "cookies": updated_cookie_str,
                "status": "Created",
            }
            store.update_record(account_id, updates)
            log(f"[💾] Account {account_id} updated in database: followed={followed_count}, status=Created")
        except Exception as err:
            log(f"[⚠️] Database update error: {err}")

    return followed_count, updated_cookie_str


def main():
    parser = argparse.ArgumentParser(description="Multi-Insta Follow Engine Pipeline")
    parser.add_argument("--account", help="Account ID or Username to follow and update in DB")
    parser.add_argument("--cookie", help="Raw cookie string or sessionid value")
    parser.add_argument("--pool", type=int, help="Run on N accounts from DB with followed < 5")
    parser.add_argument("--target", type=int, default=5, help="Number of accounts to follow (default: 5)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--url", default="https://accountscenter.instagram.com/profiles/", help="Target URL after following")
    args = parser.parse_args()

    if args.pool:
        conn = db.get_connection()
        cur = conn.execute(
            """
            SELECT * FROM accounts
            WHERE platform = 'Meta+Instagram'
              AND (cookies IS NOT NULL AND cookies != '')
              AND (followed IS NULL OR followed < ?)
              AND (status = 'Created' OR status IS NULL)
            ORDER BY created_at DESC LIMIT ?
            """,
            (args.target, args.pool)
        )
        rows = [db.dict_from_row(r) for r in cur.fetchall()]
        if not rows:
            print("[INFO] No accounts in pool needing follows.")
            return

        print(f"[INFO] Found {len(rows)} account(s) to process via Multi-Insta Engine...")
        for acc in rows:
            aid = acc["id"]
            user = acc.get("instagram_username") or acc.get("username")
            print(f"\n================ Processing {aid} (@{user}) ================")
            run_multi_insta_follow(
                cookie_string=acc["cookies"],
                target_follows=args.target,
                target_url=args.url,
                headless=args.headless,
                account_id=aid,
            )

    elif args.account:
        conn = db.get_connection()
        cur = conn.execute("SELECT * FROM accounts WHERE id = ? OR instagram_username = ? LIMIT 1",
                           (args.account, args.account))
        row = cur.fetchone()
        if not row:
            print(f"[ERROR] Account {args.account} not found in database!")
            return
        acc = db.dict_from_row(row)
        run_multi_insta_follow(
            cookie_string=acc["cookies"],
            target_follows=args.target,
            target_url=args.url,
            headless=args.headless,
            account_id=acc["id"],
        )

    elif args.cookie:
        run_multi_insta_follow(
            cookie_string=args.cookie,
            target_follows=args.target,
            target_url=args.url,
            headless=args.headless,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
