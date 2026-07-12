import pytest

from app.security import clear_all_rate_limits
from tests.conftest import DEFAULT_PIN, login_admin, login_trainer, write_headers


@pytest.mark.asyncio
async def test_verify_pin_flags_weak_default_pin(client):
    response = await client.post("/trainers/1/verify-pin", json={"pin": DEFAULT_PIN})
    assert response.status_code == 200
    body = response.json()
    assert body["pin_change_required"] is True


@pytest.mark.asyncio
async def test_change_trainer_pin_rejects_short_new_pin(client):
    token = await login_trainer(client, trainer_id=1)
    response = await client.post(
        "/trainers/me/change-pin",
        json={"current_pin": DEFAULT_PIN, "new_pin": "5678"},
        headers=write_headers(token),
    )
    assert response.status_code == 422


def test_pin_policy_marks_default_pin_and_validates_new_pin():
    from app.pin_policy import trainer_pin_change_required, validate_new_trainer_pin

    assert trainer_pin_change_required("1234") is True
    assert trainer_pin_change_required("847291") is False
    with pytest.raises(ValueError):
        validate_new_trainer_pin("1234")
    validate_new_trainer_pin("847291")


@pytest.mark.asyncio
async def test_resend_credentials_does_not_return_password(client):
    admin = await login_admin(client)
    response = await client.post(
        "/admin/parents/1/resend-credentials",
        headers=write_headers(admin),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"]
    assert "password" not in body


@pytest.mark.asyncio
async def test_registration_submit_rate_limit(client):
    clear_all_rate_limits()
    branch_id = (await client.get("/branches")).json()[0]["id"]
    base_child = {
        "first_name": "C",
        "last_name": "D",
        "birth_date": "2015-05-10",
        "health_insurance": "VZP ČR",
        "branch_ids": [branch_id],
    }

    for i in range(5):
        response = await client.post(
            "/register",
            json={
                "parent_first_name": "A",
                "parent_last_name": "B",
                "email": f"rate.limit{i}@example.com",
                "phone": "+420601234567",
                "second_guardian": None,
                "children": [{**base_child, "birth_number": f"150510/100{i}"}],
            },
        )
        assert response.status_code == 200, response.text

    blocked = await client.post(
        "/register",
        json={
            "parent_first_name": "A",
            "parent_last_name": "B",
            "email": "rate.limit.blocked@example.com",
            "phone": "+420601234567",
            "second_guardian": None,
            "children": [{**base_child, "birth_number": "150510/1099"}],
        },
    )
    assert blocked.status_code == 429