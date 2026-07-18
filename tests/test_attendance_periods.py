from datetime import date

import pytest
from fastapi import HTTPException

from app.attendance_report import (
    half_bounds,
    month_label_for_range,
    quarter_bounds,
    resolve_attendance_range,
    season_bounds,
    season_start_year_for_date,
)
from app.security import create_admin_token
from tests.conftest import login_parent, login_trainer, write_headers


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_season_and_half_quarter_bounds():
    assert season_bounds(2025) == (date(2025, 9, 1), date(2026, 6, 30))
    assert half_bounds(2025, 1) == (date(2025, 9, 1), date(2026, 1, 31))
    assert half_bounds(2025, 2) == (date(2026, 2, 1), date(2026, 6, 30))
    assert quarter_bounds(2025, 1) == (date(2025, 9, 1), date(2025, 11, 30))
    assert quarter_bounds(2025, 2) == (date(2025, 12, 1), date(2026, 1, 31))
    assert quarter_bounds(2025, 3) == (date(2026, 2, 1), date(2026, 4, 30))
    assert quarter_bounds(2025, 4) == (date(2026, 5, 1), date(2026, 6, 30))
    assert season_start_year_for_date(date(2026, 3, 15)) == 2025
    assert season_start_year_for_date(date(2025, 10, 1)) == 2025
    assert season_start_year_for_date(date(2026, 7, 1)) == 2025


def test_resolve_attendance_range_month_and_custom():
    assert resolve_attendance_range(month="2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert resolve_attendance_range(date_from=date(2025, 9, 1), date_to=date(2026, 1, 31)) == (
        date(2025, 9, 1),
        date(2026, 1, 31),
    )
    with pytest.raises(HTTPException) as exc:
        resolve_attendance_range(month="2026-02", date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        resolve_attendance_range(date_from=date(2026, 3, 1), date_to=date(2026, 2, 1))
    assert month_label_for_range(date(2026, 2, 1), date(2026, 2, 28)) == "2026-02"
    assert month_label_for_range(date(2025, 9, 1), date(2026, 1, 31)) == ""


async def _create_group_with_session(client, trainer, *, student_ids: list[int], session_date: date, name: str):
    groups = (await client.get("/training-groups", headers=write_headers(trainer))).json()
    branch_id = groups[0]["branch_id"]
    group = (
        await client.post(
            "/training-groups",
            json={
                "branch_id": branch_id,
                "name": name,
                "start_time": "17:00",
                "end_time": "18:30",
                "weekdays": [1, 2, 3, 4, 5, 6, 7],
                "student_ids": student_ids,
                "trainer_ids": [],
            },
            headers=write_headers(trainer),
        )
    ).json()
    session = (
        await client.post(
            f"/training-groups/{group['id']}/sessions",
            json={"session_date": session_date.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()
    return group, session


@pytest.mark.asyncio
async def test_parent_attendance_half_year_range(client):
    trainer = await login_trainer(client)
    parent = await login_parent(client)
    today = date.today()
    start_year = today.year if today.month >= 9 else today.year - 1
    d1 = date(start_year, 10, 5)
    d2 = date(start_year + 1, 1, 10)

    _, s1 = await _create_group_with_session(client, trainer, student_ids=[1], session_date=d1, name="Half A")
    _, s2 = await _create_group_with_session(client, trainer, student_ids=[1], session_date=d2, name="Half B")
    await client.put(
        f"/training-sessions/{s1['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )
    await client.put(
        f"/training-sessions/{s2['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "absent"}]},
        headers=write_headers(trainer),
    )

    hf, ht = half_bounds(start_year, 1)
    report = await client.get(
        f"/parents/me/children/1/attendance?date_from={hf.isoformat()}&date_to={ht.isoformat()}",
        headers=write_headers(parent),
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["date_from"] == hf.isoformat()
    assert body["date_to"] == ht.isoformat()
    assert body["month"] == ""
    assert body["present"] == 1
    assert body["absent"] == 1
    assert body["sessions"] >= 2


@pytest.mark.asyncio
async def test_group_report_date_range(client):
    trainer = await login_trainer(client)
    today = date.today()
    d1 = date(today.year, today.month, min(10, 28))
    d2 = date(today.year, today.month, min(15, 28))
    if d2 <= d1:
        d2 = date(today.year, today.month, min(d1.day + 1, 28))

    group, s1 = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d1, name="Range group",
    )
    await client.post(
        f"/training-groups/{group['id']}/sessions",
        json={"session_date": d2.isoformat()},
        headers=write_headers(trainer),
    )
    await client.put(
        f"/training-sessions/{s1['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )

    only_first = await client.get(
        f"/training-groups/{group['id']}/attendance-report"
        f"?date_from={d1.isoformat()}&date_to={d1.isoformat()}",
        headers=write_headers(trainer),
    )
    assert only_first.status_code == 200, only_first.text
    body = only_first.json()
    assert body["sessions"] == 1
    assert body["date_from"] == d1.isoformat()
    assert body["date_to"] == d1.isoformat()


@pytest.mark.asyncio
async def test_admin_attendance_csv_date_range(client):
    trainer = await login_trainer(client)
    today = date.today()
    d1 = date(today.year, today.month, min(8, 28))
    _, session = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d1, name="CSV range",
    )
    await client.put(
        f"/training-sessions/{session['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )

    admin = create_admin_token()[0]
    csv_resp = await client.get(
        f"/admin/attendance.csv?date_from={d1.isoformat()}&date_to={d1.isoformat()}",
        headers=_bearer(admin),
    )
    assert csv_resp.status_code == 200, csv_resp.text
    text = csv_resp.text
    assert "přítomen" in text
    assert d1.isoformat() in text

    outside = date(d1.year - 2, 6, 1)
    empty = await client.get(
        f"/admin/attendance.csv?date_from={outside.isoformat()}&date_to={outside.isoformat()}",
        headers=_bearer(admin),
    )
    assert empty.status_code == 200
    assert d1.isoformat() not in empty.text


@pytest.mark.asyncio
async def test_legacy_month_still_works(client):
    parent = await login_parent(client)
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    response = await client.get(
        f"/parents/me/children/1/attendance?month={month}",
        headers=write_headers(parent),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == month
    assert body["date_from"].startswith(month)
