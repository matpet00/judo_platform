from datetime import date

import pytest

from app.security import create_admin_token, create_trainer_token
from tests.conftest import login_admin, login_trainer, write_headers


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _session_with_trainer_attendance(
    client,
    trainer_token: str,
    *,
    mark_trainer_id: int,
    status: str,
    session_date: date,
    name: str,
):
    groups = (await client.get("/training-groups", headers=write_headers(trainer_token))).json()
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
                "student_ids": [1],
                "trainer_ids": [],
            },
            headers=write_headers(trainer_token),
        )
    ).json()
    session = (
        await client.post(
            f"/training-groups/{group['id']}/sessions",
            json={"session_date": session_date.isoformat()},
            headers=write_headers(trainer_token),
        )
    ).json()
    mark = await client.post(
        f"/training-sessions/{session['id']}/trainer-attendance",
        json={"trainer_id": mark_trainer_id, "status": status},
        headers=write_headers(trainer_token),
    )
    assert mark.status_code == 201, mark.text
    return group, session


@pytest.mark.asyncio
async def test_trainer_pay_attendance_self_only(client):
    trainer = await login_trainer(client)
    today = date.today()
    d = date(today.year, today.month, min(12, 28))

    await _session_with_trainer_attendance(
        client, trainer, mark_trainer_id=1, status="present", session_date=d, name="Pay self",
    )
    await _session_with_trainer_attendance(
        client, trainer, mark_trainer_id=2, status="present", session_date=d, name="Pay other",
    )

    report = await client.get(
        f"/trainers/me/pay-attendance?date_from={d.isoformat()}&date_to={d.isoformat()}",
        headers=write_headers(trainer),
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["trainer_id"] == 1
    assert body["present"] == 1
    assert body["payable_sessions"] == 1
    assert all(e["trainer_id"] == 1 for e in body["entries"])

    other = create_trainer_token(2)[0]
    other_report = await client.get(
        f"/trainers/me/pay-attendance?date_from={d.isoformat()}&date_to={d.isoformat()}",
        headers=_bearer(other),
    )
    assert other_report.status_code == 200
    other_body = other_report.json()
    assert other_body["trainer_id"] == 2
    assert other_body["present"] == 1
    assert all(e["trainer_id"] == 2 for e in other_body["entries"])


@pytest.mark.asyncio
async def test_trainer_pay_excludes_canceled(client):
    trainer = await login_trainer(client)
    today = date.today()
    d = date(today.year, today.month, min(14, 28))
    _, session = await _session_with_trainer_attendance(
        client, trainer, mark_trainer_id=1, status="present", session_date=d, name="Pay cancel",
    )
    cancel = await client.post(
        f"/training-sessions/{session['id']}/cancel",
        headers=write_headers(trainer),
    )
    assert cancel.status_code == 200

    report = await client.get(
        f"/trainers/me/pay-attendance?date_from={d.isoformat()}&date_to={d.isoformat()}",
        headers=write_headers(trainer),
    )
    assert report.status_code == 200
    body = report.json()
    assert body["present"] == 0
    assert session["id"] not in {e["session_id"] for e in body["entries"]}


@pytest.mark.asyncio
async def test_admin_trainer_pay_csv_multi(client):
    trainer = await login_trainer(client)
    today = date.today()
    d = date(today.year, today.month, min(16, 28))
    await _session_with_trainer_attendance(
        client, trainer, mark_trainer_id=1, status="present", session_date=d, name="Admin pay A",
    )
    await _session_with_trainer_attendance(
        client, trainer, mark_trainer_id=2, status="absent", session_date=d, name="Admin pay B",
    )

    admin = await login_admin(client)
    report = await client.get(
        f"/admin/trainer-pay-attendance?date_from={d.isoformat()}&date_to={d.isoformat()}",
        headers=write_headers(admin),
    )
    assert report.status_code == 200, report.text
    body = report.json()
    by_id = {row["trainer_id"]: row for row in body["trainers"]}
    assert by_id[1]["payable_sessions"] == 1
    assert by_id[2]["present"] == 0
    assert by_id[2]["absent"] == 1

    csv_present = await client.get(
        f"/admin/trainer-pay-attendance.csv?date_from={d.isoformat()}&date_to={d.isoformat()}",
        headers=write_headers(admin),
    )
    assert csv_present.status_code == 200
    assert "přítomen" in csv_present.text
    assert "nepřítomen" not in csv_present.text

    csv_all = await client.get(
        f"/admin/trainer-pay-attendance.csv?date_from={d.isoformat()}&date_to={d.isoformat()}"
        "&include_all_statuses=true",
        headers=write_headers(admin),
    )
    assert csv_all.status_code == 200
    assert "nepřítomen" in csv_all.text

    filtered = await client.get(
        f"/admin/trainer-pay-attendance?date_from={d.isoformat()}&date_to={d.isoformat()}&trainer_id=1",
        headers=write_headers(admin),
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["trainers"]) == 1
    assert filtered.json()["trainers"][0]["trainer_id"] == 1


@pytest.mark.asyncio
async def test_trainer_pay_includes_tournament_rsvp(client):
    from datetime import datetime, timedelta, timezone

    trainer = await login_trainer(client)
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    event = (
        await client.post(
            "/events",
            json={
                "title": "Pay Cup",
                "description": "",
                "event_type": "tournament",
                "location": "Pobocka1",
                "starts_at": starts.isoformat(),
                "targets": [{"audience": "trainer"}],
            },
            headers=write_headers(trainer),
        )
    ).json()
    rsvp = await client.post(
        f"/events/{event['id']}/rsvp",
        json={"responses": [{"status": "yes"}]},
        headers=write_headers(trainer),
    )
    assert rsvp.status_code == 200, rsvp.text

    day = starts.date()
    with_events = await client.get(
        f"/trainers/me/pay-attendance?date_from={day.isoformat()}&date_to={day.isoformat()}"
        "&include_trainings=false&event_types=tournament",
        headers=write_headers(trainer),
    )
    assert with_events.status_code == 200, with_events.text
    body = with_events.json()
    assert body["payable_sessions"] == 1
    assert body["entries"][0]["source"] == "event"
    assert body["entries"][0]["event_type"] == "tournament"
    assert body["entries"][0]["group_name"] == "Pay Cup"

    meeting_only = await client.get(
        f"/trainers/me/pay-attendance?date_from={day.isoformat()}&date_to={day.isoformat()}"
        "&include_trainings=false&event_types=meeting",
        headers=write_headers(trainer),
    )
    assert meeting_only.status_code == 200
    assert meeting_only.json()["payable_sessions"] == 0
    assert meeting_only.json()["entries"] == []


@pytest.mark.asyncio
async def test_trainer_pay_legacy_month(client):
    trainer = await login_trainer(client)
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    response = await client.get(
        f"/trainers/me/pay-attendance?month={month}",
        headers=write_headers(trainer),
    )
    assert response.status_code == 200
    assert response.json()["date_from"].startswith(month)
