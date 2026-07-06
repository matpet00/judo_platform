from datetime import UTC, date, datetime, timedelta

import pytest

from app.reminders import run_reminder_sweep
from app.security import create_parent_token
from tests.conftest import login_trainer, write_headers


def _parent_token(parent_id: int = 1) -> str:
    token, _ = create_parent_token(parent_id)
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _orlova_branch_id(client, trainer) -> int:
    groups = (await client.get("/training-groups", headers=write_headers(trainer))).json()
    return groups[0]["branch_id"]


async def _create_daily_group(client, trainer, **overrides):
    branch_id = await _orlova_branch_id(client, trainer)
    payload = {
        "branch_id": branch_id,
        "name": overrides.get("name", "Denní trénink"),
        "start_time": "17:00",
        "end_time": "18:30",
        "weekdays": [1, 2, 3, 4, 5, 6, 7],
        "active_until": overrides.get("active_until"),
        "student_ids": overrides.get("student_ids", [1, 2]),
    }
    return await client.post("/training-groups", json=payload, headers=write_headers(trainer))


@pytest.mark.asyncio
async def test_occurrences_expand_weekly_and_clip_to_active_until(client):
    trainer = await login_trainer(client)
    today = date.today()
    until = today + timedelta(days=3)
    resp = await _create_daily_group(client, trainer, active_until=until.isoformat())
    assert resp.status_code == 201, resp.text

    frm = today.isoformat()
    to = (today + timedelta(days=10)).isoformat()
    occ = (await client.get(f"/training-groups/occurrences?from={frm}&to={to}", headers=write_headers(trainer))).json()
    dates = sorted({o["date"] for o in occ})
    # Daily weekdays, clipped at active_until (inclusive) -> today..until only.
    assert dates == [(today + timedelta(days=i)).isoformat() for i in range(4)]
    assert all(o["roster_count"] == 2 for o in occ)


@pytest.mark.asyncio
async def test_parent_only_sees_groups_with_their_child(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # owns child id 1
    today = date.today()

    # Group with the parent's child.
    await _create_daily_group(client, trainer, name="S dítětem", student_ids=[1])
    # Group without the parent's child.
    await _create_daily_group(client, trainer, name="Bez dítěte", student_ids=[2])

    frm = today.isoformat()
    to = (today + timedelta(days=2)).isoformat()
    occ = (await client.get(f"/training-groups/occurrences?from={frm}&to={to}", headers=_bearer(parent))).json()
    assert occ
    assert {o["name"] for o in occ} == {"S dítětem"}


@pytest.mark.asyncio
async def test_monthly_attendance_report(client):
    trainer = await login_trainer(client)
    today = date.today()
    group_id = (await _create_daily_group(client, trainer, student_ids=[1, 2])).json()["id"]

    session = (
        await client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": today.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()
    await client.put(
        f"/training-sessions/{session['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}, {"student_id": 2, "status": "absent"}]},
        headers=write_headers(trainer),
    )

    month = f"{today.year}-{today.month:02d}"
    report = (
        await client.get(
            f"/training-groups/{group_id}/attendance-report?month={month}",
            headers=write_headers(trainer),
        )
    ).json()
    by_student = {row["student_id"]: row for row in report["rows"]}
    assert report["sessions"] == 1
    assert by_student[1]["present"] == 1
    assert by_student[2]["absent"] == 1


@pytest.mark.asyncio
async def test_enrollment_notifies_parent(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # parent of child 1
    await _create_daily_group(client, trainer, name="Zápis", student_ids=[1])

    notifs = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert any(n["title"] == "Zařazení do tréninku" for n in notifs)

    # Another parent's group enrollment does not reach this parent.
    other = _parent_token(999)
    other_notifs = (await client.get("/notifications", headers=_bearer(other))).json()
    assert not any(n["title"] == "Zařazení do tréninku" for n in other_notifs)


@pytest.mark.asyncio
async def test_cancel_occurrence_notifies_parent(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    today = date.today()
    group_id = (await _create_daily_group(client, trainer, student_ids=[1])).json()["id"]
    session = (
        await client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": today.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()

    resp = await client.post(
        f"/training-sessions/{session['id']}/cancel?canceled=true",
        headers=write_headers(trainer),
    )
    assert resp.status_code == 200

    notifs = (await client.get("/notifications", headers=_bearer(parent))).json()
    cancel_notifs = [n for n in notifs if n["title"] == "Zrušený trénink"]
    assert len(cancel_notifs) == 1
    cancel_notif = cancel_notifs[0]
    assert cancel_notif["training_group_id"] == group_id
    assert cancel_notif["training_date"] == today.isoformat()

    trainer_notifs = (await client.get("/notifications", headers=write_headers(trainer))).json()
    assert not any(n["title"] == "Zrušený trénink" for n in trainer_notifs)

    other_trainer = await login_trainer(client, trainer_id=2)
    other_trainer_notifs = (await client.get("/notifications", headers=write_headers(other_trainer))).json()
    assert any(n["title"] == "Zrušený trénink" for n in other_trainer_notifs)

    other = _parent_token(999)
    other_notifs = (await client.get("/notifications", headers=_bearer(other))).json()
    assert not any(n["title"] == "Zrušený trénink" for n in other_notifs)


@pytest.mark.asyncio
async def test_delete_training_group_notifies_parent(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    group_id = (await _create_daily_group(client, trainer, student_ids=[1])).json()["id"]

    resp = await client.delete(f"/training-groups/{group_id}", headers=write_headers(trainer))
    assert resp.status_code == 204

    notifs = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert any(n["title"] == "Trénink zrušen" for n in notifs)

    other_trainer = await login_trainer(client, trainer_id=2)
    other_trainer_notifs = (await client.get("/notifications", headers=write_headers(other_trainer))).json()
    assert any(n["title"] == "Trénink zrušen" for n in other_trainer_notifs)

    trainer_notifs = (await client.get("/notifications", headers=write_headers(trainer))).json()
    assert not any(n["title"] == "Trénink zrušen" for n in trainer_notifs)


@pytest.mark.asyncio
async def test_cancel_occurrence_visible_to_parent_in_list_window(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    today = date.today()
    group_id = (await _create_daily_group(client, trainer, student_ids=[1])).json()["id"]
    session = (
        await client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": today.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()
    await client.post(
        f"/training-sessions/{session['id']}/cancel?canceled=true",
        headers=write_headers(trainer),
    )

    frm = (today - timedelta(days=7)).isoformat()
    to = (today + timedelta(days=90)).isoformat()
    occ = (await client.get(f"/training-groups/occurrences?from={frm}&to={to}", headers=_bearer(parent))).json()
    match = [o for o in occ if o["group_id"] == group_id and o["date"] == today.isoformat()]
    assert len(match) == 1
    assert match[0]["canceled"] is True


@pytest.mark.asyncio
async def test_cancel_occurrence(client):
    trainer = await login_trainer(client)
    today = date.today()
    group_id = (await _create_daily_group(client, trainer)).json()["id"]
    session = (
        await client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": today.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()

    resp = await client.post(f"/training-sessions/{session['id']}/cancel?canceled=true", headers=write_headers(trainer))
    assert resp.status_code == 200
    assert resp.json()["canceled"] is True

    frm = today.isoformat()
    occ = (await client.get(f"/training-groups/occurrences?from={frm}&to={frm}", headers=write_headers(trainer))).json()
    match = [o for o in occ if o["group_id"] == group_id]
    assert len(match) == 1
    assert match[0]["canceled"] is True

    restore = await client.post(f"/training-sessions/{session['id']}/cancel?canceled=false", headers=write_headers(trainer))
    assert restore.status_code == 200
    occ = (await client.get(f"/training-groups/occurrences?from={frm}&to={frm}", headers=write_headers(trainer))).json()
    match = [o for o in occ if o["group_id"] == group_id]
    assert match and match[0]["canceled"] is False


@pytest.mark.asyncio
async def test_delete_training_group_cascades_sessions(client):
    trainer = await login_trainer(client)
    today = date.today()
    group_id = (await _create_daily_group(client, trainer)).json()["id"]
    session = (
        await client.post(
            f"/training-groups/{group_id}/sessions",
            json={"session_date": today.isoformat()},
            headers=write_headers(trainer),
        )
    ).json()
    await client.put(
        f"/training-sessions/{session['id']}/attendance",
        json={"records": [{"student_id": 1, "status": "present"}]},
        headers=write_headers(trainer),
    )

    # Deletion cascades even though sessions/attendance exist.
    resp = await client.delete(f"/training-groups/{group_id}", headers=write_headers(trainer))
    assert resp.status_code == 204

    assert (await client.get(f"/training-groups/{group_id}", headers=write_headers(trainer))).status_code == 404
    assert (await client.get(f"/training-sessions/{session['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_get_training_group_requires_trainer_token(client):
    trainer = await login_trainer(client)
    group_id = (await _create_daily_group(client, trainer)).json()["id"]

    assert (await client.get(f"/training-groups/{group_id}")).status_code == 401
    assert (await client.get(f"/training-groups", headers=write_headers())).status_code == 401

    assert (await client.get(f"/training-groups/{group_id}", headers=write_headers(trainer))).status_code == 200
    assert (await client.get("/training-groups", headers=write_headers(trainer))).status_code == 200


@pytest.mark.asyncio
async def test_patch_training_group_rejects_inverted_active_window(client):
    trainer = await login_trainer(client)
    create = await _create_daily_group(client, trainer)
    group_id = create.json()["id"]

    resp = await client.patch(
        f"/training-groups/{group_id}",
        json={"active_from": "2030-02-01", "active_until": "2030-01-01"},
        headers=write_headers(trainer),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reminder_sweep_notifies_participants_once(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    soon = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    payload = {
        "title": "Turnaj brzy",
        "event_type": "tournament",
        "starts_at": soon,
        "targets": [{"audience": "parent"}, {"audience": "trainer"}],
    }
    event_id = (await client.post("/events", json=payload, headers=write_headers(trainer))).json()["id"]

    processed = await run_reminder_sweep()
    assert processed >= 1

    reminders = [
        n
        for n in (await client.get("/notifications", headers=_bearer(parent))).json()
        if n["event_id"] == event_id and n["title"].startswith("Připomínka")
    ]
    assert len(reminders) == 1
    assert "potvrďte" in reminders[0]["body"].lower()

    # Second sweep is a no-op (reminder_sent guard).
    await run_reminder_sweep()
    reminders_after = [
        n
        for n in (await client.get("/notifications", headers=_bearer(parent))).json()
        if n["event_id"] == event_id and n["title"].startswith("Připomínka")
    ]
    assert len(reminders_after) == 1
