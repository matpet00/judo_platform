from datetime import UTC, datetime, timedelta

import pytest

from app.security import create_parent_token
from tests.conftest import login_trainer, write_headers


def _parent_token(parent_id: int = 1) -> str:
    token, _ = create_parent_token(parent_id)
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _future(days: int = 3) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def _create_event(client, trainer, targets, **overrides):
    payload = {
        "title": overrides.get("title", "Krajský přebor"),
        "description": overrides.get("description", "Sraz v 8:00"),
        "event_type": overrides.get("event_type", "tournament"),
        "location": overrides.get("location", "Ostrava"),
        "starts_at": overrides.get("starts_at", _future()),
        "ends_at": overrides.get("ends_at"),
        "targets": targets,
    }
    return await client.post("/events", json=payload, headers=write_headers(trainer))


@pytest.mark.asyncio
async def test_targeted_parent_sees_event_and_gets_notification(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # Marie -> child A (U8) in Orlova

    resp = await _create_event(client, trainer, [{"audience": "parent"}])
    assert resp.status_code == 201, resp.text
    event_id = resp.json()["id"]

    parent_events = (await client.get("/events", headers=_bearer(parent))).json()
    assert [e["id"] for e in parent_events] == [event_id]

    # An announcement notification was generated for the same audience.
    notifications = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert any(n["event_id"] == event_id for n in notifications)


@pytest.mark.asyncio
async def test_event_scoped_by_age_group(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # child is U8

    resp = await _create_event(client, trainer, [{"audience": "parent", "age_group": "U12"}])
    assert resp.status_code == 201

    parent_events = (await client.get("/events", headers=_bearer(parent))).json()
    assert parent_events == []


@pytest.mark.asyncio
async def test_parent_cannot_create_event(client):
    parent = _parent_token(1)
    resp = await _create_event(client, parent, [{"audience": "parent"}])
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_per_child_rsvp_and_organizer_summary(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # Marie -> child id 1 (A Novak, U8)

    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    # Parent responds for their child by student_id.
    rsvp = await client.post(
        f"/events/{event_id}/rsvp",
        json={"responses": [{"student_id": 1, "status": "yes"}]},
        headers=write_headers(parent),
    )
    assert rsvp.status_code == 200, rsvp.text
    child_rsvps = rsvp.json()["my_child_rsvps"]
    assert child_rsvps == [{"student_id": 1, "name": "A Novak", "status": "yes"}]

    # Organizer sees the per-child summary; a parent does not.
    organizer_view = (await client.get(f"/events/{event_id}", headers=_bearer(trainer))).json()
    summary = organizer_view["rsvp_summary"]
    assert summary["yes"] == 1
    assert summary["participants"][0]["child_name"] == "A Novak"
    assert summary["participants"][0]["student_id"] == 1

    parent_view = (await client.get(f"/events/{event_id}", headers=_bearer(parent))).json()
    assert parent_view["rsvp_summary"] is None


@pytest.mark.asyncio
async def test_parent_cannot_rsvp_for_other_child(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)  # only owns child id 1
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    resp = await client.post(
        f"/events/{event_id}/rsvp",
        json={"responses": [{"student_id": 2, "status": "yes"}]},
        headers=write_headers(parent),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trainer_self_rsvp(client):
    trainer = await login_trainer(client)
    event_id = (await _create_event(client, trainer, [{"audience": "trainer"}])).json()["id"]

    resp = await client.post(
        f"/events/{event_id}/rsvp",
        json={"responses": [{"student_id": None, "status": "maybe"}]},
        headers=write_headers(trainer),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["my_rsvp"] == "maybe"


@pytest.mark.asyncio
async def test_comment_flow(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    created = await client.post(
        f"/events/{event_id}/comments",
        json={"body": "Kdy je sraz?"},
        headers=write_headers(parent),
    )
    assert created.status_code == 201
    comment_id = created.json()["id"]
    assert created.json()["can_edit"] is True

    detail = (await client.get(f"/events/{event_id}", headers=_bearer(parent))).json()
    assert [c["body"] for c in detail["comments"]] == ["Kdy je sraz?"]

    deleted = await client.delete(
        f"/events/{event_id}/comments/{comment_id}",
        headers=write_headers(parent),
    )
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_parent_comment_notifies_organizer(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    resp = await client.post(
        f"/events/{event_id}/comments",
        json={"body": "Kdy je sraz?"},
        headers=write_headers(parent),
    )
    assert resp.status_code == 201

    notifications = (await client.get("/notifications", headers=write_headers(trainer))).json()
    reactions = [
        n for n in notifications if n["event_id"] == event_id and n["title"].startswith("Nová reakce")
    ]
    assert len(reactions) == 1
    assert reactions[0]["unread"] is True


@pytest.mark.asyncio
async def test_reply_notifies_parent_participant(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    # Parent asks a question first.
    await client.post(
        f"/events/{event_id}/comments",
        json={"body": "kde to bude?"},
        headers=write_headers(parent),
    )
    # Organizer replies -> the parent participant should be notified.
    await client.post(
        f"/events/{event_id}/comments",
        json={"body": "ostrava"},
        headers=write_headers(trainer),
    )

    notifications = (await client.get("/notifications", headers=write_headers(parent))).json()
    reactions = [
        n for n in notifications if n["event_id"] == event_id and n["title"].startswith("Nová reakce")
    ]
    assert len(reactions) == 1
    assert reactions[0]["unread"] is True


@pytest.mark.asyncio
async def test_organizer_own_comment_does_not_notify(client):
    trainer = await login_trainer(client)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    resp = await client.post(
        f"/events/{event_id}/comments",
        json={"body": "Interní poznámka"},
        headers=write_headers(trainer),
    )
    assert resp.status_code == 201

    notifications = (await client.get("/notifications", headers=write_headers(trainer))).json()
    reactions = [n for n in notifications if n["title"].startswith("Nová reakce")]
    assert reactions == []


@pytest.mark.asyncio
async def test_attachment_upload_download_delete(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    uploaded = await client.post(
        f"/events/{event_id}/attachments",
        files={"file": ("propozice.txt", b"hello judo", "text/plain")},
        headers=write_headers(trainer),
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]
    assert uploaded.json()["size_bytes"] == len(b"hello judo")

    # Parent can download it.
    download = await client.get(
        f"/events/{event_id}/attachments/{attachment_id}/download",
        headers=_bearer(parent),
    )
    assert download.status_code == 200
    assert download.content == b"hello judo"

    # Parent (not uploader, not organizer) cannot delete it.
    forbidden = await client.delete(
        f"/events/{event_id}/attachments/{attachment_id}",
        headers=write_headers(parent),
    )
    assert forbidden.status_code == 403

    removed = await client.delete(
        f"/events/{event_id}/attachments/{attachment_id}",
        headers=write_headers(trainer),
    )
    assert removed.status_code == 204


@pytest.mark.asyncio
async def test_only_author_can_delete_event(client):
    trainer = await login_trainer(client)
    other = await login_trainer(client, trainer_id=2)
    event_id = (await _create_event(client, trainer, [{"audience": "trainer"}])).json()["id"]

    forbidden = await client.delete(f"/events/{event_id}", headers=write_headers(other))
    assert forbidden.status_code == 403

    ok = await client.delete(f"/events/{event_id}", headers=write_headers(trainer))
    assert ok.status_code == 204


@pytest.mark.asyncio
async def test_author_can_update_event(client):
    trainer = await login_trainer(client)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    updated = await client.patch(
        f"/events/{event_id}",
        json={"title": "Změněný název", "location": "Bohumín", "event_type": "meeting"},
        headers=write_headers(trainer),
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "Změněný název"
    assert body["location"] == "Bohumín"
    assert body["event_type"] == "meeting"


@pytest.mark.asyncio
async def test_update_rejects_empty_targets(client):
    trainer = await login_trainer(client)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    resp = await client.patch(
        f"/events/{event_id}",
        json={"targets": []},
        headers=write_headers(trainer),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_syncs_linked_notification(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)
    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    # Retarget to a category the parent's children don't belong to.
    await client.patch(
        f"/events/{event_id}",
        json={"title": "Jen U16", "targets": [{"audience": "parent", "age_group": "U16"}]},
        headers=write_headers(trainer),
    )

    # The board notification followed the new targets and is no longer visible to this parent.
    notifications = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert not any(n["event_id"] == event_id for n in notifications)

    # A trainer still sees it, with the refreshed title.
    trainer_notifs = (await client.get("/notifications", headers=_bearer(trainer))).json()
    linked = [n for n in trainer_notifs if n["event_id"] == event_id]
    assert linked and linked[0]["title"] == "Nová akce: Jen U16"


@pytest.mark.asyncio
async def test_deleting_event_removes_its_notification(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    event_id = (await _create_event(client, trainer, [{"audience": "parent"}])).json()["id"]

    before = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert any(n["event_id"] == event_id for n in before)

    ok = await client.delete(f"/events/{event_id}", headers=write_headers(trainer))
    assert ok.status_code == 204

    after = (await client.get("/notifications", headers=_bearer(parent))).json()
    assert not any(n["event_id"] == event_id for n in after)
