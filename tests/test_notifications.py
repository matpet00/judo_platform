from datetime import UTC, datetime, timedelta

import pytest

from app.main import app
from app.routers.notifications import notification_now
from tests.conftest import login_trainer, write_headers


def set_notification_now(value: datetime) -> None:
    app.dependency_overrides[notification_now] = lambda: value


def clear_notification_now() -> None:
    app.dependency_overrides.pop(notification_now, None)


@pytest.mark.asyncio
async def test_trainer_can_create_and_list_all_trainer_notification(client):
    token = await login_trainer(client, trainer_id=1)

    create = await client.post(
        "/notifications",
        json={
            "title": "Meeting",
            "body": "Short trainer meeting after practice.",
            "audiences": ["trainer"],
            "targets": [],
        },
        headers=write_headers(token),
    )

    assert create.status_code == 201
    created = create.json()
    assert created["can_delete"] is True
    assert created["targets"][0]["audience"] == "trainer"
    assert created["targets"][0]["trainer_id"] is None

    other_token = await login_trainer(client, trainer_id=2)
    listing = await client.get("/notifications", headers={"Authorization": f"Bearer {other_token}"})
    assert listing.status_code == 200
    assert [row["title"] for row in listing.json()] == ["Meeting"]
    assert listing.json()[0]["can_delete"] is False
    assert listing.json()[0]["visibility_state"] == "active"


@pytest.mark.asyncio
async def test_parent_and_individual_targets_are_stored(client):
    token = await login_trainer(client, trainer_id=1)

    response = await client.post(
        "/notifications",
        json={
            "title": "Payment",
            "body": "Please check membership fees.",
            "audiences": ["parent"],
            "targets": [{"audience": "trainer", "trainer_id": 2}],
        },
        headers=write_headers(token),
    )

    assert response.status_code == 201
    targets = response.json()["targets"]
    assert {"audience": "parent", "trainer_id": None, "parent_id": None} in [
        {k: target[k] for k in ("audience", "trainer_id", "parent_id")}
        for target in targets
    ]
    assert {"audience": "trainer", "trainer_id": 2, "parent_id": None} in [
        {k: target[k] for k in ("audience", "trainer_id", "parent_id")}
        for target in targets
    ]


@pytest.mark.asyncio
async def test_only_author_can_delete_notification(client):
    token = await login_trainer(client, trainer_id=1)
    other_token = await login_trainer(client, trainer_id=2)

    create = await client.post(
        "/notifications",
        json={"title": "Private", "body": "Author only delete.", "audiences": ["trainer"]},
        headers=write_headers(token),
    )
    notification_id = create.json()["id"]

    forbidden = await client.delete(f"/notifications/{notification_id}", headers=write_headers(other_token))
    assert forbidden.status_code == 403

    deleted = await client.delete(f"/notifications/{notification_id}", headers=write_headers(token))
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_notification_default_visibility_is_seven_days(client):
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    set_notification_now(fixed_now)
    try:
        token = await login_trainer(client, trainer_id=1)
        response = await client.post(
            "/notifications",
            json={"title": "Default", "body": "Default expiry.", "audiences": ["trainer"]},
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()

    assert response.status_code == 201
    body = response.json()
    assert datetime.fromisoformat(body["visible_until"]) == fixed_now + timedelta(days=7)
    assert datetime.fromisoformat(body["hide_after"]) == fixed_now + timedelta(days=14)


@pytest.mark.asyncio
async def test_notification_duration_and_exact_visibility(client):
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    set_notification_now(fixed_now)
    try:
        token = await login_trainer(client, trainer_id=1)
        duration = await client.post(
            "/notifications",
            json={
                "title": "Duration",
                "body": "Two hours.",
                "audiences": ["trainer"],
                "duration_amount": 2,
                "duration_unit": "hours",
            },
            headers=write_headers(token),
        )
        exact_until = datetime(2026, 1, 3, 9, 30, tzinfo=UTC)
        exact = await client.post(
            "/notifications",
            json={
                "title": "Exact",
                "body": "Exact expiry.",
                "audiences": ["trainer"],
                "visible_until": exact_until.isoformat(),
            },
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()

    assert duration.status_code == 201
    assert datetime.fromisoformat(duration.json()["visible_until"]) == fixed_now + timedelta(hours=2)
    assert exact.status_code == 201
    assert datetime.fromisoformat(exact.json()["visible_until"]) == exact_until


@pytest.mark.asyncio
async def test_expired_notifications_gray_period_then_hidden(client):
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    set_notification_now(fixed_now)
    try:
        token = await login_trainer(client, trainer_id=1)
        response = await client.post(
            "/notifications",
            json={
                "title": "Short",
                "body": "Expires quickly.",
                "audiences": ["trainer"],
                "duration_amount": 1,
                "duration_unit": "hours",
            },
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()

    assert response.status_code == 201

    set_notification_now(fixed_now + timedelta(days=2))
    try:
        expired = await client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    finally:
        clear_notification_now()
    assert expired.status_code == 200
    assert expired.json()[0]["visibility_state"] == "expired"

    set_notification_now(fixed_now + timedelta(days=9))
    try:
        hidden = await client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    finally:
        clear_notification_now()
    assert hidden.status_code == 200
    assert hidden.json() == []
