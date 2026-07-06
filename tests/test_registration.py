from datetime import date

import pytest
from sqlalchemy import select

from app.age_group import age_at_year_end, compute_age_group
from app.database import async_session_maker
from app.models import AgeGroup, Parent
from app.parent_credentials import build_username_base, name_part
from app.phone import validate_e164_phone
from app.security import verify_pin


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+420601234567", "+420601234567"),
        ("+420 601 234 567", "+420601234567"),
        ("+1 (415) 555-2671", "+14155552671"),
    ],
)
def test_validate_e164_phone_accepts_standard_formats(raw: str, expected: str) -> None:
    assert validate_e164_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["601234567", "420601234567", "+", "+420", "00420601234567"],
)
def test_validate_e164_phone_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError, match="\\+"):
        validate_e164_phone(raw)


def test_name_part_strips_diacritics() -> None:
    assert name_part("Nováková") == "nov"
    assert name_part("Jan") == "jan"
    assert build_username_base("Nováková", "Jan") == "novjan"


@pytest.mark.parametrize(
    ("birth", "year", "expected"),
    [
        (date(2019, 3, 15), 2026, AgeGroup.U8),
        (date(2018, 1, 1), 2026, AgeGroup.U10),
        (date(2017, 6, 1), 2026, AgeGroup.U10),
        (date(2016, 12, 31), 2026, AgeGroup.U12),
        (date(2015, 5, 1), 2026, AgeGroup.U12),
        (date(2013, 8, 20), 2026, AgeGroup.U14),
        (date(2011, 2, 10), 2026, AgeGroup.U16),
        (date(2009, 7, 4), 2026, AgeGroup.U18),
    ],
)
def test_compute_age_group_czech_calendar_year(birth: date, year: int, expected: AgeGroup) -> None:
    assert age_at_year_end(birth, year) == year - birth.year
    assert compute_age_group(birth, year) == expected


def test_compute_age_group_uses_current_year_by_default() -> None:
    year = date.today().year
    birth = date(year - 9, 6, 1)
    assert compute_age_group(birth) == AgeGroup.U10


def _child(branch_id: int, **overrides: object) -> dict:
    base = {
        "first_name": "Pepa",
        "last_name": "Novák",
        "birth_date": "2017-05-10",
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


@pytest.mark.asyncio
async def test_register_generates_username_and_stores_password(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]

    resp = await client.post(
        "/register",
        json=_parent(
            email="jana.novakova@example.com",
            parent_first_name="Jana",
            parent_last_name="Nováková",
            children=[_child(branch_id, first_name="Ema", last_name="Nováková")],
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["credentials_created"] is True
    assert data["username"] == "novjan"
    assert data["password"]
    assert len(data["password"]) == 8

    async with async_session_maker() as session:
        parent = (
            await session.execute(select(Parent).where(Parent.email == "jana.novakova@example.com"))
        ).scalar_one()
        assert parent.username == "novjan"
        assert parent.password_plain == data["password"]
        assert verify_pin(data["password"], parent.password_hash)


@pytest.mark.asyncio
async def test_register_username_collision_gets_suffix(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]

    first = await client.post(
        "/register",
        json=_parent(
            email="first.novak@example.com",
            parent_first_name="Jan",
            parent_last_name="Novák",
            children=[_child(branch_id)],
        ),
    )
    assert first.status_code == 200
    assert first.json()["username"] == "novjan"

    second = await client.post(
        "/register",
        json=_parent(
            email="second.novak@example.com",
            parent_first_name="Jan",
            parent_last_name="Novák",
            children=[_child(branch_id, first_name="Tom")],
        ),
    )
    assert second.status_code == 200
    assert second.json()["username"] == "novjan2"


@pytest.mark.asyncio
async def test_register_rejects_invalid_phone(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]

    resp = await client.post(
        "/register",
        json=_parent(
            email="jan.badphone@example.com",
            phone="601234567",
            children=[_child(branch_id)],
        ),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_with_second_guardian_gets_credentials(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]

    resp = await client.post(
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
            children=[_child(branch_id, first_name="Ema", last_name="Králová")],
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["credentials_created"] is True
    assert data["username"] == build_username_base("Králová", "Anna")
    assert data["second_guardian"]["username"] == build_username_base("Král", "Pavel")
    assert data["second_guardian"]["credentials_created"] is True
    assert data["second_guardian"]["password"]

    async with async_session_maker() as session:
        second = (
            await session.execute(select(Parent).where(Parent.email == "pavel.kral@example.com"))
        ).scalar_one()
        assert second.username == build_username_base("Král", "Pavel")
        assert second.password_plain == data["second_guardian"]["password"]
        assert verify_pin(data["second_guardian"]["password"], second.password_hash)

    student = data["students"][0]
    parent_emails = {p["email"] for p in student["parents"]}
    assert parent_emails == {"anna.kralova@example.com", "pavel.kral@example.com"}


@pytest.mark.asyncio
async def test_register_existing_parent_reuses_account(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]

    first = await client.post(
        "/register",
        json=_parent(
            email="marie.dvorakova@example.com",
            parent_first_name="Marie",
            parent_last_name="Dvořáková",
            children=[_child(branch_id, first_name="Klára", last_name="Dvořáková", birth_date="2018-04-12")],
        ),
    )
    assert first.status_code == 200
    parent_id = first.json()["parent_id"]
    first_username = first.json()["username"]

    second = await client.post(
        "/register",
        json=_parent(
            email="marie.dvorakova@example.com",
            phone="+420609999999",
            children=[_child(branch_id, first_name="Filip", last_name="Dvořáková", birth_date="2016-08-01")],
        ),
    )
    assert second.status_code == 200
    data = second.json()
    assert data["existing_parent"] is True
    assert data["parent_id"] == parent_id
    assert data["credentials_created"] is False
    assert data["password"] is None
    assert data["username"] == first_username

    parents = (await client.get("/parents", headers={"X-API-Key": "test-api-key"})).json()
    marie_rows = [p for p in parents if p["email"] == "marie.dvorakova@example.com"]
    assert len(marie_rows) == 1


@pytest.mark.asyncio
async def test_age_group_preview_defaults_to_current_year(client):
    year = date.today().year
    birth_year = year - 9
    resp = await client.get("/age-group", params={"birth_date": f"{birth_year}-05-10"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reference_year"] == year
    assert data["age_group"] == "U10"


@pytest.mark.asyncio
async def test_parent_email_status(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]
    await client.post(
        "/register",
        json=_parent(
            email="test.rodic@example.com",
            parent_first_name="Test",
            parent_last_name="Rodič",
            children=[_child(branch_id, first_name="Dítě", last_name="Test", birth_date="2019-01-01")],
        ),
    )

    unknown = await client.get("/register/parent-status", params={"email": "neexistuje@example.com"})
    assert unknown.json() == {"exists": False, "has_login": False}

    known = await client.get("/register/parent-status", params={"email": "test.rodic@example.com"})
    assert known.json() == {"exists": True, "has_login": True}
