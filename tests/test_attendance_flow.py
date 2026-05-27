from datetime import date

import pytest

from tests.conftest import DEFAULT_PIN, first_group_id, login_trainer, write_headers


@pytest.mark.asyncio
async def test_attendance_post_patch_and_conflict(client):
    token = await login_trainer(client)
    group_id = await first_group_id(client)

    session_resp = await client.post(
        f"/training-groups/{group_id}/sessions",
        json={"session_date": str(date.today())},
        headers=write_headers(token),
    )
    assert session_resp.status_code in (200, 201)
    session_id = session_resp.json()["id"]

    detail = await client.get(f"/training-sessions/{session_id}")
    students = detail.json()["students"]
    assert students
    student_id = students[0]["id"]

    create = await client.post(
        f"/training-sessions/{session_id}/attendance",
        json={"student_id": student_id, "status": "present"},
        headers=write_headers(token),
    )
    assert create.status_code == 201
    attendance_id = create.json()["id"]

    duplicate = await client.post(
        f"/training-sessions/{session_id}/attendance",
        json={"student_id": student_id, "status": "absent"},
        headers=write_headers(token),
    )
    assert duplicate.status_code == 409

    patch = await client.patch(
        f"/training-sessions/{session_id}/attendance/{attendance_id}",
        json={"status": "excused"},
        headers=write_headers(token),
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "excused"


@pytest.mark.asyncio
async def test_attendance_roster_flow(client):
    token = await login_trainer(client)
    group_id = await first_group_id(client)

    session_resp = await client.post(
        f"/training-groups/{group_id}/sessions",
        json={"session_date": str(date.today())},
        headers=write_headers(token),
    )
    session_id = session_resp.json()["id"]
    students = (await client.get(f"/training-sessions/{session_id}")).json()["students"]

    for student in students[:5]:
        response = await client.post(
            f"/training-sessions/{session_id}/attendance",
            json={"student_id": student["id"], "status": "present"},
            headers=write_headers(token),
        )
        assert response.status_code == 201

        patch = await client.patch(
            f"/training-sessions/{session_id}/attendance/{response.json()['id']}",
            json={"status": "absent"},
            headers=write_headers(token),
        )
        assert patch.status_code == 200


@pytest.mark.asyncio
async def test_write_requires_api_key(client):
    token = await login_trainer(client)
    group_id = await first_group_id(client)

    response = await client.post(
        f"/training-groups/{group_id}/sessions",
        json={"session_date": str(date.today())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_pin(client):
    response = await client.post("/trainers/1/verify-pin", json={"pin": "0000"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_pin_returns_token(client):
    response = await client.post("/trainers/1/verify-pin", json={"pin": DEFAULT_PIN})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["trainer_id"] == 1
