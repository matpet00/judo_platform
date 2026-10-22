#!/usr/bin/env python3
"""Full-app QA against a running judo backend (admin + trainer flows).

Idempotent seed data uses the QA_FULL name prefix. Safe to re-run.

Usage:
    python scripts/full_app_qa.py [--base http://127.0.0.1:8001]
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

TAG = "QA_FULL"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
API_KEY = os.environ.get("API_WRITE_KEY", "")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{status}] {self.name}{suffix}"


@dataclass
class SeedState:
    admin_token: str = ""
    trainer_token: str = ""
    trainer_id: int = 0
    orlova_branch_id: int = 0
    second_branch_id: int = 0
    calendar_group_ids: list[int] = field(default_factory=list)
    nocalendar_group_id: int | None = None
    orlova_student_ids: list[int] = field(default_factory=list)
    second_branch_student_ids: list[int] = field(default_factory=list)
    event_id: int | None = None
    test_month: str = ""


def write_headers(token: str | None = None) -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def month_bounds(month: str) -> tuple[str, str] | None:
    parts = month.split("-")
    if len(parts) != 2:
        return None
    year, mon = int(parts[0]), int(parts[1])
    last_day = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def calendar_groups_for_month(groups: list[dict[str, Any]], month: str) -> list[dict[str, Any]]:
    """Mirror frontend MonthlyAttendanceReport.calendarGroupsForMonth."""
    bounds = month_bounds(month)
    if not bounds:
        return []
    start, end = bounds
    out: list[dict[str, Any]] = []
    for g in groups:
        weekdays = g.get("weekdays") or []
        if not weekdays:
            continue
        active_from = g.get("active_from")
        active_until = g.get("active_until")
        if active_from and active_from > end:
            continue
        if active_until and active_until < start:
            continue
        out.append(g)
    return out


def occurrence_dates(group: dict[str, Any], from_date: date, to_date: date) -> list[date]:
    weekdays = group.get("weekdays") or []
    if not weekdays:
        return []
    lo, hi = from_date, to_date
    active_from = group.get("active_from")
    active_until = group.get("active_until")
    if active_from:
        af = date.fromisoformat(active_from)
        if af > lo:
            lo = af
    if active_until:
        au = date.fromisoformat(active_until)
        if au < hi:
            hi = au
    dates: list[date] = []
    cur = lo
    while cur <= hi:
        if cur.isoweekday() in weekdays:
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


class QAClient:
    def __init__(self, base: str) -> None:
        self.base = base
        self.client = httpx.Client(base_url=base, timeout=45.0)
        self.checks: list[Check] = []

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, passed, detail))

    def require(self, name: str, resp: httpx.Response | None, ok: tuple[int, ...] = (200,)) -> dict[str, Any] | list[Any] | None:
        if resp is None:
            self.record(name, False, "no response")
            return None
        if resp.status_code not in ok:
            self.record(name, False, f"HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        self.record(name, True)
        if resp.status_code == 204:
            return None
        return resp.json()

    def close(self) -> None:
        self.client.close()


def login_admin(qa: QAClient) -> str | None:
    resp = qa.client.post(
        "/admin/login",
        headers=write_headers(),
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    data = qa.require("admin_login", resp)
    return data["access_token"] if isinstance(data, dict) else None


def login_trainer(qa: QAClient, trainer_id: int) -> str | None:
    resp = qa.client.post(
        f"/trainers/{trainer_id}/verify-pin",
        headers=write_headers(),
        json={"pin": TRAINER_PIN},
    )
    data = qa.require("trainer_pin_login", resp)
    return data["access_token"] if isinstance(data, dict) else None


def find_by_name(items: list[dict[str, Any]], field: str, prefix: str) -> list[dict[str, Any]]:
    return [x for x in items if str(x.get(field, "")).startswith(prefix)]


def seed_data(qa: QAClient, state: SeedState) -> bool:
    print("\n== SEED (idempotent, QA_FULL) ==")

    admin = login_admin(qa)
    if not admin:
        return False
    state.admin_token = admin

    trainers = qa.client.get("/trainers").json()
    trainer = next((t for t in trainers if t["id"] <= 5 and any(b["name"] == "Pobocka1" for b in t["branches"])), trainers[0])
    state.trainer_id = trainer["id"]
    tok = login_trainer(qa, state.trainer_id)
    if not tok:
        return False
    state.trainer_token = tok
    ah = write_headers(admin)
    th = write_headers(tok)

    branches = qa.client.get("/branches").json()
    orlova = next((b for b in branches if b["name"] == "Pobocka1"), None)
    if orlova is None:
        qa.record("seed_orlova_branch", False, "Pobocka1 branch missing")
        return False
    state.orlova_branch_id = orlova["id"]

    qa_branches = find_by_name(branches, "name", f"{TAG} ")
    if qa_branches:
        state.second_branch_id = qa_branches[0]["id"]
        qa.record("seed_second_branch", True, f"reuse id={state.second_branch_id}")
    else:
        resp = qa.client.post(
            "/branches",
            headers=ah,
            json={"name": f"{TAG} Pobocka3", "address": "QA test branch"},
        )
        data = qa.require("seed_create_branch", resp, (201,))
        if not isinstance(data, dict):
            return False
        state.second_branch_id = data["id"]

    students = qa.client.get("/students", headers=ah).json()
    qa_students = find_by_name(students, "first_name", f"{TAG}")
    orlova_ids = [s["id"] for s in students if any(b["id"] == state.orlova_branch_id for b in s["branches"])]
    state.orlova_student_ids = orlova_ids[:6]
    if len(state.orlova_student_ids) < 3:
        qa.record("seed_orlova_students", False, f"only {len(state.orlova_student_ids)} on Pobocka1")
        return False

    second_ids = [s["id"] for s in qa_students if any(b["id"] == state.second_branch_id for b in s["branches"])]
    if len(second_ids) < 4:
        need = 4 - len(second_ids)
        ages = ["U8", "U10", "U12", "U14"]
        for i in range(need):
            resp = qa.client.post(
                "/students",
                headers=ah,
                json={
                    "first_name": f"{TAG} S{len(second_ids) + i}",
                    "last_name": "Test",
                    "age_group": ages[(len(second_ids) + i) % len(ages)],
                    "branch_ids": [state.second_branch_id],
                    "parents": [{
                        "first_name": f"{TAG}P{len(second_ids) + i}",
                        "last_name": "Rodic",
                        "email": f"qa_full_parent_{len(second_ids) + i}_{int(time.time())}@example.com",
                        "phone": f"+420700{len(second_ids) + i:06d}",
                    }],
                },
            )
            data = qa.require(f"seed_student_b_{i}", resp, (200,))
            if isinstance(data, dict):
                second_ids.append(data["id"])
    state.second_branch_student_ids = second_ids[:4]
    qa.record("seed_students_two_branches", len(state.second_branch_student_ids) >= 4,
              f"Pobocka1={len(state.orlova_student_ids)}, branch2={len(state.second_branch_student_ids)}")

    groups = qa.client.get("/training-groups", headers=th).json()
    qa_groups = find_by_name(groups, "name", f"{TAG} ")
    calendar = [g for g in qa_groups if g.get("weekdays")]
    nocal = next((g for g in qa_groups if not g.get("weekdays")), None)

    specs = [
        {
            "name": f"{TAG} Pobocka1 Po+Ct",
            "branch_id": state.orlova_branch_id,
            "start_time": "16:30:00",
            "end_time": "17:30:00",
            "weekdays": [1, 4],
            "student_ids": state.orlova_student_ids[:4],
        },
        {
            "name": f"{TAG} Pobocka3 Ut+Ct",
            "branch_id": state.second_branch_id,
            "start_time": "17:00:00",
            "end_time": "18:00:00",
            "weekdays": [2, 4],
            "student_ids": state.second_branch_student_ids,
        },
    ]

    by_name = {g["name"]: g for g in qa_groups}
    for spec in specs:
        if spec["name"] in by_name:
            state.calendar_group_ids.append(by_name[spec["name"]]["id"])
            continue
        resp = qa.client.post("/training-groups", headers=th, json=spec)
        data = qa.require(f"seed_group_{spec['name']}", resp, (201,))
        if isinstance(data, dict):
            state.calendar_group_ids.append(data["id"])

    if nocal:
        state.nocalendar_group_id = nocal["id"]
    elif f"{TAG} Ad-hoc" not in by_name:
        resp = qa.client.post(
            "/training-groups",
            headers=th,
            json={
                "name": f"{TAG} Ad-hoc",
                "branch_id": state.orlova_branch_id,
                "start_time": "18:00:00",
                "end_time": "19:00:00",
                "weekdays": None,
                "student_ids": state.orlova_student_ids[:2],
            },
        )
        data = qa.require("seed_group_adhoc", resp, (201,))
        if isinstance(data, dict):
            state.nocalendar_group_id = data["id"]
    else:
        state.nocalendar_group_id = by_name[f"{TAG} Ad-hoc"]["id"]

    qa.record("seed_calendar_groups", len(state.calendar_group_ids) >= 2,
              f"ids={state.calendar_group_ids}")

    now = date.today()
    state.test_month = f"{now.year}-{now.month:02d}"
    month_start = date(now.year, now.month, 1)
    if now.month == 12:
        month_end = date(now.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(now.year, now.month + 1, 1) - timedelta(days=1)

    statuses = ["present", "absent", "excused"]
    sessions_created = 0
    attendance_marked = 0

    groups_full = qa.client.get("/training-groups", headers=th).json()
    group_map = {g["id"]: g for g in groups_full}

    for gid in state.calendar_group_ids:
        group = group_map.get(gid, {})
        dates = occurrence_dates(group, month_start, month_end)
        for idx, session_date in enumerate(dates[:8]):
            resp = qa.client.post(
                f"/training-groups/{gid}/sessions",
                headers=th,
                json={"session_date": session_date.isoformat()},
            )
            if resp.status_code not in (200, 201):
                qa.record(f"seed_session_{gid}_{session_date}", False, resp.text[:120])
                continue
            sessions_created += 1
            session = resp.json()
            sid = session["id"]
            roster = [s["id"] for s in group.get("students", [])]
            for j, student_id in enumerate(roster):
                status = statuses[(idx + j) % 3]
                detail = qa.client.get(f"/training-sessions/{sid}", headers=th).json()
                existing = next((s for s in detail.get("students", []) if s["id"] == student_id), None)
                att = existing.get("attendance") if existing else None
                if att:
                    patch = qa.client.patch(
                        f"/training-sessions/{sid}/attendance/{att['id']}",
                        headers=th,
                        json={"status": status},
                    )
                    if patch.status_code == 200:
                        attendance_marked += 1
                else:
                    post = qa.client.post(
                        f"/training-sessions/{sid}/attendance",
                        headers=th,
                        json={"student_id": student_id, "status": status},
                    )
                    if post.status_code in (200, 201):
                        attendance_marked += 1

            # Guest on first session of first calendar group
            if gid == state.calendar_group_ids[0] and idx == 0 and state.second_branch_student_ids:
                guest_id = state.second_branch_student_ids[0]
                if guest_id not in roster:
                    post = qa.client.post(
                        f"/training-sessions/{sid}/attendance",
                        headers=th,
                        json={"student_id": guest_id, "status": "present"},
                    )
                    if post.status_code in (200, 201):
                        attendance_marked += 1

    qa.record("seed_month_sessions", sessions_created >= 4, f"sessions={sessions_created}, marks={attendance_marked}")

    # QA_FULL event in current month for admin event-participation
    month_dt_start, _ = month_bounds(state.test_month)
    event_start = datetime.fromisoformat(f"{month_dt_start}T10:00:00").replace(tzinfo=UTC) + timedelta(days=10)
    qa_events = [e for e in qa.client.get("/events", headers=th).json() if str(e.get("title", "")).startswith(TAG)]
    if qa_events:
        state.event_id = qa_events[0]["id"]
        qa.record("seed_event", True, f"reuse id={state.event_id}")
    else:
        resp = qa.client.post(
            "/events",
            headers=th,
            json={
                "title": f"{TAG} Turnaj",
                "event_type": "tournament",
                "location": "QA hala",
                "starts_at": event_start.isoformat().replace("+00:00", "Z"),
                "targets": [{"audience": "parent"}],
            },
        )
        data = qa.require("seed_event_create", resp, (201,))
        if isinstance(data, dict):
            state.event_id = data["id"]
            qa.client.post(
                f"/events/{state.event_id}/rsvp",
                headers=th,
                json={"responses": [{"status": "yes"}]},
            )

    return True


def test_admin_dashboard(qa: QAClient, state: SeedState) -> None:
    resp = qa.client.get("/admin/stats", headers=auth_headers(state.admin_token))
    data = qa.require("admin_stats", resp)
    if not isinstance(data, dict):
        return
    ok = (
        data.get("trainers", 0) >= 1
        and data.get("students", 0) >= 8
        and data.get("branches", 0) >= 2
        and data.get("training_groups", 0) >= 2
    )
    qa.record("admin_stats_counts", ok, f"groups={data.get('training_groups')}, students={data.get('students')}")


def test_admin_exports(qa: QAClient, state: SeedState) -> None:
    month = state.test_month
    resp = qa.client.get(f"/admin/attendance.csv?month={month}", headers=auth_headers(state.admin_token))
    if resp.status_code != 200:
        qa.record("attendance_csv", False, f"HTTP {resp.status_code}")
    else:
        body = resp.text
        ok = body.startswith("\ufeff") and "Datum" in body and "Docházka" in body
        qa.record("attendance_csv", ok, f"bytes={len(body.encode())}")

    resp = qa.client.get(f"/admin/event-participation.csv?month={month}", headers=auth_headers(state.admin_token))
    if resp.status_code != 200:
        qa.record("event_participation_csv", False, f"HTTP {resp.status_code}")
    else:
        body = resp.text
        ok = body.startswith("\ufeff") and "Akce" in body and "Účast" in body
        qa.record("event_participation_csv", ok, f"bytes={len(body.encode())}")

    if state.orlova_branch_id:
        resp = qa.client.get(
            f"/admin/attendance.csv?month={month}&branch_id={state.orlova_branch_id}",
            headers=auth_headers(state.admin_token),
        )
        qa.record("attendance_csv_branch_filter", resp.status_code == 200, f"HTTP {resp.status_code}")


def test_admin_event_participation(qa: QAClient, state: SeedState) -> None:
    resp = qa.client.get(
        f"/admin/event-participation?month={state.test_month}",
        headers=auth_headers(state.admin_token),
    )
    data = qa.require("admin_event_participation", resp)
    if not isinstance(data, list):
        return
    tagged = [e for e in data if str(e.get("title", "")).startswith(TAG)]
    qa.record("admin_event_participation_has_qa_event", len(tagged) >= 1, f"events_in_month={len(data)}")


def test_trainer_calendar_flow(qa: QAClient, state: SeedState) -> None:
    th = auth_headers(state.trainer_token)
    month = state.test_month
    bounds = month_bounds(month)
    if not bounds:
        qa.record("month_bounds", False)
        return
    start, end = bounds

    groups = qa.client.get("/training-groups", headers=th).json()
    calendar = calendar_groups_for_month(groups, month)
    qa.record("calendar_groups_nonempty", len(calendar) >= 2, f"calendar={len(calendar)}, all={len(groups)}")

    if state.nocalendar_group_id:
        cal_ids = {g["id"] for g in calendar}
        excluded = state.nocalendar_group_id not in cal_ids
        qa.record("calendar_excludes_no_weekdays_group", excluded,
                  f"nocalendar_id={state.nocalendar_group_id}")

    all_with_weekdays = [g for g in groups if g.get("weekdays")]
    for g in all_with_weekdays:
        if g["id"] == state.nocalendar_group_id:
            continue
        if g.get("active_from") and g["active_from"] > end:
            continue
        if g.get("active_until") and g["active_until"] < start:
            continue
        if g["id"] not in {c["id"] for c in calendar}:
            qa.record("calendar_includes_weekday_groups", False, f"missing group {g['id']}")
            return
    qa.record("calendar_includes_weekday_groups", True)

    resp = qa.client.get(f"/training-groups/occurrences?from={start}&to={end}", headers=th)
    occ = qa.require("occurrences_api", resp)
    if not isinstance(occ, list):
        return
    qa_occ = [o for o in occ if o["group_id"] in state.calendar_group_ids]
    qa.record("occurrences_for_seed_groups", len(qa_occ) >= 4, f"occurrences={len(qa_occ)}")

    if state.calendar_group_ids:
        gid = state.calendar_group_ids[0]
        resp = qa.client.get(
            f"/training-groups/{gid}/attendance-report?month={month}",
            headers=th,
        )
        report = qa.require("attendance_report_month", resp)
        if isinstance(report, dict):
            ok = report.get("sessions", 0) >= 1 and len(report.get("rows", [])) >= 1
            qa.record("attendance_report_has_data", ok,
                      f"sessions={report.get('sessions')}, rows={len(report.get('rows', []))}")


def test_empty_month_report(qa: QAClient, state: SeedState) -> None:
    if not state.calendar_group_ids:
        qa.record("empty_month_report", False, "no calendar group")
        return
    gid = state.calendar_group_ids[0]
    resp = qa.client.get(
        f"/training-groups/{gid}/attendance-report?month=2099-01",
        headers=auth_headers(state.trainer_token),
    )
    data = qa.require("empty_month_report", resp)
    if isinstance(data, dict):
        rows = data.get("rows") or []
        # API returns roster rows with zero counts (no sessions in month), not an empty list.
        ok = data.get("sessions") == 0 and all(
            r.get("present") == 0 and r.get("absent") == 0 and r.get("excused") == 0 for r in rows
        )
        qa.record("empty_month_report_zero", ok,
                  f"sessions={data.get('sessions')}, roster_rows={len(rows)}")


def test_guest_on_session(qa: QAClient, state: SeedState) -> None:
    if not state.calendar_group_ids or not state.second_branch_student_ids:
        qa.record("guest_on_session", False, "missing seed ids")
        return
    th = auth_headers(state.trainer_token)
    gid = state.calendar_group_ids[0]
    groups = qa.client.get("/training-groups", headers=th).json()
    group = next((g for g in groups if g["id"] == gid), None)
    if not group:
        qa.record("guest_on_session", False, "group not found")
        return

    month_start = date.today().replace(day=1)
    dates = occurrence_dates(group, month_start, date.today())
    if not dates:
        qa.record("guest_on_session", False, "no occurrence dates")
        return
    session_date = dates[0].isoformat()
    resp = qa.client.post(
        f"/training-groups/{gid}/sessions",
        headers=write_headers(state.trainer_token),
        json={"session_date": session_date},
    )
    if resp.status_code not in (200, 201):
        qa.record("guest_on_session", False, f"session HTTP {resp.status_code}")
        return
    sid = resp.json()["id"]
    guest_id = state.second_branch_student_ids[0]
    roster = {s["id"] for s in group.get("students", [])}
    if guest_id in roster:
        guest_id = state.second_branch_student_ids[-1]
    post = qa.client.post(
        f"/training-sessions/{sid}/attendance",
        headers=write_headers(state.trainer_token),
        json={"student_id": guest_id, "status": "present"},
    )
    if post.status_code == 409:
        qa.record("guest_on_session_idempotent", True, "guest already marked (seed)")
    elif post.status_code not in (200, 201):
        qa.record("guest_on_session", False, f"attendance HTTP {post.status_code}")
        return
    else:
        qa.record("guest_on_session_mark", True)

    detail = qa.client.get(f"/training-sessions/{sid}", headers=th).json()
    guest_rows = [s for s in detail.get("students", []) if s.get("is_guest")]
    qa.record("guest_on_session_detail", any(s["id"] == guest_id for s in guest_rows),
              f"guest_rows={len(guest_rows)}")

    report = qa.client.get(
        f"/training-groups/{gid}/attendance-report?month={state.test_month}",
        headers=th,
    ).json()
    guest_report = [r for r in report.get("rows", []) if r.get("is_guest") and r["student_id"] == guest_id]
    qa.record("guest_in_monthly_report", len(guest_report) == 1,
              f"present={guest_report[0]['present'] if guest_report else 'n/a'}")


def test_delete_student_with_attendance(qa: QAClient, state: SeedState) -> None:
    ah = write_headers(state.admin_token)
    th = write_headers(state.trainer_token)
    resp = qa.client.post(
        "/students",
        headers=ah,
        json={
            "first_name": f"{TAG} DeleteMe",
            "last_name": "Disposable",
            "age_group": "U10",
            "branch_ids": [state.orlova_branch_id],
            "parents": [{
                "first_name": f"{TAG}Del",
                "last_name": "Parent",
                "email": f"qa_full_del_{int(time.time())}@example.com",
                "phone": "+420700999999",
            }],
        },
    )
    data = qa.require("delete_test_create_student", resp, (200,))
    if not isinstance(data, dict):
        return
    student_id = data["id"]

    if not state.calendar_group_ids:
        qa.record("delete_student_with_attendance", False, "no group")
        return
    gid = state.calendar_group_ids[0]
    session_date = date.today().isoformat()
    sresp = qa.client.post(
        f"/training-groups/{gid}/sessions",
        headers=th,
        json={"session_date": session_date},
    )
    if sresp.status_code not in (200, 201):
        qa.record("delete_test_session", False, sresp.text[:100])
        qa.client.delete(f"/students/{student_id}", headers=ah)
        return
    sid = sresp.json()["id"]
    qa.client.post(
        f"/training-sessions/{sid}/attendance",
        headers=th,
        json={"student_id": student_id, "status": "present"},
    )

    dresp = qa.client.delete(f"/students/{student_id}", headers=ah)
    qa.record("delete_student_with_attendance", dresp.status_code == 204, f"HTTP {dresp.status_code}")

    all_students = qa.client.get("/students", headers=ah).json()
    still_there = any(s["id"] == student_id for s in all_students)
    qa.record("delete_student_gone", not still_there, f"in_list={still_there}")


async def test_concurrent_rsvp(qa: QAClient, state: SeedState) -> None:
    if not state.event_id:
        qa.record("concurrent_rsvp", False, "no event")
        return

    ah = auth_headers(state.admin_token)
    students = qa.client.get("/students", headers=ah).json()
    candidate = next(
        (s for s in students if s.get("parents") and any(b["id"] == state.second_branch_id for b in s["branches"])),
        None,
    )
    if not candidate or not candidate.get("parents"):
        qa.record("concurrent_rsvp", False, "no parent/child pair")
        return
    parent_id = candidate["parents"][0]["id"]
    child_id = candidate["id"]

    resp = qa.client.post(f"/admin/parents/{parent_id}/resend-credentials", headers=ah)
    if resp.status_code != 200:
        qa.record("concurrent_rsvp_credentials", False, resp.text[:120])
        return
    creds = resp.json()
    login = qa.client.post(
        "/parents/login",
        headers=write_headers(),
        json={"username": creds["username"], "password": creds["password"]},
    )
    if login.status_code != 200:
        qa.record("concurrent_rsvp_parent_login", False, login.text[:120])
        return
    parent_token = login.json()["access_token"]

    limits = httpx.Limits(max_connections=20)
    async with httpx.AsyncClient(base_url=qa.base, timeout=30.0, limits=limits) as client:
        async def rsvp_once(status: str) -> int:
            r = await client.post(
                f"/events/{state.event_id}/rsvp",
                headers=auth_headers(parent_token),
                json={"responses": [{"student_id": child_id, "status": status}]},
            )
            return r.status_code

        tasks = [rsvp_once(random.choice(["yes", "no", "maybe"])) for _ in range(12)]
        codes = await asyncio.gather(*tasks)
        ok_codes = sum(1 for c in codes if c == 200)
        qa.record("concurrent_rsvp_all_ok", ok_codes == len(codes), f"ok={ok_codes}/{len(codes)}")

        detail = await client.get(f"/events/{state.event_id}", headers=auth_headers(state.trainer_token))
        if detail.status_code == 200:
            summ = detail.json().get("rsvp_summary") or {}
            parts = summ.get("participants", [])
            child_rows = [p for p in parts if p.get("student_id") == child_id]
            unique = len(child_rows) == 1
            qa.record("concurrent_rsvp_unique_row", unique, f"child_rows={len(child_rows)}")
        else:
            qa.record("concurrent_rsvp_unique_row", False, f"detail HTTP {detail.status_code}")


def run_qa(base: str) -> int:
    qa = QAClient(base)
    state = SeedState()

    print(f"Full-app QA @ {base}")
    print(f"TAG={TAG}")

    health = qa.client.get("/health")
    qa.require("health", health)

    if not seed_data(qa, state):
        print("\nSeed failed — aborting tests.")
        qa.close()
        return 1

    test_admin_dashboard(qa, state)
    test_admin_exports(qa, state)
    test_admin_event_participation(qa, state)
    test_trainer_calendar_flow(qa, state)
    test_empty_month_report(qa, state)
    test_guest_on_session(qa, state)
    test_delete_student_with_attendance(qa, state)
    asyncio.run(test_concurrent_rsvp(qa, state))

    print("\n== PASS/FAIL MATRIX ==")
    passed = failed = 0
    for c in qa.checks:
        print(c)
        if c.passed:
            passed += 1
        else:
            failed += 1
    print(f"\nTotal: {passed} passed, {failed} failed, {len(qa.checks)} checks")
    qa.close()
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-app QA for judo backend")
    parser.add_argument("--base", default=BASE_URL, help="API base URL")
    args = parser.parse_args()
    sys.exit(run_qa(args.base.rstrip("/")))


if __name__ == "__main__":
    main()
