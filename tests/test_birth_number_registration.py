import pytest
from sqlalchemy import select

from app.birth_number import validate_birth_number
from app.database import async_session_maker
from app.models import Student
from tests.conftest import admin_headers, login_admin, write_headers


def test_validate_birth_number_requires_slash() -> None:
    with pytest.raises(ValueError, match="lomítko"):
        validate_birth_number("1705101234")


def test_validate_birth_number_accepts_standard_format() -> None:
    assert validate_birth_number("170510/1234") == "170510/1234"
    assert validate_birth_number("170510/123") == "170510/123"


@pytest.mark.parametrize("raw", ["17051/1234", "170510123/4", "abcdef/ghi"])
def test_validate_birth_number_rejects_invalid_format(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_birth_number(raw)


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
async def test_register_rejects_birth_number_without_slash(client):
    branch_id = await _branch_id(client)
    resp = await client.post(
        "/register",
        json=_parent(
            email="no.slash@example.com",
            children=[_child(branch_id, birth_number="1705101234")],
        ),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_stores_birth_number_in_pending_payload(client):
    branch_id = await _branch_id(client)
    resp = await client.post(
        "/register",
        json=_parent(
            email="payload.rc@example.com",
            children=[_child(branch_id, birth_number="170510/5678", health_insurance="OZP")],
        ),
    )
    assert resp.status_code == 200
    request_id = resp.json()["request_id"]
    admin = await login_admin(client)
    detail = await client.get(
        f"/admin/registration-requests/{request_id}",
        headers=write_headers(admin),
    )
    assert detail.status_code == 200
    child = detail.json()["children"][0]
    assert child["birth_number"] == "170510/5678"
    assert child["health_insurance"] == "OZP"


@pytest.mark.asyncio
async def test_register_rejects_duplicate_birth_number_in_db(client):
    branch_id = await _branch_id(client)
    existing = await client.post(
        "/students",
        headers=await admin_headers(client),
        json={
            "first_name": "Exist",
            "last_name": "Student",
            "age_group": "U10",
            "birth_number": "150101/9999",
            "health_insurance": "VZP ČR",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "Par",
                "last_name": "Ent",
                "email": "parent.exist@example.com",
                "phone": "+420601222222",
            }],
        },
    )
    assert existing.status_code == 200

    duplicate = await client.post(
        "/register",
        json=_parent(
            email="dup.rc@example.com",
            children=[_child(branch_id, birth_number="150101/9999")],
        ),
    )
    assert duplicate.status_code == 409
    assert "rodným číslem" in duplicate.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_rejects_duplicate_birth_numbers_in_one_request(client):
    branch_id = await _branch_id(client)
    resp = await client.post(
        "/register",
        json=_parent(
            email="dup.form@example.com",
            children=[
                _child(branch_id, first_name="A", birth_number="160202/1111"),
                _child(branch_id, first_name="B", birth_number="160202/1111"),
            ],
        ),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_birth_number_status_endpoint(client):
    available = await client.get("/register/birth-number-status", params={"birth_number": "180303/4444"})
    assert available.status_code == 200
    assert available.json()["available"] is True

    branch_id = await _branch_id(client)
    await client.post(
        "/students",
        headers=await admin_headers(client),
        json={
            "first_name": "Taken",
            "last_name": "RC",
            "age_group": "U10",
            "birth_number": "180303/4444",
            "health_insurance": "RBP",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "P",
                "last_name": "T",
                "email": "taken.rc@example.com",
                "phone": "+420601333333",
            }],
        },
    )
    taken = await client.get("/register/birth-number-status", params={"birth_number": "180303/4444"})
    assert taken.json()["available"] is False


@pytest.mark.asyncio
async def test_admin_approve_persists_birth_number_and_insurance(client):
    branch_id = await _branch_id(client)
    reg = await client.post(
        "/register",
        json=_parent(
            email="approve.rc@example.com",
            children=[_child(branch_id, birth_number="190404/5555", health_insurance="ČPZP")],
        ),
    )
    request_id = reg.json()["request_id"]
    admin = await login_admin(client)
    approved = await client.post(
        f"/admin/registration-requests/{request_id}/approve",
        headers=write_headers(admin),
    )
    assert approved.status_code == 200
    student = approved.json()["students"][0]
    assert student["birth_number"] == "190404/5555"
    assert student["health_insurance"] == "ČPZP"

    async with async_session_maker() as session:
        row = (
            await session.execute(select(Student).where(Student.birth_number == "190404/5555"))
        ).scalar_one()
        assert row.health_insurance == "ČPZP"


@pytest.mark.asyncio
async def test_admin_patch_student_rejects_duplicate_birth_number(client):
    branch_id = await _branch_id(client)
    first = await client.post(
        "/students",
        headers=await admin_headers(client),
        json={
            "first_name": "One",
            "last_name": "Kid",
            "age_group": "U10",
            "birth_number": "200505/1111",
            "health_insurance": "VZP ČR",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "A",
                "last_name": "B",
                "email": "one.kid@example.com",
                "phone": "+420601444444",
            }],
        },
    )
    second = await client.post(
        "/students",
        headers=await admin_headers(client),
        json={
            "first_name": "Two",
            "last_name": "Kid",
            "age_group": "U10",
            "birth_number": "200505/2222",
            "health_insurance": "OZP",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "C",
                "last_name": "D",
                "email": "two.kid@example.com",
                "phone": "+420601555555",
            }],
        },
    )
    patch = await client.patch(
        f"/students/{second.json()['id']}",
        headers=await admin_headers(client),
        json={"birth_number": "200505/1111"},
    )
    assert patch.status_code == 409


@pytest.mark.asyncio
async def test_legacy_student_without_birth_number_still_works(client):
    branch_id = await _branch_id(client)
    resp = await client.post(
        "/students",
        headers=await admin_headers(client),
        json={
            "first_name": "Legacy",
            "last_name": "Kid",
            "age_group": "U10",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "Old",
                "last_name": "Parent",
                "email": "legacy.kid@example.com",
                "phone": "+420601666666",
            }],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["birth_number"] is None
