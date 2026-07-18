from datetime import date

import pytest

from app.security import create_parent_token
from tests.conftest import login_parent, login_trainer, write_headers


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _dates_in_month(count: int = 3) -> list[date]:
    """Return `count` distinct dates in the current calendar month."""
    today = date.today()
    days = [d for d in range(1, 29) if date(today.year, today.month, d) <= today or True]
    picks = days[:count]
    while len(picks) < count:
        picks.append(days[-1])
    return [date(today.year, today.month, d) for d in picks]


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
async def test_parent_child_attendance_requires_auth(client):
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    response = await client.get(f"/parents/me/children/1/attendance?month={month}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_parent_cannot_see_other_child_attendance(client):
    token = await login_parent(client)
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    response = await client.get(
        f"/parents/me/children/2/attendance?month={month}",
        headers=write_headers(token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_child_attendance_aggregates_statuses(client):
    trainer = await login_trainer(client)
    parent = await login_parent(client)
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    d1, d2, d3 = _dates_in_month(3)

    _, session_a = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d1, name="PA present",
    )
    _, session_b = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d2, name="PA absent",
    )
    _, session_c = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d3, name="PA unmarked",
    )

    await client.put(
        f"/training-sessions/{session_a['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )
    await client.put(
        f"/training-sessions/{session_b['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "absent"}]},
        headers=write_headers(trainer),
    )

    report = await client.get(
        f"/parents/me/children/1/attendance?month={month}",
        headers=write_headers(parent),
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["student_id"] == 1
    assert body["month"] == month
    assert body["present"] == 1
    assert body["absent"] == 1
    assert body["excused"] == 0
    assert body["sessions"] == 3
    assert body["unmarked"] == 1
    assert body["attendance_rate"] == round((1 / 3) * 100, 1)
    assert len(body["entries"]) == 3
    statuses = {e["session_id"]: e["status"] for e in body["entries"]}
    assert statuses[session_a["id"]] == "present"
    assert statuses[session_b["id"]] == "absent"
    assert statuses[session_c["id"]] is None


@pytest.mark.asyncio
async def test_parent_child_attendance_excludes_canceled(client):
    trainer = await login_trainer(client)
    parent = await login_parent(client)
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    d1, d2, _ = _dates_in_month(3)

    _, session_live = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d1, name="PA live",
    )
    _, session_cancel = await _create_group_with_session(
        client, trainer, student_ids=[1], session_date=d2, name="PA cancel",
    )
    await client.put(
        f"/training-sessions/{session_live['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )
    await client.put(
        f"/training-sessions/{session_cancel['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )
    cancel = await client.post(
        f"/training-sessions/{session_cancel['id']}/cancel",
        headers=write_headers(trainer),
    )
    assert cancel.status_code == 200, cancel.text

    report = await client.get(
        f"/parents/me/children/1/attendance?month={month}",
        headers=write_headers(parent),
    )
    assert report.status_code == 200
    body = report.json()
    ids = {e["session_id"] for e in body["entries"]}
    assert session_live["id"] in ids
    assert session_cancel["id"] not in ids
    assert body["present"] == 1


@pytest.mark.asyncio
async def test_foreign_parent_token_denied(client):
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    foreign = create_parent_token(999)[0]
    response = await client.get(
        f"/parents/me/children/1/attendance?month={month}",
        headers=_bearer(foreign),
    )
    assert response.status_code in (403, 404)
