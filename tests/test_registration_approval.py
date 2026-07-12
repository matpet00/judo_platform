import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.models import Parent, RegistrationRequest, RegistrationRequestStatus
from app.parent_credentials import build_username_base
from app.security import verify_pin
from tests.conftest import login_admin, write_headers


def _child(branch_id: int, **overrides: object) -> dict:
    base = {
        "first_name": "Pepa",
        "last_name": "Novák",
        "birth_date": "2017-05-10",
        "birth_number": "170510/1234",
        "health_insurance": "VZP ČR",
        "branch_ids": [branch_id],
    }
    base.update(overrides)
    return base


def _parent(**overrides: object) -> dict:
    base = {
        "parent_first_name": "Jan",
        "parent_last_name": "Novák",
        "email": "jan.novak@example.com",
        "phone": "+420601111111",
        "children": [],
    }
    base.update(overrides)
    return base


async def _branch_id(client) -> int:
    return (await client.get("/branches")).json()[0]["id"]


@pytest.mark.asyncio
async def test_register_creates_pending_request_not_parent_login(client):
    branch_id = await _branch_id(client)
    resp = await client.post(
        "/register",
        json=_parent(
            email="pending.parent@example.com",
            children=[_child(branch_id, first_name="Ema", last_name="Nováková", birth_number="170510/1001")],
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] > 0
    assert "přijata" in data["message"].lower() or "zkontroluje" in data["message"].lower()

    async with async_session_maker() as session:
        parent = (
            await session.execute(select(Parent).where(Parent.email == "pending.parent@example.com"))
        ).scalar_one_or_none()
        assert parent is None

        request = await session.get(RegistrationRequest, data["request_id"])
        assert request is not None
        assert request.status == RegistrationRequestStatus.pending


@pytest.mark.asyncio
async def test_register_duplicate_pending_email_returns_409(client):
    branch_id = await _branch_id(client)
    payload = _parent(
        email="dup.pending@example.com",
        children=[_child(branch_id, birth_number="170510/1002")],
    )
    first = await client.post("/register", json=payload)
    assert first.status_code == 200
    second = await client.post("/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_registration_status_endpoints(client):
    branch_id = await _branch_id(client)
    email = "status.check@example.com"
    created = await client.post(
        "/register",
        json=_parent(email=email, children=[_child(branch_id, birth_number="170510/1003")]),
    )
    request_id = created.json()["request_id"]

    pending = await client.get("/register/status", params={"email": email})
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending"
    assert pending.json()["request_id"] == request_id

    none = await client.get("/register/status", params={"email": "unknown@example.com"})
    assert none.json()["status"] == "none"


@pytest.mark.asyncio
async def test_admin_approve_creates_parent_and_login(client, monkeypatch):
    generated_password = "testpass9"
    monkeypatch.setattr(
        "app.registration_service.generate_password",
        lambda length=8: generated_password,
    )

    branch_id = await _branch_id(client)
    email = "approve.me@example.com"
    reg = await client.post(
        "/register",
        json=_parent(
            email=email,
            parent_first_name="Jana",
            parent_last_name="Nováková",
            children=[_child(branch_id, first_name="Ema", last_name="Nováková", birth_number="170510/1004")],
        ),
    )
    request_id = reg.json()["request_id"]
    admin = await login_admin(client)

    approved = await client.post(
        f"/admin/registration-requests/{request_id}/approve",
        headers=write_headers(admin),
    )
    assert approved.status_code == 200
    data = approved.json()
    assert data["credentials_created"] is True
    assert data["username"] == "novjan"
    assert "password" not in data
    assert data["access_token"] is None

    async with async_session_maker() as session:
        parent = (await session.execute(select(Parent).where(Parent.email == email))).scalar_one()
        assert parent.username == "novjan"
        assert verify_pin(generated_password, parent.password_hash)

        request = await session.get(RegistrationRequest, request_id)
        assert request.status == RegistrationRequestStatus.approved
        assert request.approved_parent_id == parent.id

    status = await client.get("/register/status", params={"email": email})
    assert status.json()["status"] == "approved"

    login = await client.post("/parents/login", json={"username": "novjan", "password": generated_password})
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_admin_reject_sets_reason_and_allows_new_request(client):
    branch_id = await _branch_id(client)
    email = "reject.me@example.com"
    reg = await client.post(
        "/register",
        json=_parent(email=email, children=[_child(branch_id, birth_number="170510/1005")]),
    )
    request_id = reg.json()["request_id"]
    admin = await login_admin(client)

    rejected = await client.post(
        f"/admin/registration-requests/{request_id}/reject",
        headers=write_headers(admin),
        json={"reason": "Špatná pobočka"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Špatná pobočka"

    status = await client.get("/register/status", params={"email": email})
    assert status.json()["status"] == "rejected"
    assert status.json()["rejection_reason"] == "Špatná pobočka"

    again = await client.post(
        "/register",
        json=_parent(email=email, children=[_child(branch_id, first_name="Oprava", birth_number="170510/1006")]),
    )
    assert again.status_code == 200

    status_after_resubmit = await client.get("/register/status", params={"email": email})
    assert status_after_resubmit.json()["status"] == "pending"
    assert status_after_resubmit.json()["rejection_reason"] is None


@pytest.mark.asyncio
async def test_admin_approve_with_second_guardian(client):
    branch_id = await _branch_id(client)
    reg = await client.post(
        "/register",
        json=_parent(
            email="anna.kralova@example.com",
            parent_first_name="Anna",
            parent_last_name="Králová",
            second_guardian={
                "first_name": "Pavel",
                "last_name": "Král",
                "email": "pavel.kral@example.com",
                "phone": "+420602222222",
            },
            children=[_child(branch_id, first_name="Ema", last_name="Králová", birth_number="170510/1007")],
        ),
    )
    admin = await login_admin(client)
    approved = await client.post(
        f"/admin/registration-requests/{reg.json()['request_id']}/approve",
        headers=write_headers(admin),
    )
    assert approved.status_code == 200
    data = approved.json()
    assert data["credentials_created"] is True
    assert data["username"] == build_username_base("Králová", "Anna")
    assert data["second_guardian"]["username"] == build_username_base("Král", "Pavel")


@pytest.mark.asyncio
async def test_admin_registration_requests_list(client):
    branch_id = await _branch_id(client)
    await client.post(
        "/register",
        json=_parent(email="list@example.com", children=[_child(branch_id, birth_number="170510/1008")]),
    )
    admin = await login_admin(client)
    listing = await client.get("/admin/registration-requests", headers=write_headers(admin))
    assert listing.status_code == 200
    assert len(listing.json()) >= 1
    assert listing.json()[0]["status"] == "pending"
