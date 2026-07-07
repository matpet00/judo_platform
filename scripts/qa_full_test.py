#!/usr/bin/env python3
"""Comprehensive live API QA against judo.db. Tag: QA_FULL."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

TAG = "QA_FULL"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
API_KEY = os.environ.get("API_WRITE_KEY", "")
TRAINER_PIN = os.environ.get("TRAINER_PIN", "1234")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin")
PARENT_USER = os.environ.get("PARENT_USER", "rodic")
PARENT_PASS = os.environ.get("PARENT_PASS", "rodic")
SLOW_MS = 2000


@dataclass
class TestResult:
    name: str
    status: str  # pass | fail | warn
    detail: str = ""
    ms: float = 0.0
    unexpected: str = ""


@dataclass
class Report:
    passed: list[TestResult] = field(default_factory=list)
    failed: list[TestResult] = field(default_factory=list)
    warnings: list[TestResult] = field(default_factory=list)
    performance: list[str] = field(default_factory=list)
    cleanup: dict[str, Any] = field(default_factory=dict)
    created_ids: dict[str, list[int]] = field(default_factory=dict)


def headers(token: str | None = None, write: bool = False) -> dict[str, str]:
    h: dict[str, str] = {}
    if write and API_KEY:
        h["X-API-Key"] = API_KEY
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def track_ids(report: Report, kind: str, obj_id: int) -> None:
    report.created_ids.setdefault(kind, []).append(obj_id)


class QAClient:
    def __init__(self, report: Report) -> None:
        self.report = report
        self.client = httpx.Client(base_url=BASE_URL, timeout=60.0)
        self.admin_token: str | None = None
        self.trainer_token: str | None = None
        self.trainer_id: int | None = None
        self.parent_token: str | None = None
        self.parent_id: int | None = None
        self.timings: list[float] = []

    def close(self) -> None:
        self.client.close()

    def record(
        self,
        name: str,
        ok: bool,
        *,
        detail: str = "",
        ms: float = 0.0,
        unexpected: str = "",
        warn: bool = False,
    ) -> None:
        result = TestResult(name=name, status="pass" if ok else ("warn" if warn else "fail"), detail=detail, ms=ms, unexpected=unexpected)
        if ok:
            self.report.passed.append(result)
        elif warn:
            self.report.warnings.append(result)
        else:
            self.report.failed.append(result)
        if ms >= SLOW_MS:
            self.report.performance.append(f"{name}: {ms:.0f}ms (>{SLOW_MS}ms)")

    def request(
        self,
        name: str,
        method: str,
        path: str,
        *,
        token: str | None = None,
        write: bool = False,
        json_body: Any = None,
        expect: int | tuple[int, ...] = 200,
        params: dict | None = None,
    ) -> httpx.Response | None:
        t0 = time.perf_counter()
        try:
            resp = self.client.request(
                method,
                path,
                headers=headers(token, write=write),
                json=json_body,
                params=params,
            )
        except Exception as exc:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            self.record(name, False, detail=f"{type(exc).__name__}: {exc}", ms=ms)
            return None
        ms = (time.perf_counter() - t0) * 1000
        self.timings.append(ms)
        expected = (expect,) if isinstance(expect, int) else expect
        ok = resp.status_code in expected
        detail = "" if ok else f"HTTP {resp.status_code}: {resp.text[:400]}"
        self.record(name, ok, detail=detail, ms=ms)
        return resp if ok else None


def mon_wed_fri_dates(year: int, month: int) -> list[date]:
    _, last_day = monthrange(year, month)
    out: list[date] = []
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if d.isoweekday() in (1, 3, 5):
            out.append(d)
    return out


def run_tests() -> Report:
    report = Report()
    qa = QAClient(report)
    now = datetime.now(UTC)
    test_month = now.strftime("%Y-%m")
    year, mon = (int(x) for x in test_month.split("-"))
    session_dates = mon_wed_fri_dates(year, mon)

    # --- Health ---
    qa.request("health", "GET", "/health", expect=200)

    # --- Auth: trainer ---
    trainers_resp = qa.request("list trainers", "GET", "/trainers", expect=200)
    trainer_id = None
    if trainers_resp is not None:
        trainers = trainers_resp.json()
        for t in trainers:
            if "QA_FULL" not in t.get("first_name", "") and "QA_FULL" not in t.get("last_name", ""):
                trainer_id = t["id"]
                break
        trainer_id = trainer_id or (trainers[0]["id"] if trainers else None)
    if trainer_id:
        pin_resp = qa.request(
            "trainer login PIN 1234",
            "POST",
            f"/trainers/{trainer_id}/verify-pin",
            json_body={"pin": TRAINER_PIN},
            expect=200,
        )
        if pin_resp is not None:
            qa.trainer_token = pin_resp.json()["access_token"]
            qa.trainer_id = pin_resp.json().get("trainer_id", trainer_id)

    # --- Auth: admin ---
    admin_resp = qa.request(
        "admin login admin/admin",
        "POST",
        "/admin/login",
        json_body={"username": ADMIN_USER, "password": ADMIN_PASS},
        expect=200,
    )
    if admin_resp is not None:
        qa.admin_token = admin_resp.json()["access_token"]

    # --- Auth: parent ---
    parent_resp = qa.request(
        "parent login rodic/rodic",
        "POST",
        "/parents/login",
        json_body={"username": PARENT_USER, "password": PARENT_PASS},
        expect=200,
    )
    if parent_resp is not None:
        qa.parent_token = parent_resp.json()["access_token"]
        qa.parent_id = parent_resp.json().get("parent_id")

    if qa.parent_token:
        qa.request("parent me", "GET", "/parents/me", token=qa.parent_token, expect=200)

    # --- CRUD branches ---
    branch_id: int | None = None
    branch2_id: int | None = None
    branches = qa.client.get("/branches").json() if qa.client.get("/branches").status_code == 200 else []
    orlova_id = next((b["id"] for b in branches if b["name"] == "Orlova"), None)
    lutyne_id = next((b["id"] for b in branches if b["name"] == "Dolni Lutyne"), None)
    petrvald_id = next((b["id"] for b in branches if b["name"] == "Petrvald"), None)
    group_branch_b = lutyne_id or petrvald_id

    create_branch = qa.request(
        "CRUD branch create",
        "POST",
        "/branches",
        write=True,
        json_body={"name": f"{TAG} Branch", "address": f"{TAG} Test Address 1"},
        expect=201,
    )
    if create_branch is not None:
        branch_id = create_branch.json()["id"]
        track_ids(report, "branches", branch_id)

    if branch_id:
        qa.request("CRUD branch read", "GET", f"/branches/{branch_id}", expect=200)
        qa.request(
            "CRUD branch patch",
            "PATCH",
            f"/branches/{branch_id}",
            write=True,
            json_body={"address": f"{TAG} Updated Address"},
            expect=200,
        )

    # --- CRUD trainers ---
    qa_trainer_id: int | None = None
    if branch_id:
        create_trainer = qa.request(
            "CRUD trainer create",
            "POST",
            "/trainers",
            write=True,
            json_body={
                "first_name": TAG,
                "last_name": "Trainer",
                "branch_ids": [branch_id],
            },
            expect=200,
        )
        if create_trainer is not None:
            qa_trainer_id = create_trainer.json()["id"]
            track_ids(report, "trainers", qa_trainer_id)
            qa.request(
                "CRUD trainer patch + set PIN",
                "PATCH",
                f"/trainers/{qa_trainer_id}",
                write=True,
                json_body={"pin": "5678"},
                expect=200,
            )
            qa.request(
                "CRUD trainer verify new PIN",
                "POST",
                f"/trainers/{qa_trainer_id}/verify-pin",
                json_body={"pin": "5678"},
                expect=200,
            )

    # --- CRUD parents ---
    qa_parent_id: int | None = None
    qa_parent_email = f"qa_full_{int(time.time())}@example.com"
    create_parent = qa.request(
        "CRUD parent create",
        "POST",
        "/parents",
        write=True,
        json_body={
            "first_name": TAG,
            "last_name": "Parent",
            "email": qa_parent_email,
            "phone": "+420601111111",
        },
        expect=200,
    )
    if create_parent is not None:
        qa_parent_id = create_parent.json()["id"]
        track_ids(report, "parents", qa_parent_id)
        qa.request(
            "CRUD parent patch",
            "PATCH",
            f"/parents/{qa_parent_id}",
            write=True,
            json_body={"phone": "+420602222222"},
            expect=200,
        )

    # --- CRUD students ---
    student_ids: list[int] = []
    guest_student_id: int | None = None
    if orlova_id:
        for i, ag in enumerate(["U8", "U10", "U12"], start=1):
            payload = {
                "first_name": f"{TAG}",
                "last_name": f"Student{i}",
                "age_group": ag,
                "branch_ids": [orlova_id],
                "parents": [],
            }
            if i == 1 and qa_parent_id:
                payload["parents"] = [
                    {
                        "email": qa_parent_email,
                        "first_name": TAG,
                        "last_name": "Parent",
                        "phone": "+420602222222",
                    }
                ]
            resp = qa.request(
                f"CRUD student create {i}",
                "POST",
                "/students",
                write=True,
                json_body=payload,
                expect=200,
            )
            if resp is not None:
                sid = resp.json()["id"]
                student_ids.append(sid)
                track_ids(report, "students", sid)

        if group_branch_b:
            guest_resp = qa.request(
                "CRUD guest student create",
                "POST",
                "/students",
                write=True,
                json_body={
                    "first_name": TAG,
                    "last_name": "Guest",
                    "age_group": "U10",
                    "branch_ids": [group_branch_b],
                },
                expect=200,
            )
            if guest_resp is not None:
                guest_student_id = guest_resp.json()["id"]
                track_ids(report, "students", guest_student_id)

        if student_ids:
            qa.request(
                "CRUD student patch",
                "PATCH",
                f"/students/{student_ids[0]}",
                write=True,
                json_body={"last_name": f"{TAG} Student1 Updated"},
                expect=200,
            )
            qa.request("CRUD students list", "GET", "/students", expect=200)

    branch_b_students: list[int] = []
    if group_branch_b:
        for i in range(4, 6):
            resp = qa.request(
                f"CRUD student branch B {i}",
                "POST",
                "/students",
                write=True,
                json_body={
                    "first_name": TAG,
                    "last_name": f"Student{i}",
                    "age_group": "U10",
                    "branch_ids": [group_branch_b],
                },
                expect=200,
            )
            if resp is not None:
                sid = resp.json()["id"]
                branch_b_students.append(sid)
                student_ids.append(sid)
                track_ids(report, "students", sid)

    # --- Training groups on 2 branches ---
    group_a_id: int | None = None
    group_b_id: int | None = None
    if qa.trainer_token and orlova_id and student_ids:
        ga = qa.request(
            "training group Orlova Mon/Wed/Fri",
            "POST",
            "/training-groups",
            token=qa.trainer_token,
            write=True,
            json_body={
                "branch_id": orlova_id,
                "name": f"{TAG} Orlova 16:00",
                "start_time": "16:00:00",
                "end_time": "17:30:00",
                "weekdays": [1, 3, 5],
                "student_ids": student_ids[:3],
            },
            expect=201,
        )
        if ga is not None:
            group_a_id = ga.json()["id"]
            track_ids(report, "training_groups", group_a_id)

    if qa.trainer_token and group_branch_b and branch_b_students:
        gb = qa.request(
            f"training group {group_branch_b} Mon/Wed/Fri",
            "POST",
            "/training-groups",
            token=qa.trainer_token,
            write=True,
            json_body={
                "branch_id": group_branch_b,
                "name": f"{TAG} BranchB 17:00",
                "start_time": "17:00:00",
                "end_time": "18:30:00",
                "weekdays": [1, 3, 5],
                "student_ids": branch_b_students,
            },
            expect=201,
        )
        if gb is not None:
            group_b_id = gb.json()["id"]
            track_ids(report, "training_groups", group_b_id)

    # --- Open sessions full month + attendance ---
    session_ids: list[int] = []
    primary_session_id: int | None = None
    if qa.trainer_token and group_a_id:
        open_times: list[float] = []
        for d in session_dates:
            t0 = time.perf_counter()
            resp = qa.client.post(
                f"/training-groups/{group_a_id}/sessions",
                json={"session_date": d.isoformat()},
                headers=headers(qa.trainer_token, write=True),
            )
            open_times.append((time.perf_counter() - t0) * 1000)
            if resp.status_code in (200, 201):
                sid = resp.json()["id"]
                if sid not in session_ids:
                    session_ids.append(sid)
                    track_ids(report, "sessions", sid)
            elif resp.status_code == 409:
                pass
            else:
                qa.record(
                    f"open session {d.isoformat()}",
                    False,
                    detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
        if open_times:
            avg = statistics.mean(open_times)
            p95 = sorted(open_times)[min(len(open_times) - 1, int(0.95 * len(open_times)))]
            qa.record(
                f"open sessions full month ({len(session_dates)} dates)",
                len(session_ids) > 0,
                detail=f"opened {len(session_ids)} sessions, avg {avg:.0f}ms, p95 {p95:.0f}ms",
                ms=sum(open_times),
            )
            if p95 >= SLOW_MS:
                report.performance.append(f"session open p95: {p95:.0f}ms across {len(session_dates)} dates")
        primary_session_id = session_ids[0] if session_ids else None

    # Mark attendance on first session: present/absent/excused + guest
    if qa.trainer_token and primary_session_id and student_ids:
        roster = student_ids[:3]
        statuses = ["present", "absent", "excused"]
        for sid, st in zip(roster, statuses):
            qa.request(
                f"attendance mark {st}",
                "POST",
                f"/training-sessions/{primary_session_id}/attendance",
                token=qa.trainer_token,
                write=True,
                json_body={"student_id": sid, "status": st, "recorded_by_id": qa.trainer_id},
                expect=201,
            )
        if guest_student_id:
            qa.request(
                "attendance guest present",
                "POST",
                f"/training-sessions/{primary_session_id}/attendance",
                token=qa.trainer_token,
                write=True,
                json_body={"student_id": guest_student_id, "status": "present"},
                expect=201,
            )
        qa.request(
            "attendance bulk replace",
            "PUT",
            f"/training-sessions/{primary_session_id}/attendance",
            token=qa.trainer_token,
            write=True,
            json_body={
                "records": [
                    {"student_id": roster[0], "status": "present"},
                    {"student_id": roster[1], "status": "excused"},
                    {"student_id": roster[2], "status": "absent"},
                ]
            },
            expect=200,
        )
        qa.request(
            "session detail after attendance",
            "GET",
            f"/training-sessions/{primary_session_id}",
            expect=200,
        )
        qa.request(
            "list session attendance",
            "GET",
            f"/training-sessions/{primary_session_id}/attendance",
            expect=200,
        )

    # Trainer attendance on session
    if qa.trainer_token and primary_session_id and qa.trainer_id:
        ta = qa.request(
            "trainer attendance create",
            "POST",
            f"/training-sessions/{primary_session_id}/trainer-attendance",
            token=qa.trainer_token,
            write=True,
            json_body={
                "trainer_id": qa.trainer_id,
                "status": "present",
                "recorded_by_id": qa.trainer_id,
            },
            expect=201,
        )
        if ta is not None:
            ta_id = ta.json()["id"]
            qa.request(
                "trainer attendance patch",
                "PATCH",
                f"/training-sessions/{primary_session_id}/trainer-attendance/{ta_id}",
                token=qa.trainer_token,
                write=True,
                json_body={"status": "excused"},
                expect=200,
            )

    # Monthly attendance report
    if qa.trainer_token and group_a_id:
        rep = qa.request(
            "monthly attendance report",
            "GET",
            f"/training-groups/{group_a_id}/attendance-report",
            token=qa.trainer_token,
            params={"month": test_month},
            expect=200,
        )
        if rep is not None:
            data = rep.json()
            if data.get("sessions", 0) == 0 and session_ids:
                qa.record(
                    "monthly report session count",
                    False,
                    unexpected="Report shows 0 sessions but sessions were opened",
                )
            else:
                qa.record("monthly report session count", True, detail=f"sessions={data.get('sessions')}, rows={len(data.get('rows', []))}")

    # --- Events ---
    event_id: int | None = None
    if qa.trainer_token and orlova_id:
        starts = datetime(year, mon, 15, 10, 0, tzinfo=UTC)
        ev = qa.request(
            "event create",
            "POST",
            "/events",
            token=qa.trainer_token,
            write=True,
            json_body={
                "title": f"{TAG} Tournament",
                "description": "QA event",
                "event_type": "tournament",
                "location": "Orlova",
                "starts_at": starts.isoformat().replace("+00:00", "Z"),
                "targets": [{"audience": "trainer"}, {"audience": "parent", "branch_id": orlova_id}],
            },
            expect=201,
        )
        if ev is not None:
            event_id = ev.json()["id"]
            track_ids(report, "events", event_id)
            qa.request("event read", "GET", f"/events/{event_id}", token=qa.trainer_token, expect=200)
            qa.request(
                "event patch",
                "PATCH",
                f"/events/{event_id}",
                token=qa.trainer_token,
                write=True,
                json_body={"description": f"{TAG} updated"},
                expect=200,
            )

    if qa.trainer_token and event_id:
        qa.request(
            "event RSVP trainer yes",
            "POST",
            f"/events/{event_id}/rsvp",
            token=qa.trainer_token,
            write=True,
            json_body={"responses": [{"status": "yes"}]},
            expect=200,
        )

    if qa.parent_token and event_id:
        me = qa.client.get("/parents/me", headers=headers(qa.parent_token)).json()
        children = me.get("children", [])
        if children:
            qa.request(
                "event RSVP student",
                "POST",
                f"/events/{event_id}/rsvp",
                token=qa.parent_token,
                write=True,
                json_body={
                    "responses": [{"student_id": children[0]["id"], "status": "maybe"}],
                },
                expect=200,
            )
        else:
            qa.record("event RSVP student", False, detail="parent has no children", warn=True)

    if qa.admin_token:
        qa.request(
            "admin event-participation",
            "GET",
            "/admin/event-participation",
            token=qa.admin_token,
            params={"month": test_month},
            expect=200,
        )
        csv_resp = qa.client.get(
            "/admin/event-participation.csv",
            headers=headers(qa.admin_token),
            params={"month": test_month},
        )
        ok = csv_resp.status_code == 200 and "QA_FULL" in csv_resp.text
        qa.record(
            "admin event-participation CSV",
            ok,
            detail="" if ok else f"HTTP {csv_resp.status_code}, QA_FULL in body={('QA_FULL' in csv_resp.text)}",
            ms=0,
        )

    # --- Notifications ---
    notif_id: int | None = None
    if qa.trainer_token and orlova_id:
        n = qa.request(
            "notification create",
            "POST",
            "/notifications",
            token=qa.trainer_token,
            write=True,
            json_body={
                "title": f"{TAG} Notice",
                "body": "Test notification body",
                "targets": [{"audience": "parent", "branch_id": orlova_id}],
                "duration_amount": 7,
                "duration_unit": "days",
            },
            expect=201,
        )
        if n is not None:
            notif_id = n.json()["id"]
            track_ids(report, "notifications", notif_id)
            qa.request("notifications list trainer", "GET", "/notifications", token=qa.trainer_token, expect=200)

    if qa.parent_token:
        qa.request("notifications list parent", "GET", "/notifications", token=qa.parent_token, expect=200)
        if notif_id:
            qa.request(
                "notification mark read parent",
                "POST",
                f"/notifications/{notif_id}/read",
                token=qa.parent_token,
                write=True,
                expect=200,
            )
            qa.request(
                "notification comment parent",
                "POST",
                f"/notifications/{notif_id}/comments",
                token=qa.parent_token,
                write=True,
                json_body={"body": f"{TAG} parent comment"},
                expect=201,
            )

    if qa.parent_token and orlova_id:
        pn = qa.request(
            "parent notification to trainers",
            "POST",
            "/notifications/to-trainers",
            token=qa.parent_token,
            write=True,
            json_body={
                "title": f"{TAG} Parent msg",
                "body": "Message to trainers",
                "branch_id": orlova_id,
            },
            expect=201,
        )
        if pn is not None:
            track_ids(report, "notifications", pn.json()["id"])

    # --- Chat ---
    conv_id: int | None = None
    if qa.trainer_token and qa.parent_id:
        sc = qa.request(
            "chat start conversation",
            "POST",
            "/chat/conversations",
            token=qa.trainer_token,
            write=True,
            json_body={"counterpart_kind": "parent", "counterpart_id": qa.parent_id},
            expect=201,
        )
        if sc is not None:
            conv_id = sc.json()["id"]
            track_ids(report, "conversations", conv_id)
            msg = qa.request(
                "chat send message",
                "POST",
                f"/chat/conversations/{conv_id}/messages",
                token=qa.trainer_token,
                write=True,
                json_body={"body": f"{TAG} hello from trainer"},
                expect=201,
            )
            if msg is not None:
                mid = msg.json()["id"]
                qa.request(
                    "chat edit message",
                    "PATCH",
                    f"/chat/conversations/{conv_id}/messages/{mid}",
                    token=qa.trainer_token,
                    write=True,
                    json_body={"body": f"{TAG} edited"},
                    expect=200,
                )
            qa.request("chat list conversations parent", "GET", "/chat/conversations", token=qa.parent_token, expect=200)
            qa.request(
                "chat parent reply",
                "POST",
                f"/chat/conversations/{conv_id}/messages",
                token=qa.parent_token,
                write=True,
                json_body={"body": f"{TAG} reply from parent"},
                expect=201,
            )
            qa.request("chat contacts", "GET", "/chat/contacts", token=qa.trainer_token, expect=200)

    # --- Calendar occurrences ---
    if qa.trainer_token:
        from_d = date(year, mon, 1).isoformat()
        to_d = date(year, mon, monthrange(year, mon)[1]).isoformat()
        occ = qa.request(
            "calendar occurrences trainer",
            "GET",
            "/training-groups/occurrences",
            token=qa.trainer_token,
            params={"from": from_d, "to": to_d},
            expect=200,
        )
        if occ is not None and group_a_id:
            qa_occ = [o for o in occ.json() if o.get("group_id") == group_a_id]
            expected_min = len(session_dates)
            if len(qa_occ) < expected_min:
                qa.record(
                    "occurrences count for QA group",
                    False,
                    unexpected=f"Expected >={expected_min} occurrences, got {len(qa_occ)}",
                )
            else:
                qa.record("occurrences count for QA group", True, detail=f"{len(qa_occ)} occurrences")

    if qa.parent_token:
        qa.request(
            "calendar occurrences parent",
            "GET",
            "/training-groups/occurrences",
            token=qa.parent_token,
            params={"from": from_d, "to": to_d},
            expect=200,
        )

    # Occurrence comments
    if qa.trainer_token and group_a_id and session_dates:
        qa.request(
            "occurrence comment create",
            "POST",
            f"/training-groups/{group_a_id}/occurrences/{session_dates[0].isoformat()}/comments",
            token=qa.trainer_token,
            write=True,
            json_body={"body": f"{TAG} occurrence note"},
            expect=201,
        )
        qa.request(
            "occurrence comments list",
            "GET",
            f"/training-groups/{group_a_id}/occurrences/{session_dates[0].isoformat()}/comments",
            token=qa.trainer_token,
            expect=200,
        )

    # --- Admin stats + charts data ---
    if qa.admin_token:
        stats = qa.request("admin stats", "GET", "/admin/stats", token=qa.admin_token, expect=200)
        if stats is not None:
            s = stats.json()
            required = ["trainers", "students", "parents", "branches", "training_groups", "students_per_branch", "students_per_age_group"]
            missing = [k for k in required if k not in s]
            qa.record(
                "admin stats chart fields",
                len(missing) == 0,
                detail=f"missing: {missing}" if missing else f"trainers={s.get('trainers')}, students={s.get('students')}",
            )
        att_csv = qa.client.get(
            "/admin/attendance.csv",
            headers=headers(qa.admin_token),
            params={"month": test_month},
        )
        qa.record(
            "admin attendance CSV export",
            att_csv.status_code == 200 and len(att_csv.text) > 20,
            detail=f"HTTP {att_csv.status_code}, bytes={len(att_csv.content)}",
        )

    # --- Admin resend parent credentials ---
    if qa.admin_token and qa_parent_id:
        cred = qa.request(
            "admin resend parent credentials",
            "POST",
            f"/admin/parents/{qa_parent_id}/resend-credentials",
            token=qa.admin_token,
            write=True,
            expect=200,
        )
        if cred is not None and cred.json().get("password"):
            qa.record("admin credentials password returned", True, detail="password generated")

    # --- Training groups list / get ---
    if qa.trainer_token and group_a_id:
        qa.request("training groups list", "GET", "/training-groups", token=qa.trainer_token, expect=200)
        qa.request("training group detail", "GET", f"/training-groups/{group_a_id}", token=qa.trainer_token, expect=200)

    # --- Negative / edge checks ---
    bad_admin = qa.client.post("/admin/login", json={"username": "admin", "password": "wrong"})
    qa.record("admin login bad password 401", bad_admin.status_code == 401, detail=f"HTTP {bad_admin.status_code}")

    if trainer_id:
        bad_pin = qa.client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": "0000"})
        qa.record("trainer bad PIN 401", bad_pin.status_code == 401, detail=f"HTTP {bad_pin.status_code}")

    # --- Cleanup ---
    cleanup_errors: list[str] = []
    cleanup_ok = True

    def try_delete(name: str, method: str, path: str, token: str | None = None) -> None:
        nonlocal cleanup_ok
        try:
            resp = qa.client.request(method, path, headers=headers(token, write=True))
            if resp.status_code not in (200, 204, 404):
                cleanup_ok = False
                cleanup_errors.append(f"{name}: HTTP {resp.status_code} {resp.text[:120]}")
        except Exception as exc:  # noqa: BLE001
            cleanup_ok = False
            cleanup_errors.append(f"{name}: {exc}")

    if qa.trainer_token:
        for eid in report.created_ids.get("events", []):
            try_delete(f"delete event {eid}", "DELETE", f"/events/{eid}", qa.trainer_token)
        for gid in report.created_ids.get("training_groups", []):
            try_delete(f"delete group {gid}", "DELETE", f"/training-groups/{gid}", qa.trainer_token)
        for nid in report.created_ids.get("notifications", []):
            try_delete(f"delete notification {nid}", "DELETE", f"/notifications/{nid}", qa.trainer_token)

    for sid in reversed(report.created_ids.get("students", [])):
        try_delete(f"delete student {sid}", "DELETE", f"/students/{sid}", qa.admin_token)

    for tid in report.created_ids.get("trainers", []):
        try_delete(f"delete trainer {tid}", "DELETE", f"/trainers/{tid}")

    for pid in report.created_ids.get("parents", []):
        try_delete(f"delete parent {pid}", "DELETE", f"/parents/{pid}")

    for bid in report.created_ids.get("branches", []):
        try_delete(f"delete branch {bid}", "DELETE", f"/branches/{bid}")

    report.cleanup = {
        "attempted": True,
        "success": cleanup_ok and not cleanup_errors,
        "errors": cleanup_errors,
        "leftover_ids": report.created_ids if cleanup_errors else {},
    }

    if qa.timings:
        report.performance.insert(
            0,
            f"overall: {len(qa.timings)} requests, mean {statistics.mean(qa.timings):.0f}ms, max {max(qa.timings):.0f}ms",
        )

    qa.close()
    return report


def print_report(report: Report) -> None:
    print("=" * 72)
    print(f"QA_FULL Live API Report — {BASE_URL}")
    print("=" * 72)
    print(f"\nPASSED ({len(report.passed)}):")
    for r in report.passed:
        extra = f" — {r.detail}" if r.detail else ""
        slow = f" [{r.ms:.0f}ms]" if r.ms >= 500 else ""
        print(f"  ✓ {r.name}{extra}{slow}")

    if report.warnings:
        print(f"\nWARNINGS ({len(report.warnings)}):")
        for r in report.warnings:
            print(f"  ! {r.name}: {r.detail}")

    print(f"\nFAILED ({len(report.failed)}):")
    for r in report.failed:
        print(f"  ✗ {r.name}: {r.detail}")
        if r.unexpected:
            print(f"    unexpected: {r.unexpected}")

    unexpected = [r for r in report.passed + report.failed + report.warnings if r.unexpected]
    if unexpected:
        print(f"\nUNEXPECTED BEHAVIOR ({len(unexpected)}):")
        for r in unexpected:
            print(f"  ? {r.name}: {r.unexpected}")

    if report.performance:
        print(f"\nPERFORMANCE:")
        for line in report.performance:
            print(f"  • {line}")

    print(f"\nCLEANUP:")
    print(f"  success: {report.cleanup.get('success')}")
    if report.cleanup.get("errors"):
        print("  errors:")
        for e in report.cleanup["errors"]:
            print(f"    - {e}")
        print(f"  leftover QA_FULL ids: {json.dumps(report.cleanup.get('leftover_ids', {}), indent=2)}")
    else:
        print("  all QA_FULL test entities removed")

    print(f"\nSUMMARY: {len(report.passed)} passed, {len(report.failed)} failed, {len(report.warnings)} warnings")
    print("=" * 72)


def main() -> int:
    report = run_tests()
    print_report(report)
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
