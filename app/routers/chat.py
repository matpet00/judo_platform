from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    ChatConversation,
    ChatMessage,
    ChatParticipant,
    Parent,
    Trainer,
)
from app.schemas import (
    ChatContact,
    ChatConversationRead,
    ChatMessageCreate,
    ChatMessageRead,
    ChatParticipantBrief,
    StartConversation,
)
from app.security import Actor, get_actor

router = APIRouter(prefix="/chat", tags=["chat"])


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _actor_key(kind: str, subject_id: int) -> str:
    return f"{kind}:{subject_id}"


def _dm_key(kind_a: str, id_a: int, kind_b: str, id_b: int) -> str:
    return "|".join(sorted([_actor_key(kind_a, id_a), _actor_key(kind_b, id_b)]))


def _hidden_for_actor(conversation: ChatConversation, actor: Actor) -> bool:
    me = next((p for p in conversation.participants if _participant_is_actor(p, actor)), None)
    return me is not None and me.hidden_at is not None


def _participant_is_actor(participant: ChatParticipant, actor: Actor) -> bool:
    if actor.kind == "trainer":
        return participant.trainer_id == actor.trainer_id
    return participant.parent_id == actor.parent_id


def _message_is_actor(message: ChatMessage, actor: Actor) -> bool:
    if actor.kind == "trainer":
        return message.sender_trainer_id == actor.trainer_id
    return message.sender_parent_id == actor.parent_id


def _participant_brief(participant: ChatParticipant) -> ChatParticipantBrief:
    if participant.trainer_id is not None:
        trainer = participant.trainer
        name = f"{trainer.first_name} {trainer.last_name}" if trainer else f"Trenér #{participant.trainer_id}"
        return ChatParticipantBrief(kind="trainer", id=participant.trainer_id, name=name)
    parent = participant.parent
    name = f"{parent.first_name} {parent.last_name}" if parent else f"Rodič #{participant.parent_id}"
    return ChatParticipantBrief(kind="parent", id=participant.parent_id or 0, name=name)


def _message_to_read(message: ChatMessage) -> ChatMessageRead:
    sender_kind: str | None = None
    sender_id: int | None = None
    sender_name: str | None = None
    if message.sender_trainer_id is not None:
        sender_kind = "trainer"
        sender_id = message.sender_trainer_id
        if message.sender_trainer is not None:
            sender_name = f"{message.sender_trainer.first_name} {message.sender_trainer.last_name}"
    elif message.sender_parent_id is not None:
        sender_kind = "parent"
        sender_id = message.sender_parent_id
        if message.sender_parent is not None:
            sender_name = f"{message.sender_parent.first_name} {message.sender_parent.last_name}"
    created_at = _as_aware_utc(message.created_at)
    updated_at = _as_aware_utc(message.updated_at) if message.updated_at is not None else created_at
    return ChatMessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_kind=sender_kind,
        sender_id=sender_id,
        sender_name=sender_name,
        body=message.body,
        created_at=created_at,
        updated_at=updated_at,
    )


def _conversation_options():
    return (
        selectinload(ChatConversation.participants).selectinload(ChatParticipant.trainer),
        selectinload(ChatConversation.participants).selectinload(ChatParticipant.parent),
        selectinload(ChatConversation.messages).selectinload(ChatMessage.sender_trainer),
        selectinload(ChatConversation.messages).selectinload(ChatMessage.sender_parent),
    )


def _conversation_to_read(conversation: ChatConversation, actor: Actor) -> ChatConversationRead:
    me = next((p for p in conversation.participants if _participant_is_actor(p, actor)), None)
    counterpart = next((p for p in conversation.participants if not _participant_is_actor(p, actor)), None)
    last_read = _as_aware_utc(me.last_read_at) if me is not None and me.last_read_at is not None else None

    messages = sorted(conversation.messages, key=lambda m: (_as_aware_utc(m.created_at), m.id))
    last_message = messages[-1] if messages else None

    unread = 0
    for message in messages:
        if _message_is_actor(message, actor):
            continue
        if last_read is None or _as_aware_utc(message.created_at) > last_read:
            unread += 1

    return ChatConversationRead(
        id=conversation.id,
        is_group=conversation.is_group,
        counterpart=_participant_brief(counterpart) if counterpart is not None else None,
        last_message=_message_to_read(last_message) if last_message is not None else None,
        last_message_at=_as_aware_utc(conversation.last_message_at) if conversation.last_message_at else None,
        unread_count=unread,
        created_at=_as_aware_utc(conversation.created_at),
    )


async def _load_conversation_for_actor(db: AsyncSession, conversation_id: int, actor: Actor) -> ChatConversation:
    result = await db.execute(
        select(ChatConversation).where(ChatConversation.id == conversation_id).options(*_conversation_options()),
    )
    conversation = result.scalar_one_or_none()
    if conversation is None or not any(_participant_is_actor(p, actor) for p in conversation.participants):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.get("/contacts", response_model=list[ChatContact])
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[ChatContact]:
    contacts: list[ChatContact] = []

    trainers = (await db.execute(select(Trainer).order_by(Trainer.first_name, Trainer.last_name))).scalars().all()
    for trainer in trainers:
        if actor.kind == "trainer" and trainer.id == actor.trainer_id:
            continue
        contacts.append(
            ChatContact(
                kind="trainer",
                id=trainer.id,
                name=f"{trainer.first_name} {trainer.last_name}",
                subtitle="Trenér",
            ),
        )

    parents = (await db.execute(select(Parent).order_by(Parent.first_name, Parent.last_name))).scalars().all()
    for parent in parents:
        if actor.kind == "parent" and parent.id == actor.parent_id:
            continue
        contacts.append(
            ChatContact(
                kind="parent",
                id=parent.id,
                name=f"{parent.first_name} {parent.last_name}",
                subtitle="Rodič",
            ),
        )

    return contacts


@router.get("/conversations", response_model=list[ChatConversationRead])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[ChatConversationRead]:
    if actor.kind == "trainer":
        member = ChatParticipant.trainer_id == actor.trainer_id
    else:
        member = ChatParticipant.parent_id == actor.parent_id

    ids = (
        await db.execute(select(ChatParticipant.conversation_id).where(member))
    ).scalars().all()
    if not ids:
        return []

    result = await db.execute(
        select(ChatConversation).where(ChatConversation.id.in_(ids)).options(*_conversation_options()),
    )
    conversations = result.scalars().unique().all()
    visible = [c for c in conversations if not _hidden_for_actor(c, actor)]
    reads = [_conversation_to_read(c, actor) for c in visible]
    reads.sort(
        key=lambda c: c.last_message_at or c.created_at,
        reverse=True,
    )
    return reads


@router.post("/conversations", response_model=ChatConversationRead, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    payload: StartConversation,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> ChatConversationRead:
    my_kind = actor.kind
    my_id = actor.trainer_id if actor.kind == "trainer" else actor.parent_id
    if payload.counterpart_kind == my_kind and payload.counterpart_id == my_id:
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself.")

    if payload.counterpart_kind == "trainer":
        counterpart = await db.get(Trainer, payload.counterpart_id)
    else:
        counterpart = await db.get(Parent, payload.counterpart_id)
    if counterpart is None:
        raise HTTPException(status_code=404, detail="Counterpart not found.")

    dm_key = _dm_key(my_kind, int(my_id), payload.counterpart_kind, payload.counterpart_id)
    existing = (
        await db.execute(select(ChatConversation.id).where(ChatConversation.dm_key == dm_key))
    ).scalar_one_or_none()

    if existing is None:
        conversation = ChatConversation(dm_key=dm_key, is_group=False)
        conversation.participants = [
            _new_participant(my_kind, int(my_id)),
            _new_participant(payload.counterpart_kind, payload.counterpart_id),
        ]
        db.add(conversation)
        await db.commit()
        conversation_id = conversation.id
    else:
        conversation_id = existing

    conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    me = next((p for p in conversation.participants if _participant_is_actor(p, actor)), None)
    if me is not None and me.hidden_at is not None:
        me.hidden_at = None
        await db.commit()
        conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    return _conversation_to_read(conversation, actor)


def _new_participant(kind: str, subject_id: int) -> ChatParticipant:
    if kind == "trainer":
        return ChatParticipant(trainer_id=subject_id)
    return ChatParticipant(parent_id=subject_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    conversation_id: int,
    after_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> list[ChatMessageRead]:
    await _load_conversation_for_actor(db, conversation_id, actor)

    query = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .options(selectinload(ChatMessage.sender_trainer), selectinload(ChatMessage.sender_parent))
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    if after_id is not None:
        query = query.where(ChatMessage.id > after_id)

    messages = (await db.execute(query)).scalars().all()
    return [_message_to_read(m) for m in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: int,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> ChatMessageRead:
    conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    now = _now()

    message = ChatMessage(
        conversation_id=conversation_id,
        sender_trainer_id=actor.trainer_id if actor.kind == "trainer" else None,
        sender_parent_id=actor.parent_id if actor.kind == "parent" else None,
        body=payload.body,
        created_at=now,
        updated_at=now,
    )
    db.add(message)
    conversation.last_message_at = now
    for participant in conversation.participants:
        # New activity revives the conversation for anyone who had hidden it.
        participant.hidden_at = None
        if _participant_is_actor(participant, actor):
            participant.last_read_at = now
    await db.commit()

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.id == message.id)
        .options(selectinload(ChatMessage.sender_trainer), selectinload(ChatMessage.sender_parent)),
    )
    return _message_to_read(result.scalar_one())


async def _load_own_message_or_404(
    db: AsyncSession,
    conversation_id: int,
    message_id: int,
    actor: Actor,
) -> ChatMessage:
    await _load_conversation_for_actor(db, conversation_id, actor)
    message = await db.get(
        ChatMessage,
        message_id,
        options=[selectinload(ChatMessage.sender_trainer), selectinload(ChatMessage.sender_parent)],
    )
    if message is None or message.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="Message not found.")
    if not _message_is_actor(message, actor):
        raise HTTPException(status_code=403, detail="Only the author can modify this message.")
    return message


@router.patch(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=ChatMessageRead,
)
async def edit_message(
    conversation_id: int,
    message_id: int,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> ChatMessageRead:
    message = await _load_own_message_or_404(db, conversation_id, message_id, actor)
    message.body = payload.body
    message.updated_at = _now()
    await db.commit()

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.id == message.id)
        .options(selectinload(ChatMessage.sender_trainer), selectinload(ChatMessage.sender_parent)),
    )
    return _message_to_read(result.scalar_one())


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(
    conversation_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> None:
    message = await _load_own_message_or_404(db, conversation_id, message_id, actor)
    await db.delete(message)
    await db.commit()


@router.post("/conversations/{conversation_id}/read", response_model=ChatConversationRead)
async def mark_conversation_read(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> ChatConversationRead:
    conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    me = next((p for p in conversation.participants if _participant_is_actor(p, actor)), None)
    if me is not None:
        me.last_read_at = _now()
    await db.commit()

    conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    return _conversation_to_read(conversation, actor)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> None:
    conversation = await _load_conversation_for_actor(db, conversation_id, actor)
    me = next((p for p in conversation.participants if _participant_is_actor(p, actor)), None)
    if me is not None:
        # Soft delete: hide only from my list. Counterpart keeps it; new activity revives it.
        me.hidden_at = _now()
    await db.commit()