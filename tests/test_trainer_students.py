from datetime import date

import pytest

from tests.conftest import first_group_id, login_trainer, write_headers


async def _branch_id(client, name: str) -> int:
    branches = (await client.get("/branches")).json()
    return next(branch["id"] for branch in branches if branch["name"] == name)


async def _trainer_students(client, token: str, branch_id: int):
    return await client.get(
        f"/trainers/me/students?branch_id={branch_id}",
        headers=write_headers(token),
    )


@pytest.mark.asyncio
async def test_trainer_students_requires_token(client):
    orlova = await _branch_id(client, "Orlova")
    response = await client.get(f"/trainers/me/students?branch_id={orlova}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_trainer_students_forbidden_branch(client):
    token = await login_trainer(client)
    dolni = await _branch_id(client, "Dolni Lutyne")
    response = await _trainer_students(client, token, dolni)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_trainer_sees_roster_students(client):
    token = await login_trainer(client)
    orlova = await _branch_id(client, "Orlova")
    response = await _trainer_students(client, token, orlova)
    assert response.status_code == 200
    body = response.json()
    ids = {student["id"] for student in body}
    assert {1, 2, 3} <= ids
    for student in body:
        if student["id"] in {1, 2, 3}:
            assert student["is_guest"] is False
            assert student["training_groups"] == ["Test 16:00-17:30"]


@pytest.mark.asyncio
async def test_trainer_does_not_see_student_outside_groups(client):
    token = await login_trainer(client)
    orlova = await _branch_id(client, "Orlova")
    dolni = await _branch_id(client, "Dolni Lutyne")

    isolated = await client.post(
        "/students",
        headers=write_headers(),
        json={
            "first_name": "Solo",
            "last_name": "Lutyn",
            "age_group": "U10",
            "branch_ids": [dolni],
        },
    )
    assert isolated.status_code == 200
    isolated_id = isolated.json()["id"]

    response = await _trainer_students(client, token, orlova)
    assert response.status_code == 200
    ids = {student["id"] for student in response.json()}
    assert isolated_id not in ids


@pytest.mark.asyncio
async def test_trainer_without_group_gets_empty_list(client):
    token = await login_trainer(client, trainer_id=2)
    orlova = await _branch_id(client, "Orlova")
    response = await _trainer_students(client, token, orlova)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_guest_from_attendance_appears_as_guest(client):
    token = await login_trainer(client)
    orlova = await _branch_id(client, "Orlova")
    group_id = await first_group_id(client)

    guest = await client.post(
        "/students",
        headers=write_headers(),
        json={
            "first_name": "Host",
            "last_name": "Navstevnik",
            "age_group": "U12",
            "branch_ids": [orlova],
        },
    )
    assert guest.status_code == 200
    guest_id = guest.json()["id"]

    session_resp = await client.post(
        f"/training-groups/{group_id}/sessions",
        json={"session_date": str(date.today())},
        headers=write_headers(token),
    )
    assert session_resp.status_code in (200, 201)
    session_id = session_resp.json()["id"]

    attendance = await client.post(
        f"/training-sessions/{session_id}/attendance",
        json={"student_id": guest_id, "status": "present"},
        headers=write_headers(token),
    )
    assert attendance.status_code == 201

    response = await _trainer_students(client, token, orlova)
    assert response.status_code == 200
    guest_row = next(row for row in response.json() if row["id"] == guest_id)
    assert guest_row["is_guest"] is True
    assert guest_row["training_groups"] == []
    assert guest_row["home_branch"] == "Orlova"
