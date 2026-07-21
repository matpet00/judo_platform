import pytest

from tests.conftest import login_parent, login_trainer, write_headers


@pytest.mark.asyncio
async def test_public_event_share_page(client):
    trainer = await login_trainer(client)
    branch_id = (await client.get("/branches")).json()[0]["id"]

    create = await client.post(
        "/events",
        headers=write_headers(trainer),
        json={
            "title": "Share Turnaj",
            "description": "Veřejný popis",
            "event_type": "tournament",
            "location": "Hala Orlová",
            "starts_at": "2030-05-10T16:00:00+02:00",
            "ends_at": None,
            "targets": [{"audience": "parent", "branch_id": branch_id, "age_group": "U8"}],
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()
    token = created["share_token"]
    assert token

    public = await client.get(f"/public/events/{token}")
    assert public.status_code == 200
    body = public.json()
    assert body["kind"] == "event"
    assert body["title"] == "Share Turnaj"
    assert body["location"] == "Hala Orlová"
    assert body["description"] == "Veřejný popis"
    assert any("U8" in label for label in body["audience_labels"])
    assert body["intended_for_you"] is None
    assert "targets" not in body
    assert "rsvp_summary" not in body

    # Seeded testparent has U8 child → intended.
    parent_token = await login_parent(client)
    for_me = await client.get(
        f"/public/events/{token}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert for_me.status_code == 200
    assert for_me.json()["intended_for_you"] is True

    missing = await client.get("/public/events/does-not-exist")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_public_event_share_wrong_age_parent(client):
    trainer = await login_trainer(client)
    branch_id = (await client.get("/branches")).json()[0]["id"]

    create = await client.post(
        "/events",
        headers=write_headers(trainer),
        json={
            "title": "Jen U10",
            "description": "",
            "event_type": "tournament",
            "location": "Hala",
            "starts_at": "2030-06-01T10:00:00+02:00",
            "targets": [{"audience": "parent", "branch_id": branch_id, "age_group": "U10"}],
        },
    )
    assert create.status_code == 201, create.text
    token = create.json()["share_token"]

    # testparent has only U8 child
    parent_token = await login_parent(client)
    public = await client.get(
        f"/public/events/{token}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert public.status_code == 200
    assert public.json()["intended_for_you"] is False
    assert any("U10" in label for label in public.json()["audience_labels"])


@pytest.mark.asyncio
async def test_public_training_share_page(client):
    trainer = await login_trainer(client)
    groups = (await client.get("/training-groups", headers=write_headers(trainer))).json()
    branch_id = groups[0]["branch_id"]

    create = await client.post(
        "/training-groups",
        headers=write_headers(trainer),
        json={
            "branch_id": branch_id,
            "name": "Share U10 Po Unique",
            "start_time": "17:05",
            "end_time": "18:05",
            "weekdays": [1],
            "active_from": "2030-01-01",
            "active_until": "2030-12-31",
            "student_ids": [1, 2],
            "trainer_ids": [],
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()
    token = created["share_token"]
    assert token

    public = await client.get(f"/public/trainings/{token}")
    assert public.status_code == 200
    body = public.json()
    assert body["kind"] == "training"
    assert body["name"] == "Share U10 Po Unique"
    assert body["weekdays"] == [1]
    assert "students" not in body
