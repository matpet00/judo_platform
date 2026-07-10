import pytest

from tests.conftest import login_parent, write_headers

PARENT_PASSWORD = "testpass"


@pytest.mark.asyncio
async def test_parent_profile_patch_requires_token(client):
    response = await client.patch("/parents/me", json={"phone": "+420601111111"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_parent_profile_patch_updates_contact(client):
    token = await login_parent(client)
    response = await client.patch(
        "/parents/me",
        json={
            "first_name": "Marie",
            "last_name": "Testova",
            "email": "marie.testova@example.com",
            "phone": "+420602222222",
        },
        headers=write_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["last_name"] == "Testova"
    assert body["email"] == "marie.testova@example.com"
    assert body["phone"] == "+420602222222"

    me = await client.get("/parents/me", headers=write_headers(token))
    assert me.json()["email"] == "marie.testova@example.com"


@pytest.mark.asyncio
async def test_parent_profile_patch_duplicate_email(client):
    token = await login_parent(client)
    await client.post(
        "/parents",
        headers={"X-API-Key": "test-api-key"},
        json={
            "first_name": "Other",
            "last_name": "Parent",
            "email": "taken@example.com",
            "phone": "+420603333333",
        },
    )
    response = await client.patch(
        "/parents/me",
        json={"email": "taken@example.com"},
        headers=write_headers(token),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_parent_profile_patch_invalid_phone(client):
    token = await login_parent(client)
    response = await client.patch(
        "/parents/me",
        json={"phone": "123"},
        headers=write_headers(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_parent_change_password_requires_token(client):
    response = await client.post(
        "/parents/me/change-password",
        json={"current_password": PARENT_PASSWORD, "new_password": "newpass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_parent_change_password_success(client):
    token = await login_parent(client)
    response = await client.post(
        "/parents/me/change-password",
        json={"current_password": PARENT_PASSWORD, "new_password": "newpass9"},
        headers=write_headers(token),
    )
    assert response.status_code == 204

    login = await client.post(
        "/parents/login",
        json={"username": "testparent", "password": "newpass9"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_parent_change_password_wrong_current(client):
    token = await login_parent(client)
    response = await client.post(
        "/parents/me/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass9"},
        headers=write_headers(token),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_parent_change_password_too_short(client):
    token = await login_parent(client)
    response = await client.post(
        "/parents/me/change-password",
        json={"current_password": PARENT_PASSWORD, "new_password": "abc"},
        headers=write_headers(token),
    )
    assert response.status_code == 422
