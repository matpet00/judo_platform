#!/usr/bin/env python3
"""Smoke test docházky proti běžícímu API."""

from __future__ import annotations

import os
import sys
from datetime import date

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
API_KEY = os.environ.get("API_WRITE_KEY", "")
PIN = os.environ.get("TRAINER_PIN", "1234")


def headers(token: str | None = None, write: bool = False) -> dict[str, str]:
    h: dict[str, str] = {}
    if write and API_KEY:
        h["X-API-Key"] = API_KEY
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fail(message: str, response: httpx.Response | None = None) -> None:
    detail = ""
    if response is not None:
        detail = f" ({response.status_code}) {response.text[:300]}"
    print(f"FAIL: {message}{detail}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        health = client.get("/health")
        if health.status_code != 200:
            fail("GET /health", health)

        trainers = client.get("/trainers")
        if trainers.status_code != 200 or not trainers.json():
            fail("GET /trainers", trainers)
        trainer_id = trainers.json()[0]["id"]

        pin_resp = client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": PIN})
        if pin_resp.status_code != 200:
            fail("verify-pin", pin_resp)
        token = pin_resp.json()["access_token"]

        groups = client.get("/training-groups", headers=headers(token))
        if groups.status_code != 200 or not groups.json():
            fail("GET /training-groups", groups)
        group = groups.json()[0]
        group_id = group["id"]
        student_ids = [s["id"] for s in group["students"]]
        if not student_ids:
            fail("training group has no students")

        session_resp = client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": str(date.today())},
            headers=headers(token, write=True),
        )
        if session_resp.status_code not in (200, 201):
            fail("open session", session_resp)
        session_id = session_resp.json()["id"]

        for student_id in student_ids:
            detail_before = client.get(f"/training-sessions/{session_id}", headers=headers(token)).json()
            existing = next(
                (s["attendance"] for s in detail_before["students"] if s["id"] == student_id),
                None,
            )

            if existing:
                attendance_id = existing["id"]
                patch = client.patch(
                    f"/training-sessions/{session_id}/attendance/{attendance_id}",
                    json={"status": "excused"},
                    headers=headers(token, write=True),
                )
                if patch.status_code != 200:
                    fail(f"PATCH attendance student {student_id}", patch)
                continue

            create = client.post(
                f"/training-sessions/{session_id}/attendance",
                json={"student_id": student_id, "status": "present"},
                headers=headers(token, write=True),
            )
            if create.status_code == 201:
                attendance_id = create.json()["id"]
            elif create.status_code == 409:
                detail_retry = client.get(f"/training-sessions/{session_id}", headers=headers(token)).json()
                row = next(s for s in detail_retry["students"] if s["id"] == student_id)
                if not row.get("attendance"):
                    fail(f"POST 409 but no attendance for student {student_id}", create)
                attendance_id = row["attendance"]["id"]
            else:
                fail(f"POST attendance student {student_id}", create)
            patch = client.patch(
                f"/training-sessions/{session_id}/attendance/{attendance_id}",
                json={"status": "excused"},
                headers=headers(token, write=True),
            )
            if patch.status_code != 200:
                fail(f"PATCH attendance student {student_id}", patch)

        detail = client.get(f"/training-sessions/{session_id}", headers=headers(token))
        if detail.status_code != 200:
            fail("GET session detail", detail)

        marked = sum(1 for s in detail.json()["students"] if s["attendance"] is not None)
        if marked != len(student_ids):
            fail(f"expected {len(student_ids)} marked, got {marked}")

    print(f"OK: smoke passed for {len(student_ids)} students on session {session_id}")


if __name__ == "__main__":
    main()
