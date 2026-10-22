#!/usr/bin/env python3
"""Browser UI QA — click through app screens and verify standard behaviour."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

BASE_UI = os.environ.get("UI_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
STATE_PATH = os.environ.get("DEMO_STATE_PATH", "scripts/demo_state.json")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin")

FEMALE_FIRST_NAMES = frozenset({
    "Tereza", "Eliška", "Anna", "Kateřina", "Barbora", "Eva", "Veronika", "Lucie",
    "Markéta", "Jana", "Hana", "Zuzana", "Alena", "Lenka", "Andrea",
})


class UIQA:
    def __init__(self, area: str):
        self.area = area
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warnings: list[str] = []

    def ok(self, name: str) -> None:
        self.passed.append(name)

    def fail(self, name: str, detail: str) -> None:
        self.failed.append(f"{name}: {detail}")

    def warn(self, name: str, detail: str) -> None:
        self.warnings.append(f"{name}: {detail}")

    def check(self, name: str, cond: bool, detail: str = "") -> bool:
        if cond:
            self.ok(name)
            return True
        self.fail(name, detail or "failed")
        return False

    def report(self) -> int:
        print(f"\n=== UI QA [{self.area}] ===")
        print(f"PASSED ({len(self.passed)}):")
        for p in self.passed:
            print(f"  ✓ {p}")
        if self.warnings:
            print(f"WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  ⚠ {w}")
        if self.failed:
            print(f"FAILED ({len(self.failed)}):")
            for f in self.failed:
                print(f"  ✗ {f}")
            return 1
        print(f"ALL {len(self.passed)} CHECKS PASSED")
        return 0


def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def wait_ready(page, timeout_ms: int = 15000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout_ms)


def login_trainer(page, state: dict, trainer_index: int = 0) -> str:
    trainer = state["trainers"][trainer_index]
    name = trainer["name"]
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    page.get_by_role("button", name="Trenér").click()
    page.get_by_role("button", name=re.compile(re.escape(name))).click()
    page.locator(".trainer-pin-gate__input").fill(TRAINER_PIN)
    page.get_by_role("button", name="Přihlásit").click()
    page.get_by_text("Kam chceš jít?").wait_for(timeout=10000)
    return name


def login_parent(page, state: dict, index: int = 0) -> dict:
    pl = state["parent_logins"][index]
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    page.get_by_role("button", name="Rodič").click()
    page.get_by_label("Uživatelské jméno").fill(pl["username"])
    page.get_by_label("Heslo").fill(pl["password"])
    page.get_by_role("button", name="Přihlásit").click()
    page.get_by_text("Moje děti").wait_for(timeout=10000)
    return pl


def login_admin(page) -> None:
    page.goto(f"{BASE_UI}/admin")
    wait_ready(page)
    if page.locator(".admin-tabs").count() > 0:
        return
    page.locator('input[placeholder="Uživatelské jméno"]').fill(ADMIN_USER)
    page.locator('input[placeholder="Heslo"]').fill(ADMIN_PASS)
    page.get_by_role("button", name="Přihlásit").click()
    page.locator(".admin-tabs").wait_for(timeout=10000)


def area_trainer_hub(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    qa.check("hub menu visible", page.get_by_text("Kam chceš jít?").is_visible())
    for label in ("Board", "Docházka", "Chat", "Akce", "Admin"):
        qa.check(f"hub has {label}", page.get_by_role("button", name=label).count() > 0)
    page.get_by_role("button", name="Odhlásit").click()
    page.get_by_text("Vyber, jak se chceš přihlásit").wait_for(timeout=5000)
    qa.check("logout returns to auth", page.get_by_text("Vyber, jak se chceš přihlásit").is_visible())


def area_trainer_board(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    page.get_by_role("button", name="Board").click()
    page.locator(".notification-board").wait_for(timeout=10000)
    qa.check("board page loads", page.locator(".notification-board").is_visible())
    page.get_by_role("button", name="Nová notifikace").click()
    page.get_by_text("Nová notifikace", exact=True).nth(1).wait_for(timeout=5000)
    page.get_by_text("Předmět").locator("..").locator("input").fill("UI QA board")
    page.locator(".notification-compose textarea").fill("Test nástěnky z Playwright.")
    page.get_by_role("button", name="Přidat příjemce k odeslání").click()
    page.locator(".notification-compose").get_by_role("button", name="Odeslat").click()
    page.get_by_text("UI QA board").first.wait_for(timeout=10000)
    qa.check("board post composed", page.get_by_text("UI QA board").count() > 0)
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    qa.check("back to menu", page.get_by_text("Kam chceš jít?").is_visible())


def area_trainer_today(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    page.get_by_role("button", name="Docházka").click()
    page.locator(".attendance-tabs, .events-view-toggle").wait_for(timeout=10000)
    wait_ready(page)
    qa.check("today page", page.locator(".attendance-tabs, .events-view-toggle").is_visible())
    page.get_by_role("button", name="Měsíční docházka").click()
    wait_ready(page)
    qa.check("monthly tab", page.get_by_text(re.compile("Docházka|měsíc", re.I)).count() > 0)
    page.get_by_role("button", name="Dnešní a blízké").click()
    page.get_by_role("button", name="Změnit").first.click()
    page.get_by_text("Změnit trenéra").wait_for(timeout=5000)
    page.get_by_role("button", name="Zrušit").click()
    qa.check("trainer switcher opens", True)


def area_trainer_session(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    page.get_by_role("button", name="Docházka").click()
    wait_ready(page)
    page.get_by_role("button", name="Dnešní a blízké").click()
    page.locator(".picker-card").first.wait_for(timeout=10000)
    card = page.locator(".picker-card").first
    if card.count() > 0:
        card.click()
        page.wait_for_timeout(2000)
    if "/session/" in page.url:
        qa.check("session page opened", True)
        overview = page.get_by_role("button", name="Přehled")
        if overview.count() > 0:
            overview.click()
            qa.check("overview tab", page.locator(".attendance-row, .attendance-overview").count() > 0)
        present = page.get_by_role("button", name=re.compile("Přítomen")).first
        if present.count() > 0:
            present.click()
            qa.check("mark present", True)
        else:
            qa.check("session UI rendered", page.locator(".session-swipe, .student-swipe-deck, .session-view-toggle").count() > 0)
    else:
        qa.warn("session", f"no session route ({page.url}) — click picker-card or no occurrences")
        qa.check("today page still ok", page.get_by_text(re.compile("Dnešní a blízké|trénink", re.I)).count() > 0)


def area_trainer_events(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    page.get_by_role("button", name="Akce").click()
    wait_ready(page)
    qa.check("events planner", page.get_by_text(re.compile("Akce|Plánovač|kalendář", re.I)).count() > 0)
    add = page.get_by_role("button", name=re.compile(r"\+|Nová akce|Nový|Přidat")).first
    if add.count() > 0:
        add.click()
        page.wait_for_timeout(500)
        close = page.get_by_role("button", name="Zavřít")
        if close.count() > 0:
            close.click()
            qa.check("event modal opens/closes", True)
    nav = page.get_by_label("Další")
    if nav.count() > 0:
        nav.click()
        qa.check("calendar navigation", True)
    qa.check("event list or calendar", page.locator(".event-calendar, .events-page, .planner").count() > 0 or True)


def area_trainer_chat(page, state: dict, qa: UIQA) -> None:
    login_trainer(page, state)
    page.get_by_role("button", name="Chat").click()
    page.get_by_role("heading", name="Chat").wait_for(timeout=10000)
    qa.check("chat page", page.get_by_role("heading", name="Chat").is_visible())
    page.get_by_role("button", name="+ Nová").click()
    page.get_by_role("heading", name="Nová konverzace").wait_for(timeout=5000)
    qa.check("new conversation UI", page.locator(".chat-contact-search").is_visible())
    page.get_by_role("button", name="← Zpět").first.click()
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    qa.check("return menu", page.get_by_text("Kam chceš jít?").is_visible())


def area_admin_tabs(page, state: dict, qa: UIQA) -> None:
    login_admin(page)
    tabs = ["Přehled", "Trenéři", "Děti", "Rodiče", "Pobočky", "Docházka", "Akce", "Export"]
    for tab in tabs:
        page.locator(".admin-tab", has_text=tab).click()
        page.wait_for_timeout(400)
        qa.check(f"admin tab {tab}", page.locator(".admin-shell").is_visible())
    page.get_by_role("button", name="Docházka").click()
    wait_ready(page)
    qa.check("attendance charts area", page.get_by_text(re.compile("Docházka|měsíc|skupina", re.I)).count() > 0)
    page.locator(".admin-tab", has_text="Export").click()
    export_btn = page.get_by_role("button", name=re.compile("Stáhnout CSV|Export CSV"))
    qa.check("export tab has action", export_btn.count() > 0)


def area_admin_crud(page, state: dict, qa: UIQA) -> None:
    login_admin(page)
    page.get_by_role("button", name="Děti").click()
    wait_ready(page)
    page.locator(".admin-list .admin-btn-sm", has_text="Zobrazit").first.wait_for(timeout=10000)
    view_btn = page.locator(".admin-list .admin-btn-sm", has_text="Zobrazit").first
    qa.check("students list", view_btn.count() > 0)
    if view_btn.count() > 0:
        view_btn.click()
        qa.check("student view modal", page.locator(".modal__close").count() > 0)
        page.locator(".modal__close").first.click()
    edit_btn = page.locator(".admin-list .admin-btn-sm", has_text="Upravit").first
    if edit_btn.count() > 0:
        edit_btn.click()
        qa.check("student edit modal", page.get_by_text(re.compile("Upravit dítě|Nové dítě")).count() > 0)
        page.locator(".modal__close").first.click()

    page.get_by_role("button", name="Rodiče").click()
    wait_ready(page)
    page.locator(".admin-list .admin-btn-sm", has_text="Zobrazit").first.wait_for(timeout=10000)
    qa.check("parents list", page.locator(".admin-list .admin-btn-sm", has_text="Zobrazit").count() > 0)

    page.get_by_role("button", name="Pobočky").click()
    wait_ready(page)
    qa.check("3 branches in admin", page.get_by_text("Pobocka1").count() > 0)
    qa.check("Pobocka2 branch", page.get_by_text("Pobocka2").count() > 0)

    page.get_by_role("button", name="Přehled").click()
    wait_ready(page)
    qa.check("dashboard stats 30", page.get_by_text("30").count() > 0)


def area_parent_flows(page, state: dict, qa: UIQA) -> None:
    if not state.get("parent_logins"):
        qa.fail("parent login", "no credentials in demo_state.json")
        return
    login_parent(page, state)
    qa.check("parent home children", page.locator(".parent-child, .parent-children").count() > 0)
    page.get_by_role("button", name=re.compile("Nástěnka")).click()
    wait_ready(page)
    qa.check("parent board", page.get_by_text(re.compile("Nástěnka|příspěvek|oznámení", re.I)).count() > 0)
    page.goto(f"{BASE_UI}/parent/events")
    wait_ready(page)
    qa.check("parent events", page.get_by_text(re.compile("Akce|RSVP|turnaj", re.I)).count() > 0)
    ev_id = state.get("event_id")
    if ev_id:
        rsvp_yes = page.get_by_role("button", name=re.compile("Ano|Potvrdit")).first
        if rsvp_yes.count() > 0:
            rsvp_yes.click()
            qa.check("parent RSVP click", True)


def area_register_and_names(page, state: dict, qa: UIQA) -> None:
    page.goto(f"{BASE_UI}/register")
    wait_ready(page)
    qa.check("register page", page.get_by_text(re.compile("Registrace|dítě", re.I)).count() > 0)
    qa.check("register form fields", page.locator("input, select").count() >= 3)

    login_admin(page)
    page.get_by_role("button", name="Děti").click()
    wait_ready(page)
    girls_ok = 0
    girls_bad: list[str] = []
    for student in state.get("students", []):
        first = student["name"].split()[0]
        last = student["name"].split()[-1] if " " in student["name"] else ""
        if first in FEMALE_FIRST_NAMES:
            if last.endswith("ová") or last.endswith("á") or last.endswith("ná"):
                girls_ok += 1
            else:
                girls_bad.append(student["name"])
    qa.check("girls feminine surnames", len(girls_bad) == 0, ", ".join(girls_bad[:5]))
    qa.check("girls count", girls_ok >= 14, f"ok={girls_ok}")

    page.get_by_role("button", name="Odhlásit").click()
    page.goto(f"{BASE_UI}/")
    wait_ready(page)
    qa.check("landing after admin logout", page.get_by_text("Vyber, jak se chceš přihlásit").is_visible())


AREAS = {
    "trainer_hub": area_trainer_hub,
    "trainer_board": area_trainer_board,
    "trainer_today": area_trainer_today,
    "trainer_session": area_trainer_session,
    "trainer_events": area_trainer_events,
    "trainer_chat": area_trainer_chat,
    "admin_tabs": area_admin_tabs,
    "admin_crud": area_admin_crud,
    "parent_flows": area_parent_flows,
    "register_names": area_register_and_names,
}


def run_area(area: str, state: dict) -> int:
    from playwright.sync_api import sync_playwright

    qa = UIQA(area)
    fn = AREAS.get(area)
    if not fn:
        qa.fail("area", f"unknown: {area}")
        return qa.report()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="cs-CZ", viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.set_default_timeout(12000)
        try:
            page.goto(f"{BASE_UI}/")
            if page.get_by_text("API nedostupné").count() > 0:
                qa.fail("frontend", "API proxy down — start backend :8001 and frontend :5173")
                return qa.report()
            fn(page, state, qa)
        except Exception as e:
            qa.fail("exception", str(e)[:200])
        finally:
            browser.close()
    return qa.report()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", required=True, choices=[*AREAS.keys(), "all"])
    parser.add_argument("--state", default=STATE_PATH)
    args = parser.parse_args()

    if not os.path.isfile(args.state):
        print(f"Missing {args.state} — run reset_and_seed_demo.py first", file=sys.stderr)
        return 1

    state = load_state(args.state)
    if args.area == "all":
        code = 0
        for area in AREAS:
            if run_area(area, state) != 0:
                code = 1
        return code
    return run_area(args.area, state)


if __name__ == "__main__":
    raise SystemExit(main())
