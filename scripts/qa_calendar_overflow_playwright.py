#!/usr/bin/env python3
"""Verify event calendar month grid does not overflow horizontally on narrow viewports."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

VIEWPORT_WIDTH = 375
VIEWPORT_HEIGHT = 812
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "calendar_overflow_fixture.html"


def measure_overflow(page) -> dict:
    return page.evaluate(
        """() => {
            const calendar = document.querySelector('.event-calendar');
            const grid = document.querySelector('.event-calendar__grid');
            const shell = document.querySelector('.app-shell');
            const stressCell = document.querySelector('[data-testid="stress-cell"]');
            const stressPillCount = stressCell
                ? stressCell.querySelectorAll('.event-calendar__pill').length
                : 0;
            const calendarRight = calendar?.getBoundingClientRect().right ?? 0;
            const protruding = calendar
                ? [...calendar.querySelectorAll('.event-calendar__pill, .event-calendar__cell, .event-calendar__grid')]
                    .filter((el) => el.getBoundingClientRect().right > calendarRight + 0.5)
                    .map((el) => el.className)
                : [];
            return {
                viewportWidth: window.innerWidth,
                gridScrollWidth: grid?.scrollWidth ?? 0,
                gridClientWidth: grid?.clientWidth ?? 0,
                calendarScrollWidth: calendar?.scrollWidth ?? 0,
                calendarClientWidth: calendar?.clientWidth ?? 0,
                shellScrollWidth: shell?.scrollWidth ?? 0,
                shellClientWidth: shell?.clientWidth ?? 0,
                documentScrollWidth: document.documentElement.scrollWidth,
                documentClientWidth: document.documentElement.clientWidth,
                stressPillCount,
                protruding,
            };
        }"""
    )


def run_fixture(headless: bool = True) -> int:
    from playwright.sync_api import sync_playwright

    if not FIXTURE_PATH.is_file():
        print(f"Missing fixture: {FIXTURE_PATH}", file=sys.stderr)
        return 1

    fixture_url = FIXTURE_PATH.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="cs-CZ",
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        )
        page = context.new_page()
        try:
            page.goto(fixture_url, wait_until="load")
            page.wait_for_selector('[data-testid="calendar-grid"]')

            metrics = measure_overflow(page)
            failures: list[str] = []

            if metrics["stressPillCount"] < 5:
                failures.append(
                    f"stress cell has only {metrics['stressPillCount']} pills (expected 5+)"
                )

            grid_overflow = metrics["gridScrollWidth"] - metrics["calendarClientWidth"]
            if grid_overflow > 0:
                failures.append(
                    "grid overflows calendar container: "
                    f"grid.scrollWidth={metrics['gridScrollWidth']} > "
                    f"calendar.clientWidth={metrics['calendarClientWidth']}"
                )

            calendar_overflow = metrics["calendarScrollWidth"] - metrics["calendarClientWidth"]
            if calendar_overflow > 0:
                failures.append(
                    "calendar section overflows itself: "
                    f"calendar.scrollWidth={metrics['calendarScrollWidth']} > "
                    f"calendar.clientWidth={metrics['calendarClientWidth']}"
                )

            doc_overflow = metrics["documentScrollWidth"] - metrics["viewportWidth"]
            if doc_overflow > 1:
                failures.append(
                    "page overflows viewport: "
                    f"document.scrollWidth={metrics['documentScrollWidth']} > "
                    f"viewport={metrics['viewportWidth']}"
                )

            if metrics["protruding"]:
                failures.append(
                    "elements protrude past calendar right edge: "
                    + ", ".join(metrics["protruding"][:5])
                )

            print("=== Calendar overflow QA ===")
            print(f"fixture: {FIXTURE_PATH}")
            print(f"viewport: {metrics['viewportWidth']}x{VIEWPORT_HEIGHT}")
            print(
                "grid: "
                f"scrollWidth={metrics['gridScrollWidth']} "
                f"clientWidth={metrics['gridClientWidth']} "
                f"calendar.clientWidth={metrics['calendarClientWidth']}"
            )
            print(
                "shell: "
                f"scrollWidth={metrics['shellScrollWidth']} "
                f"clientWidth={metrics['shellClientWidth']}"
            )
            print(f"stress pills: {metrics['stressPillCount']}")

            if failures:
                print(f"FAILED ({len(failures)}):")
                for item in failures:
                    print(f"  ✗ {item}")
                return 1

            print("PASSED — no horizontal overflow detected")
            return 0
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with UI visible (default: headless)",
    )
    args = parser.parse_args()
    return run_fixture(headless=not args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
