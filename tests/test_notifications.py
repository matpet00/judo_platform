from datetime import UTC, datetime, timedelta

import pytest

from app.main import app
from app.routers.notifications import notification_now
from app.security import create_parent_token, create_trainer_token
from tests.conftest import login_trainer, write_headers


def _parent_bearer(parent_id: int = 1) -> dict[str, str]:
    token, _ = create_parent_token(parent_id)
    return {"Authorization": f"Bearer {token}"}


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
            "targets": [{"audience": "trainer"}],
        },
        headers=write_headers(token),
    )

    assert create.status_code == 201
    created = create.json()
    assert created["can_delete"] is True
    assert created["targets"][0]["audience"] == "trainer"
    assert created["targets"][0]["branch_id"] is None

    other_token = await login_trainer(client, trainer_id=2)
    listing = await client.get("/notifications", headers={"Authorization": f"Bearer {other_token}"})
    assert listing.status_code == 200
    assert [row["title"] for row in listing.json()] == ["Meeting"]
    assert listing.json()[0]["can_delete"] is False
    assert listing.json()[0]["visibility_state"] == "active"


@pytest.mark.asyncio
async def test_branch_targets_are_stored(client):
    token = await login_trainer(client, trainer_id=1)

    branches = await client.get("/branches")
    orlova_id = next(row["id"] for row in branches.json() if row["name"] == "Orlova")

    response = await client.post(
        "/notifications",
        json={
            "title": "Payment",
            "body": "Please check membership fees.",
            "targets": [
                {"audience": "parent", "branch_id": orlova_id},
                {"audience": "trainer", "branch_id": orlova_id},
            ],
        },
        headers=write_headers(token),
    )

    assert response.status_code == 201
    targets = [
        {k: target[k] for k in ("audience", "branch_id")}
        for target in response.json()["targets"]
    ]
    assert {"audience": "parent", "branch_id": orlova_id} in targets
    assert {"audience": "trainer", "branch_id": orlova_id} in targets


@pytest.mark.asyncio
async def test_parent_category_targets_are_stored(client):
    token = await login_trainer(client, trainer_id=1)

    branches = await client.get("/branches")
    orlova_id = next(row["id"] for row in branches.json() if row["name"] == "Orlova")

    response = await client.post(
        "/notifications",
        json={
            "title": "U8 info",
            "body": "Info pro rodiče U8 a U10.",
            "targets": [
                {"audience": "parent", "branch_id": orlova_id, "age_group": "U8"},
                {"audience": "parent", "branch_id": orlova_id, "age_group": "U10"},
            ],
        },
        headers=write_headers(token),
    )

    assert response.status_code == 201
    stored = [
        {k: target[k] for k in ("audience", "branch_id", "age_group")}
        for target in response.json()["targets"]
    ]
    assert {"audience": "parent", "branch_id": orlova_id, "age_group": "U8"} in stored
    assert {"audience": "parent", "branch_id": orlova_id, "age_group": "U10"} in stored


@pytest.mark.asyncio
async def test_trainer_target_rejects_age_group(client):
    token = await login_trainer(client, trainer_id=1)

    response = await client.post(
        "/notifications",
        json={
            "title": "Bad",
            "body": "Trainer target with category.",
            "targets": [{"audience": "trainer", "age_group": "U8"}],
        },
        headers=write_headers(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_notification_read_state_new_then_read(client):
    author_token = await login_trainer(client, trainer_id=1)
    reader_token = await login_trainer(client, trainer_id=2)

    create = await client.post(
        "/notifications",
        json={"title": "Hi", "body": "Body.", "targets": [{"audience": "trainer"}]},
        headers=write_headers(author_token),
    )
    assert create.status_code == 201
    notification_id = create.json()["id"]
    assert create.json()["unread"] is False

    reader_list = await client.get("/notifications", headers={"Authorization": f"Bearer {reader_token}"})
    reader_view = next(row for row in reader_list.json() if row["id"] == notification_id)
    assert reader_view["unread"] is True

    marked = await client.post(
        f"/notifications/{notification_id}/read",
        headers=write_headers(reader_token),
    )
    assert marked.status_code == 200
    assert marked.json()["unread"] is False

    reader_list2 = await client.get("/notifications", headers={"Authorization": f"Bearer {reader_token}"})
    reader_view2 = next(row for row in reader_list2.json() if row["id"] == notification_id)
    assert reader_view2["unread"] is False


@pytest.mark.asyncio
async def test_new_comment_makes_notification_unread_again(client):
    author_token = await login_trainer(client, trainer_id=1)
    reader_token = await login_trainer(client, trainer_id=2)

    create = await client.post(
        "/notifications",
        json={"title": "Thread", "body": "Discuss.", "targets": [{"audience": "trainer"}]},
        headers=write_headers(author_token),
    )
    notification_id = create.json()["id"]

    await client.post(f"/notifications/{notification_id}/read", headers=write_headers(reader_token))

    comment = await client.post(
        f"/notifications/{notification_id}/comments",
        json={"body": "First reply"},
        headers=write_headers(author_token),
    )
    assert comment.status_code == 201
    assert comment.json()["author_trainer"]["id"] == 1

    reader_list = await client.get("/notifications", headers={"Authorization": f"Bearer {reader_token}"})
    reader_view = next(row for row in reader_list.json() if row["id"] == notification_id)
    assert reader_view["unread"] is True
    assert reader_view["comment_count"] == 1

    listed = await client.get(
        f"/notifications/{notification_id}/comments",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert listed.status_code == 200
    assert [row["body"] for row in listed.json()] == ["First reply"]

    author_list = await client.get("/notifications", headers={"Authorization": f"Bearer {author_token}"})
    author_view = next(row for row in author_list.json() if row["id"] == notification_id)
    assert author_view["unread"] is False

    # Reader already read once, so the new comment shows up as has_read + unread (nová odpověď).
    assert reader_view["has_read"] is True


@pytest.mark.asyncio
async def test_parent_comment_makes_notification_unread_for_author(client):
    author_token = await login_trainer(client, trainer_id=1)

    create = await client.post(
        "/notifications",
        json={"title": "Trénink", "body": "Dnes není.", "targets": [{"audience": "parent"}]},
        headers=write_headers(author_token),
    )
    notification_id = create.json()["id"]
    assert create.json()["unread"] is False  # author starts read

    reply = await client.post(
        f"/notifications/{notification_id}/comments",
        json={"body": "děkujeme za info"},
        headers={**write_headers(), **_parent_bearer(1)},
    )
    assert reply.status_code == 201

    author_list = await client.get("/notifications", headers={"Authorization": f"Bearer {author_token}"})
    author_view = next(row for row in author_list.json() if row["id"] == notification_id)
    assert author_view["unread"] is True
    assert author_view["comment_count"] == 1

    # The whole reaction thread lives on the original notification (no extra items).
    assert len(author_list.json()) == 1


@pytest.mark.asyncio
async def test_trainer_comment_makes_notification_unread_for_targeted_parent(client):
    author_token = await login_trainer(client, trainer_id=1)

    create = await client.post(
        "/notifications",
        json={"title": "Turnaj", "body": "Info.", "targets": [{"audience": "parent"}]},
        headers=write_headers(author_token),
    )
    notification_id = create.json()["id"]

    # Parent sees it and reads it first.
    await client.post(f"/notifications/{notification_id}/read", headers=_parent_bearer(1))

    reply = await client.post(
        f"/notifications/{notification_id}/comments",
        json={"body": "doplňuji čas srazu"},
        headers=write_headers(author_token),
    )
    assert reply.status_code == 201

    parent_list = await client.get("/notifications", headers=_parent_bearer(1))
    # No separate alert notifications; the original thread flips unread again.
    assert len(parent_list.json()) == 1
    parent_view = parent_list.json()[0]
    assert parent_view["id"] == notification_id
    assert parent_view["unread"] is True
    assert parent_view["comment_count"] == 1


@pytest.mark.asyncio
async def test_own_comment_does_not_self_notify(client):
    author_token = await login_trainer(client, trainer_id=1)

    create = await client.post(
        "/notifications",
        json={"title": "Jen treneri", "body": "Info.", "targets": [{"audience": "trainer"}]},
        headers=write_headers(author_token),
    )
    notification_id = create.json()["id"]

    await client.post(
        f"/notifications/{notification_id}/comments",
        json={"body": "poznámka"},
        headers=write_headers(author_token),
    )

    author_list = await client.get("/notifications", headers={"Authorization": f"Bearer {author_token}"})
    # No extra items, and the author's own comment does not flip their own thread unread.
    assert len(author_list.json()) == 1
    assert author_list.json()[0]["unread"] is False


@pytest.mark.asyncio
async def test_cannot_comment_on_expired_notification(client):
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    set_notification_now(fixed_now)
    try:
        token = await login_trainer(client, trainer_id=1)
        create = await client.post(
            "/notifications",
            json={
                "title": "Short",
                "body": "Expires quickly.",
                "targets": [{"audience": "trainer"}],
                "duration_amount": 1,
                "duration_unit": "hours",
                "keep_after_expiry": True,
                "grace_amount": 7,
                "grace_unit": "days",
            },
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()
    notification_id = create.json()["id"]

    set_notification_now(fixed_now + timedelta(days=2))
    try:
        blocked = await client.post(
            f"/notifications/{notification_id}/comments",
            json={"body": "too late"},
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_only_author_can_edit_comment(client):
    author_token = await login_trainer(client, trainer_id=1)
    other_token = await login_trainer(client, trainer_id=2)

    create = await client.post(
        "/notifications",
        json={"title": "T", "body": "B.", "targets": [{"audience": "trainer"}]},
        headers=write_headers(author_token),
    )
    notification_id = create.json()["id"]

    comment = await client.post(
        f"/notifications/{notification_id}/comments",
        json={"body": "original"},
        headers=write_headers(author_token),
    )
    comment_id = comment.json()["id"]

    forbidden = await client.patch(
        f"/notifications/{notification_id}/comments/{comment_id}",
        json={"body": "hacked"},
        headers=write_headers(other_token),
    )
    assert forbidden.status_code == 403

    edited = await client.patch(
        f"/notifications/{notification_id}/comments/{comment_id}",
        json={"body": "edited body"},
        headers=write_headers(author_token),
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "edited body"
    assert edited.json()["can_edit"] is True

    listed = await client.get(
        f"/notifications/{notification_id}/comments",
        headers={"Authorization": f"Bearer {author_token}"},
    )
    assert [row["body"] for row in listed.json()] == ["edited body"]


@pytest.mark.asyncio
async def test_only_author_can_delete_notification(client):
    token = await login_trainer(client, trainer_id=1)
    other_token = await login_trainer(client, trainer_id=2)

    create = await client.post(
        "/notifications",
        json={"title": "Private", "body": "Author only delete.", "targets": [{"audience": "trainer"}]},
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
            json={"title": "Default", "body": "Default expiry.", "targets": [{"audience": "trainer"}]},
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()

    assert response.status_code == 201
    body = response.json()
    assert datetime.fromisoformat(body["visible_until"]) == fixed_now + timedelta(days=7)
    # No grace by default -> hidden/deleted right at expiry.
    assert datetime.fromisoformat(body["hide_after"]) == fixed_now + timedelta(days=7)


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
                "targets": [{"audience": "trainer"}],
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
                "targets": [{"audience": "trainer"}],
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
                "targets": [{"audience": "trainer"}],
                "duration_amount": 1,
                "duration_unit": "hours",
                "keep_after_expiry": True,
                "grace_amount": 7,
                "grace_unit": "days",
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


@pytest.mark.asyncio
async def test_notification_without_grace_deleted_after_expiry(client):
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    set_notification_now(fixed_now)
    try:
        token = await login_trainer(client, trainer_id=1)
        create = await client.post(
            "/notifications",
            json={
                "title": "No grace",
                "body": "Vanishes at expiry.",
                "targets": [{"audience": "trainer"}],
                "duration_amount": 1,
                "duration_unit": "hours",
            },
            headers=write_headers(token),
        )
    finally:
        clear_notification_now()
    assert create.status_code == 201
    notification_id = create.json()["id"]

    set_notification_now(fixed_now + timedelta(hours=2))
    try:
        listing = await client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    finally:
        clear_notification_now()
    assert listing.status_code == 200
    assert listing.json() == []

    # Hard-deleted from DB: even a direct fetch is gone.
    gone = await client.post(f"/notifications/{notification_id}/read", headers=write_headers(token))
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_keep_after_expiry_requires_grace(client):
    token = await login_trainer(client, trainer_id=1)
    response = await client.post(
        "/notifications",
        json={
            "title": "Bad",
            "body": "Missing grace.",
            "targets": [{"audience": "trainer"}],
            "keep_after_expiry": True,
        },
        headers=write_headers(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_branch_scoped_notification_visibility(client):
    author_token = await login_trainer(client, trainer_id=1)

    branches = await client.get("/branches")
    branch_by_name = {row["name"]: row["id"] for row in branches.json()}
    orlova_id = branch_by_name["Orlova"]
    petrvald_id = branch_by_name["Petrvald"]

    created = await client.post(
        "/trainers",
        json={"first_name": "Petr", "last_name": "Vald", "branch_ids": [petrvald_id]},
        headers=write_headers(author_token),
    )
    assert created.status_code == 200
    petrvald_trainer_id = created.json()["id"]
    petrvald_token, _ = create_trainer_token(petrvald_trainer_id)

    orlova_only = await client.post(
        "/notifications",
        json={
            "title": "Orlova only",
            "body": "For Orlova trainers.",
            "targets": [{"audience": "trainer", "branch_id": orlova_id}],
        },
        headers=write_headers(author_token),
    )
    assert orlova_only.status_code == 201

    all_trainers = await client.post(
        "/notifications",
        json={
            "title": "All trainers",
            "body": "For every trainer.",
            "targets": [{"audience": "trainer"}],
        },
        headers=write_headers(author_token),
    )
    assert all_trainers.status_code == 201

    petrvald_listing = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {petrvald_token}"},
    )
    assert petrvald_listing.status_code == 200
    petrvald_titles = {row["title"] for row in petrvald_listing.json()}
    assert "All trainers" in petrvald_titles
    assert "Orlova only" not in petrvald_titles

    orlova_listing = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {author_token}"},
    )
    assert orlova_listing.status_code == 200
    orlova_titles = {row["title"] for row in orlova_listing.json()}
    assert {"All trainers", "Orlova only"} <= orlova_titles
