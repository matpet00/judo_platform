from datetime import date

import pytest

from tests.conftest import login_parent, write_headers


@pytest.mark.asyncio
async def test_parent_child_patch_requires_token(client):
    response = await client.patch("/parents/me/children/1", json={"first_name": "Jan"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_parent_child_patch_forbidden_for_other_child(client):
    token = await login_parent(client)
    response = await client.patch(
        "/parents/me/children/2",
        json={"first_name": "Hacker"},
        headers=write_headers(token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_child_patch_updates_own_child(client):
    token = await login_parent(client)
    response = await client.patch(
        "/parents/me/children/1",
        json={
            "first_name": "Adam",
            "last_name": "Novak",
            "birth_number": "180315/5678",
            "health_insurance": "OZP",
        },
        headers=write_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Adam"
    assert body["last_name"] == "Novak"
    assert body["birth_number"] == "180315/5678"
    assert body["health_insurance"] == "OZP"

    me = await client.get("/parents/me", headers=write_headers(token))
    assert me.status_code == 200
    child = next(row for row in me.json()["children"] if row["id"] == 1)
    assert child["first_name"] == "Adam"
    assert child["birth_number"] == "180315/5678"


@pytest.mark.asyncio
async def test_parent_child_patch_recalculates_age_group(client):
    token = await login_parent(client)
    response = await client.patch(
        "/parents/me/children/1",
        json={"birth_date": "2015-06-01"},
        headers=write_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["age_group"] == "U12"


@pytest.mark.asyncio
async def test_parent_child_patch_rejects_duplicate_birth_number(client):
    token = await login_parent(client)
    await client.post(
        "/students",
        headers={"X-API-Key": "test-api-key"},
        json={
            "first_name": "Other",
            "last_name": "Kid",
            "age_group": "U10",
            "branch_ids": [1],
            "birth_number": "150101/9999",
        },
    )
    response = await client.patch(
        "/parents/me/children/1",
        json={"birth_number": "150101/9999"},
        headers=write_headers(token),
    )
    assert response.status_code == 409
