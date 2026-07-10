from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import DEFAULT_PIN, login_admin, login_trainer, write_headers

NEW_PIN = "5678"
ADMIN_PIN = "9999"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _verify_pin(client, trainer_id: int, pin: str) -> int:
    return (
        await client.post(f"/trainers/{trainer_id}/verify-pin", json={"pin": pin})
    ).status_code


async def _assert_trainer_features(client, token: str) -> None:
    notifs = await client.get("/notifications", headers=write_headers(token))
    assert notifs.status_code == 200

    create_notif = await client.post(
        "/notifications",
        json={
            "title": "PIN test",
            "body": "After PIN change",
            "targets": [{"audience": "trainer"}],
        },
        headers=write_headers(token),
    )
    assert create_notif.status_code == 201

    contacts = await client.get("/chat/contacts", headers=write_headers(token))
    assert contacts.status_code == 200

    convs = await client.get("/chat/conversations", headers=write_headers(token))
    assert convs.status_code == 200

    conv = await client.post(
        "/chat/conversations",
        json={"counterpart_kind": "parent", "counterpart_id": 1},
        headers=write_headers(token),
    )
    assert conv.status_code == 201
    conv_id = conv.json()["id"]

    msg = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "PIN change smoke"},
        headers=write_headers(token),
    )
    assert msg.status_code == 201

    events = await client.get("/events", headers=write_headers(token))
    assert events.status_code == 200

    event_resp = await client.post(
        "/events",
        json={
            "title": "PIN test event",
            "description": "After PIN change",
            "event_type": "training",
            "location": "Orlova",
            "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "targets": [{"audience": "trainer"}],
        },
        headers=write_headers(token),
    )
    assert event_resp.status_code == 201
    event_id = event_resp.json()["id"]

    rsvp = await client.post(
        f"/events/{event_id}/rsvp",
        json={"responses": [{"student_id": None, "status": "maybe"}]},
        headers=write_headers(token),
    )
    assert rsvp.status_code == 200

    groups = await client.get("/training-groups", headers=write_headers(token))
    assert groups.status_code == 200
    assert groups.json()

    group_id = groups.json()[0]["id"]
    session = await client.post(
        f"/training-groups/{group_id}/sessions",
        json={"session_date": datetime.now(UTC).date().isoformat()},
        headers=write_headers(token),
    )
    assert session.status_code in (200, 201)
    session_id = session.json()["id"]

    detail = await client.get(f"/training-sessions/{session_id}")
    assert detail.status_code == 200
    student = detail.json()["students"][0]
    if student.get("attendance"):
        attendance_id = student["attendance"]["id"]
        patch = await client.patch(
            f"/training-sessions/{session_id}/attendance/{attendance_id}",
            json={"status": "present"},
            headers=write_headers(token),
        )
        assert patch.status_code == 200
    else:
        create = await client.post(
            f"/training-sessions/{session_id}/attendance",
            json={"student_id": student["id"], "status": "present"},
            headers=write_headers(token),
        )
        assert create.status_code in (201, 409)


@pytest.mark.asyncio
async def test_trainer_change_pin_success(client):
    token = await login_trainer(client)
    change = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": DEFAULT_PIN, "new_pin": NEW_PIN},
        headers=write_headers(token),
    )
    assert change.status_code == 204
    assert await _verify_pin(client, 1, DEFAULT_PIN) == 401
    assert await _verify_pin(client, 1, NEW_PIN) == 200


@pytest.mark.asyncio
async def test_trainer_change_pin_wrong_current(client):
    token = await login_trainer(client)
    change = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": "0000", "new_pin": NEW_PIN},
        headers=write_headers(token),
    )
    assert change.status_code == 401


@pytest.mark.asyncio
async def test_trainer_change_pin_requires_token(client):
    change = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": DEFAULT_PIN, "new_pin": NEW_PIN},
        headers=write_headers(),
    )
    assert change.status_code == 401


@pytest.mark.asyncio
async def test_admin_patch_pin_overwrites(client):
    admin = await login_admin(client)
    patch = await client.patch(
        "/trainers/2",
        json={"pin": ADMIN_PIN},
        headers=write_headers(admin),
    )
    assert patch.status_code == 200
    assert await _verify_pin(client, 2, ADMIN_PIN) == 200
    assert await _verify_pin(client, 2, DEFAULT_PIN) == 401


@pytest.mark.asyncio
async def test_patch_pin_without_admin_fails(client):
    token = await login_trainer(client)
    patch = await client.patch(
        "/trainers/1",
        json={"pin": "8888"},
        headers=write_headers(token),
    )
    assert patch.status_code == 401


@pytest.mark.asyncio
async def test_old_pin_rejected_after_change(client):
    token = await login_trainer(client)
    change = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": DEFAULT_PIN, "new_pin": NEW_PIN},
        headers=write_headers(token),
    )
    assert change.status_code == 204
    assert await _verify_pin(client, 1, DEFAULT_PIN) == 401


@pytest.mark.asyncio
async def test_trainer_features_work_after_pin_change_and_relogin(client):
    token = await login_trainer(client)
    change = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": DEFAULT_PIN, "new_pin": NEW_PIN},
        headers=write_headers(token),
    )
    assert change.status_code == 204

    new_token = await login_trainer(client, trainer_id=1, pin=NEW_PIN)
    await _assert_trainer_features(client, new_token)


@pytest.mark.asyncio
async def test_admin_pin_overwrite_then_trainer_features_work(client):
    admin = await login_admin(client)
    patch = await client.patch(
        "/trainers/2",
        json={"pin": ADMIN_PIN},
        headers=write_headers(admin),
    )
    assert patch.status_code == 200

    token = await login_trainer(client, trainer_id=2, pin=ADMIN_PIN)
    await _assert_trainer_features(client, token)
