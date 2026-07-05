import pytest

from app.security import create_parent_token
from tests.conftest import login_trainer, write_headers


def _parent_token(parent_id: int = 1) -> str:
    token, _ = create_parent_token(parent_id)
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_start_conversation_is_idempotent(client):
    trainer = await login_trainer(client)

    first = await client.post(
        "/chat/conversations",
        json={"counterpart_kind": "parent", "counterpart_id": 1},
        headers=write_headers(trainer),
    )
    assert first.status_code == 201
    second = await client.post(
        "/chat/conversations",
        json={"counterpart_kind": "parent", "counterpart_id": 1},
        headers=write_headers(trainer),
    )
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_cannot_chat_with_self(client):
    trainer = await login_trainer(client)
    resp = await client.post(
        "/chat/conversations",
        json={"counterpart_kind": "trainer", "counterpart_id": 1},
        headers=write_headers(trainer),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_message_delivered_to_both_and_unread(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    conv = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()
    conv_id = conv["id"]

    sent = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "Ahoj, dorazi Pepa v sobotu?"},
        headers=write_headers(trainer),
    )
    assert sent.status_code == 201

    # Parent sees the conversation with unread=1 and the counterpart is the trainer.
    parent_convs = (await client.get("/chat/conversations", headers=_bearer(parent))).json()
    assert len(parent_convs) == 1
    assert parent_convs[0]["unread_count"] == 1
    assert parent_convs[0]["counterpart"]["kind"] == "trainer"
    assert parent_convs[0]["last_message"]["body"] == "Ahoj, dorazi Pepa v sobotu?"

    # Parent reads the messages.
    msgs = (await client.get(f"/chat/conversations/{conv_id}/messages", headers=_bearer(parent))).json()
    assert [m["body"] for m in msgs] == ["Ahoj, dorazi Pepa v sobotu?"]
    assert msgs[0]["sender_kind"] == "trainer"

    # Sender sees no unread for themselves.
    trainer_convs = (await client.get("/chat/conversations", headers=_bearer(trainer))).json()
    assert trainer_convs[0]["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_read_clears_unread(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]
    await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "test"},
        headers=write_headers(trainer),
    )

    before = (await client.get("/chat/conversations", headers=_bearer(parent))).json()[0]
    assert before["unread_count"] == 1

    read = await client.post(f"/chat/conversations/{conv_id}/read", headers=write_headers(parent))
    assert read.status_code == 200
    assert read.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_parent_can_reply(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]

    reply = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "Ano, dorazime."},
        headers=write_headers(parent),
    )
    assert reply.status_code == 201
    assert reply.json()["sender_kind"] == "parent"

    # Trainer now has an unread message from the parent.
    trainer_convs = (await client.get("/chat/conversations", headers=_bearer(trainer))).json()
    assert trainer_convs[0]["unread_count"] == 1


@pytest.mark.asyncio
async def test_author_can_edit_and_delete_message(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]
    msg_id = (
        await client.post(
            f"/chat/conversations/{conv_id}/messages",
            json={"body": "puvodni"},
            headers=write_headers(trainer),
        )
    ).json()["id"]

    edited = await client.patch(
        f"/chat/conversations/{conv_id}/messages/{msg_id}",
        json={"body": "upraveno"},
        headers=write_headers(trainer),
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "upraveno"
    assert edited.json()["updated_at"] != edited.json()["created_at"]

    # Parent (not the author) cannot edit or delete it.
    forbidden = await client.patch(
        f"/chat/conversations/{conv_id}/messages/{msg_id}",
        json={"body": "hack"},
        headers=write_headers(parent),
    )
    assert forbidden.status_code == 403

    deleted = await client.delete(
        f"/chat/conversations/{conv_id}/messages/{msg_id}",
        headers=write_headers(trainer),
    )
    assert deleted.status_code == 204

    remaining = (await client.get(f"/chat/conversations/{conv_id}/messages", headers=write_headers(trainer))).json()
    assert remaining == []


@pytest.mark.asyncio
async def test_new_message_is_not_marked_edited(client):
    trainer = await login_trainer(client)
    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]
    sent = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "cerstva zprava"},
        headers=write_headers(trainer),
    )
    assert sent.status_code == 201
    body = sent.json()
    assert body["updated_at"] == body["created_at"]


@pytest.mark.asyncio
async def test_delete_conversation_hides_only_for_me_and_revives_on_new_message(client):
    trainer = await login_trainer(client)
    parent = _parent_token(1)

    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]
    await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "prvni"},
        headers=write_headers(trainer),
    )

    # Trainer deletes (hides) the conversation.
    deleted = await client.delete(f"/chat/conversations/{conv_id}", headers=write_headers(trainer))
    assert deleted.status_code == 204

    # Gone from the trainer's list, but the parent still sees it.
    assert (await client.get("/chat/conversations", headers=_bearer(trainer))).json() == []
    parent_list = (await client.get("/chat/conversations", headers=_bearer(parent))).json()
    assert len(parent_list) == 1

    # Parent sends a new message -> conversation revives for the trainer with full history.
    await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"body": "ahoj zpet"},
        headers=write_headers(parent),
    )
    revived = (await client.get("/chat/conversations", headers=_bearer(trainer))).json()
    assert len(revived) == 1
    history = (await client.get(f"/chat/conversations/{conv_id}/messages", headers=_bearer(trainer))).json()
    assert [m["body"] for m in history] == ["prvni", "ahoj zpet"]


@pytest.mark.asyncio
async def test_non_member_cannot_access_conversation(client):
    trainer = await login_trainer(client)
    other_trainer = await login_trainer(client, trainer_id=2)

    conv_id = (
        await client.post(
            "/chat/conversations",
            json={"counterpart_kind": "parent", "counterpart_id": 1},
            headers=write_headers(trainer),
        )
    ).json()["id"]

    resp = await client.get(f"/chat/conversations/{conv_id}/messages", headers=_bearer(other_trainer))
    assert resp.status_code == 404

    # And it does not show up in the non-member's conversation list.
    others = (await client.get("/chat/conversations", headers=_bearer(other_trainer))).json()
    assert others == []
