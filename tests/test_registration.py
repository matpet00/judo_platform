from datetime import date

import pytest

from app.age_group import age_at_year_end, compute_age_group
from app.models import AgeGroup
from app.parent_credentials import build_username_base, name_part
from app.phone import validate_e164_phone
from tests.conftest import login_admin, write_headers


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
async def test_age_group_preview_defaults_to_current_year(client):
    year = date.today().year
    birth_year = year - 9
    resp = await client.get("/age-group", params={"birth_date": f"{birth_year}-05-10"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reference_year"] == year
    assert data["age_group"] == "U10"



@pytest.mark.asyncio
async def test_registration_lookup_endpoints_removed(client):
    parent_status = await client.get("/register/parent-status", params={"email": "x@example.com"})
    assert parent_status.status_code == 404

    birth_status = await client.get(
        "/register/birth-number-status",
        params={"birth_number": "170510/1234"},
    )
    assert birth_status.status_code == 404

    legacy_status = await client.get("/register/status", params={"email": "x@example.com"})
    assert legacy_status.status_code == 405


@pytest.mark.asyncio
async def test_register_status_hides_unknown_and_approved_emails(client, monkeypatch):
    generated_password = "testpass9"
    monkeypatch.setattr(
        "app.registration_service.generate_password",
        lambda length=8: generated_password,
    )

    branch_id = (await client.get("/branches")).json()[0]["id"]
    email = "hidden.status@example.com"

    unknown = await client.post("/register/status", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200
    assert unknown.json()["status"] == "unavailable"

    reg = await client.post(
        "/register",
        json=_parent(
            email=email,
            children=[_child(branch_id, birth_number="170510/2010")],
        ),
    )
    request_id = reg.json()["request_id"]
    admin = await login_admin(client)
    await client.post(
        f"/admin/registration-requests/{request_id}/approve",
        headers=write_headers(admin),
    )

    approved_lookup = await client.post("/register/status", json={"email": email})
    assert approved_lookup.status_code == 200
    assert approved_lookup.json()["status"] == "unavailable"
    assert approved_lookup.json() == unknown.json()


@pytest.mark.asyncio
async def test_register_then_approve_username_collision_gets_suffix(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]
    admin = await login_admin(client)

    first = await client.post(
        "/register",
        json=_parent(
            email="first.novak@example.com",
            parent_first_name="Jan",
            parent_last_name="Novák",
            children=[_child(branch_id, birth_number="170510/2001")],
        ),
    )
    first_id = first.json()["request_id"]
    first_approve = await client.post(
        f"/admin/registration-requests/{first_id}/approve",
        headers=write_headers(admin),
    )
    assert first_approve.status_code == 200
    assert first_approve.json()["username"] == "novjan"

    second = await client.post(
        "/register",
        json=_parent(
            email="second.novak@example.com",
            parent_first_name="Jan",
            parent_last_name="Novák",
            children=[_child(branch_id, first_name="Tom", birth_number="170510/2002")],
        ),
    )
    second_id = second.json()["request_id"]
    second_approve = await client.post(
        f"/admin/registration-requests/{second_id}/approve",
        headers=write_headers(admin),
    )
    assert second_approve.status_code == 200
    assert second_approve.json()["username"] == "novjan2"


@pytest.mark.asyncio
async def test_parent_email_status_after_approval(client):
    branches = (await client.get("/branches")).json()
    branch_id = branches[0]["id"]
    email = "test.rodic@example.com"
    reg = await client.post(
        "/register",
        json=_parent(
            email=email,
            parent_first_name="Test",
            parent_last_name="Rodič",
            children=[_child(branch_id, first_name="Dítě", last_name="Test", birth_date="2019-01-01", birth_number="190101/2003")],
        ),
    )
    admin = await login_admin(client)
    await client.post(
        f"/admin/registration-requests/{reg.json()['request_id']}/approve",
        headers=write_headers(admin),
    )

    hidden = await client.post("/register/status", json={"email": email})
    assert hidden.json()["status"] == "unavailable"
