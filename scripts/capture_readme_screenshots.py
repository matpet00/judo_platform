#!/usr/bin/env python3
"""Capture polished UI screenshots for the GitHub README."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
BASE_UI = os.environ.get("UI_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
STATE_PATH = Path(os.environ.get("DEMO_STATE_PATH", ROOT / "scripts" / "demo_state.json"))
TRAINER_PIN = os.environ.get("TRAINER_PIN", "123456")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin")

# Mobile-first product shots
VIEWPORT = {"width": 390, "height": 844}
# Wider admin panel
ADMIN_VIEWPORT = {"width": 1100, "height": 900}


def load_state() -> dict:
    with STATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def wait_ready(page, timeout_ms: int = 20000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout_ms)


def shot(page, name: str) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  saved {path.relative_to(ROOT)}")


def login_trainer(page, state: dict, name: str | None = None) -> None:
    trainer_name = name or state["trainers"][0]["name"]
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    page.get_by_role("button", name="Trenér").click()
    page.get_by_role("button", name=re.compile(re.escape(trainer_name))).click()
    page.locator(".trainer-pin-gate__input").fill(TRAINER_PIN)
    page.get_by_role("button", name="Přihlásit").click()
    page.get_by_text("Kam chceš jít?").wait_for(timeout=15000)


def login_parent(page, state: dict) -> None:
    pl = state["parent_logins"][0]
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    page.get_by_role("button", name="Rodič").click()
    page.get_by_label("Uživatelské jméno").fill(pl["username"])
    page.get_by_label("Heslo").fill(pl["password"])
    page.get_by_role("button", name="Přihlásit").click()
    page.get_by_text("Moje děti").wait_for(timeout=15000)


def login_admin(page) -> None:
    page.goto(f"{BASE_UI}/admin")
    wait_ready(page)
    if page.locator(".admin-tabs").count() > 0:
        return
    page.locator('input[placeholder="Uživatelské jméno"]').fill(ADMIN_USER)
    page.locator('input[placeholder="Heslo"]').fill(ADMIN_PASS)
    page.get_by_role("button", name="Přihlásit").click()
    page.locator(".admin-tabs").wait_for(timeout=15000)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    print(f"Capturing screenshots → {OUT.relative_to(ROOT)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1.5,
            locale="cs-CZ",
        )
        page = context.new_page()

        # 1) Landing / role picker
        page.goto(f"{BASE_UI}/")
        wait_ready(page)
        page.get_by_text("Vyber, jak se chceš přihlásit").wait_for(timeout=15000)
        shot(page, "01-landing")

        # 2) Trainer hub
        login_trainer(page, state, state["trainers"][0]["name"])
        shot(page, "02-trainer-hub")

        # 3) Attendance today
        page.get_by_role("button", name=re.compile(r"^Docházka")).click()
        page.wait_for_url("**/today", timeout=15000)
        wait_ready(page)
        page.wait_for_timeout(800)
        shot(page, "03-trainer-attendance")

        # 4) Session list — SPA click (full reload would race auth gate)
        page.locator(".picker-card").first.click()
        page.wait_for_url("**/session/**", timeout=15000)
        page.wait_for_timeout(1000)
        seznam = page.get_by_role("button", name="Seznam")
        if seznam.count():
            seznam.click()
            page.wait_for_timeout(400)
        overview = page.get_by_role("button", name=re.compile(r"Přehled"))
        if overview.count():
            overview.click()
            page.wait_for_timeout(400)
        shot(page, "04-session-attendance")

        # 5) Events
        page.locator("a").filter(has_text="Zpět").first.click()
        page.wait_for_url("**/today", timeout=10000)
        page.get_by_role("link", name="Menu").click()
        page.get_by_text("Kam chceš jít?").wait_for(timeout=10000)
        page.locator(".trainer-card").filter(has_text="Akce").click()
        page.wait_for_url("**/events", timeout=15000)
        wait_ready(page)
        page.wait_for_timeout(800)
        shot(page, "05-trainer-events")

        # 6) Board — Events uses button.board-link for Menu
        page.locator("button.board-link, a.board-link").filter(has_text="Menu").click()
        page.get_by_text("Kam chceš jít?").wait_for(timeout=10000)
        page.locator(".trainer-card").filter(has_text="Board").click()
        page.wait_for_url("**/board", timeout=15000)
        wait_ready(page)
        page.wait_for_timeout(800)
        shot(page, "06-trainer-board")

        # 7) Parent home (fresh context)
        context.clear_cookies()
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        login_parent(page, state)
        shot(page, "07-parent-home")

        # 8) Parent attendance
        page.get_by_role("button", name=re.compile(r"docházk", re.I)).first.click()
        page.wait_for_url("**/parent/attendance", timeout=15000)
        wait_ready(page)
        page.wait_for_timeout(800)
        shot(page, "08-parent-attendance")

        # 9) Registration form (anonymous)
        reg_ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1.5, locale="cs-CZ")
        reg_page = reg_ctx.new_page()
        reg_page.goto(f"{BASE_UI}/register")
        wait_ready(reg_page)
        reg_page.wait_for_timeout(600)
        shot(reg_page, "09-registration")
        reg_ctx.close()

        # 10) Admin overview (wider)
        admin_ctx = browser.new_context(
            viewport=ADMIN_VIEWPORT,
            device_scale_factor=1.5,
            locale="cs-CZ",
        )
        admin_page = admin_ctx.new_page()
        login_admin(admin_page)
        wait_ready(admin_page)
        admin_page.wait_for_timeout(800)
        shot(admin_page, "10-admin-overview")

        admin_ctx.close()
        context.close()
        browser.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
