import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.deps import Viewer, get_viewer, matched_children, viewer_can_see_targets
from app.models import (
    Branch,
    Event,
    EventAttachment,
    EventComment,
    EventRsvp,
    EventTarget,
    NotificationAudience,
    Notification,
    NotificationReadReceipt,
    NotificationTarget,
    Parent,
    Trainer,
)
from app.schemas import (
    EventAttachmentRead,
    EventChildRsvp,
    EventCommentCreate,
    EventCommentRead,
    EventCreate,
    EventDetailRead,
    EventPatch,
    EventRead,
    EventRsvpParticipant,
    EventRsvpSet,
    EventRsvpSummary,
    EventTargetCreate,
    EventTargetRead,
    ParentBrief,
    TrainerBrief,
)
from app.security import require_trainer_token

router = APIRouter(prefix="/events", tags=["events"])

DEFAULT_NOTIFY_FALLBACK = timedelta(days=7)
LOCAL_TZ = ZoneInfo("Europe/Prague")

_EVENT_TYPE_LABELS = {
    "tournament": "Turnaj",
    "training": "Trénink",
    "meeting": "Schůzka",
    "seminar": "Školení",
    "other": "Akce",
}


def event_now() -> datetime:
    return datetime.now(UTC)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_options():
    return (
        selectinload(Event.author_trainer),
        selectinload(Event.targets),
        selectinload(Event.comments).selectinload(EventComment.author_trainer),
        selectinload(Event.comments).selectinload(EventComment.author_parent),
        selectinload(Event.attachments),
        selectinload(Event.rsvps).selectinload(EventRsvp.trainer),
        selectinload(Event.rsvps).selectinload(EventRsvp.parent),
        selectinload(Event.rsvps).selectinload(EventRsvp.student),
    )


async def _get_branch_or_404(db: AsyncSession, branch_id: int) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch id not found: {branch_id}")
    return branch


def _can_edit(event: Event, viewer: Viewer) -> bool:
    return viewer.kind == "trainer" and event.author_trainer_id == viewer.trainer_id


def _viewer_owns_event(event: Event | None, viewer: Viewer) -> bool:
    return event is not None and _can_edit(event, viewer)


def _visible_to_viewer(event: Event, viewer: Viewer) -> bool:
    if viewer.kind == "trainer" and event.author_trainer_id == viewer.trainer_id:
        return True
    return viewer_can_see_targets(viewer, event.targets)


async def _get_visible_event_or_404(db: AsyncSession, event_id: int, viewer: Viewer) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id).options(*_event_options()))
    event = result.scalar_one_or_none()
    if event is None or not _visible_to_viewer(event, viewer):
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


def _my_rsvp(event: Event, viewer: Viewer):
    if viewer.kind != "trainer":
        return None
    for rsvp in event.rsvps:
        if rsvp.trainer_id == viewer.trainer_id:
            return rsvp.status
    return None


def _my_child_rsvps(event: Event, viewer: Viewer) -> list[EventChildRsvp]:
    if viewer.kind != "parent":
        return []
    status_by_student = {rsvp.student_id: rsvp.status for rsvp in event.rsvps if rsvp.student_id is not None}
    return [
        EventChildRsvp(student_id=child.id, name=child.name, status=status_by_student.get(child.id))
        for child in matched_children(viewer, event.targets)
    ]


def _target_to_read(target: EventTarget) -> EventTargetRead:
    return EventTargetRead(
        id=target.id,
        audience=target.audience,
        branch_id=target.branch_id,
        age_group=target.age_group,
    )


def _authored_by_viewer(comment: EventComment, viewer: Viewer) -> bool:
    if viewer.kind == "trainer":
        return comment.author_trainer_id is not None and comment.author_trainer_id == viewer.trainer_id
    return comment.author_parent_id is not None and comment.author_parent_id == viewer.parent_id


def _comment_to_read(comment: EventComment, viewer: Viewer, can_moderate: bool) -> EventCommentRead:
    created_at = _as_aware_utc(comment.created_at)
    updated_at = _as_aware_utc(comment.updated_at) if comment.updated_at is not None else created_at
    mine = _authored_by_viewer(comment, viewer)
    return EventCommentRead(
        id=comment.id,
        event_id=comment.event_id,
        author_trainer_id=comment.author_trainer_id,
        author_parent_id=comment.author_parent_id,
        body=comment.body,
        created_at=created_at,
        updated_at=updated_at,
        author_trainer=(
            TrainerBrief.model_validate(comment.author_trainer, from_attributes=True)
            if comment.author_trainer is not None
            else None
        ),
        author_parent=(
            ParentBrief.model_validate(comment.author_parent, from_attributes=True)
            if comment.author_parent is not None
            else None
        ),
        can_delete=mine or can_moderate,
        can_edit=mine,
    )


def _attachment_to_read(attachment: EventAttachment, viewer: Viewer, can_moderate: bool) -> EventAttachmentRead:
    mine = (
        viewer.kind == "trainer" and attachment.uploaded_trainer_id == viewer.trainer_id
    ) or (viewer.kind == "parent" and attachment.uploaded_parent_id == viewer.parent_id)
    return EventAttachmentRead(
        id=attachment.id,
        event_id=attachment.event_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        created_at=_as_aware_utc(attachment.created_at),
        can_delete=mine or can_moderate,
    )


def _rsvp_summary(event: Event) -> EventRsvpSummary:
    counts = {"yes": 0, "no": 0, "maybe": 0}
    participants: list[EventRsvpParticipant] = []
    for rsvp in event.rsvps:
        counts[rsvp.status.value] += 1
        if rsvp.trainer is not None:
            participants.append(
                EventRsvpParticipant(
                    kind="trainer",
                    id=rsvp.trainer_id,
                    name=f"{rsvp.trainer.first_name} {rsvp.trainer.last_name}",
                    status=rsvp.status,
                ),
            )
        elif rsvp.parent is not None:
            child_name = (
                f"{rsvp.student.first_name} {rsvp.student.last_name}" if rsvp.student is not None else None
            )
            participants.append(
                EventRsvpParticipant(
                    kind="parent",
                    id=rsvp.parent_id,
                    name=f"{rsvp.parent.first_name} {rsvp.parent.last_name}",
                    status=rsvp.status,
                    student_id=rsvp.student_id,
                    child_name=child_name,
                ),
            )
    return EventRsvpSummary(yes=counts["yes"], no=counts["no"], maybe=counts["maybe"], participants=participants)


def _event_to_read(event: Event, viewer: Viewer) -> EventRead:
    return EventRead(
        id=event.id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        location=event.location,
        starts_at=_as_aware_utc(event.starts_at),
        ends_at=_as_aware_utc(event.ends_at) if event.ends_at is not None else None,
        author_trainer_id=event.author_trainer_id,
        created_at=_as_aware_utc(event.created_at),
        updated_at=_as_aware_utc(event.updated_at),
        author_trainer=(
            TrainerBrief.model_validate(event.author_trainer, from_attributes=True)
            if event.author_trainer is not None
            else None
        ),
        targets=[_target_to_read(target) for target in event.targets],
        can_edit=_can_edit(event, viewer),
        my_rsvp=_my_rsvp(event, viewer),
        my_child_rsvps=_my_child_rsvps(event, viewer),
        comment_count=len(event.comments),
        attachment_count=len(event.attachments),
    )


def _event_to_detail(event: Event, viewer: Viewer) -> EventDetailRead:
    can_moderate = _can_edit(event, viewer)
    base = _event_to_read(event, viewer).model_dump()
    comments = sorted(event.comments, key=lambda c: (c.created_at, c.id))
    attachments = sorted(event.attachments, key=lambda a: (a.created_at, a.id))
    return EventDetailRead(
        **base,
        comments=[_comment_to_read(comment, viewer, can_moderate) for comment in comments],
        attachments=[_attachment_to_read(attachment, viewer, can_moderate) for attachment in attachments],
        rsvp_summary=_rsvp_summary(event) if can_moderate else None,
    )


async def _validate_targets(db: AsyncSession, targets: list[EventTargetCreate]) -> None:
    for target in targets:
        if target.branch_id is not None:
            await _get_branch_or_404(db, target.branch_id)


def _event_target_rows(targets: list[EventTargetCreate]) -> list[EventTarget]:
    return [
        EventTarget(audience=target.audience, branch_id=target.branch_id, age_group=target.age_group)
        for target in targets
    ]


def _notification_payload(event: Event, now: datetime) -> tuple[str, str, datetime]:
    """Return (title, body, visible_until) for the board announcement of an event."""
    starts = _as_aware_utc(event.starts_at)
    visible_until = starts if starts > now else now + DEFAULT_NOTIFY_FALLBACK
    type_label = _EVENT_TYPE_LABELS.get(event.event_type.value, "Akce")
    local = starts.astimezone(LOCAL_TZ)
    when = f"{local.day}. {local.month}. {local.year} {local:%H:%M}"
    body_lines = [f"{type_label}: {event.title}", f"Kdy: {when}"]
    if event.location:
        body_lines.append(f"Kde: {event.location}")
    if any(target.audience == NotificationAudience.parent for target in event.targets):
        body_lines.append("Potvrďte prosím účast svých dětí.")
    return f"Nová akce: {event.title}", "\n".join(body_lines), visible_until


def _notification_targets(event: Event) -> list[NotificationTarget]:
    return [
        NotificationTarget(audience=target.audience, branch_id=target.branch_id, age_group=target.age_group)
        for target in event.targets
    ]


async def _create_event_notification(db: AsyncSession, event: Event, trainer_id: int, now: datetime) -> None:
    """Announce a freshly created event to the same recipients as a board notification."""
    title, body, visible_until = _notification_payload(event, now)
    notification = Notification(
        title=title,
        body=body,
        author_trainer_id=trainer_id,
        event_id=event.id,
        visible_until=visible_until,
        grace_seconds=0,
        last_activity_at=now,
        targets=_notification_targets(event),
        reads=[NotificationReadReceipt(trainer_id=trainer_id, last_read_at=now)],
    )
    db.add(notification)


async def _sync_event_notification(db: AsyncSession, event: Event, now: datetime) -> None:
    """Keep the linked board notification in step with the event after an edit."""
    result = await db.execute(
        select(Notification)
        .where(Notification.event_id == event.id)
        .options(selectinload(Notification.targets)),
    )
    notification = result.scalars().first()
    if notification is None:
        return
    title, body, visible_until = _notification_payload(event, now)
    notification.title = title
    notification.body = body
    notification.visible_until = visible_until
    notification.last_activity_at = now
    notification.targets.clear()
    notification.targets.extend(_notification_targets(event))


async def _notify_event_comment(
    db: AsyncSession,
    event: Event,
    comment: EventComment,
    viewer: Viewer,
    now: datetime,
) -> None:
    """Notify everyone in the event conversation when a new comment is posted.

    Recipients are the organizer plus everyone who has already commented in the
    thread, minus the author of the new comment.
    """
    trainer_ids: set[int] = set()
    parent_ids: set[int] = set()

    if event.author_trainer_id is not None:
        trainer_ids.add(event.author_trainer_id)
    for prior in event.comments:
        if prior.author_trainer_id is not None:
            trainer_ids.add(prior.author_trainer_id)
        if prior.author_parent_id is not None:
            parent_ids.add(prior.author_parent_id)

    if viewer.kind == "trainer":
        trainer_ids.discard(viewer.trainer_id)
    else:
        parent_ids.discard(viewer.parent_id)

    if not trainer_ids and not parent_ids:
        return

    if viewer.kind == "parent":
        parent = await db.get(Parent, viewer.parent_id)
        who = f"{parent.first_name} {parent.last_name}" if parent is not None else "Rodič"
    else:
        trainer = await db.get(Trainer, viewer.trainer_id)
        who = f"{trainer.first_name} {trainer.last_name}" if trainer is not None else "Trenér"

    snippet = comment.body.strip()
    if len(snippet) > 140:
        snippet = snippet[:139] + "…"
    type_label = _EVENT_TYPE_LABELS.get(event.event_type.value, "Akce")

    targets = [
        NotificationTarget(audience=NotificationAudience.trainer, trainer_id=tid) for tid in trainer_ids
    ] + [
        NotificationTarget(audience=NotificationAudience.parent, parent_id=pid) for pid in parent_ids
    ]

    notification = Notification(
        title=f"Nová reakce k akci: {event.title}",
        body=f"{who} napsal(a) k {type_label.lower()} „{event.title}“:\n{snippet}",
        author_trainer_id=None,
        event_id=event.id,
        visible_until=now + DEFAULT_NOTIFY_FALLBACK,
        grace_seconds=0,
        last_activity_at=now,
        targets=targets,
    )
    db.add(notification)


async def _load_detail(db: AsyncSession, event_id: int, viewer: Viewer) -> EventDetailRead:
    result = await db.execute(select(Event).where(Event.id == event_id).options(*_event_options()))
    event = result.scalar_one()
    return _event_to_detail(event, viewer)


@router.get("", response_model=list[EventRead])
async def list_events(
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> list[EventRead]:
    result = await db.execute(
        select(Event).options(*_event_options()).order_by(Event.starts_at.asc(), Event.id.asc()),
    )
    events = result.scalars().unique().all()
    visible = [event for event in events if _visible_to_viewer(event, viewer)]
    return [_event_to_read(event, viewer) for event in visible]


@router.post("", response_model=EventDetailRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
    now: datetime = Depends(event_now),
) -> EventDetailRead:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail=f"Trainer id not found: {trainer_id}")
    await _validate_targets(db, payload.targets)

    event = Event(
        title=payload.title,
        description=payload.description,
        event_type=payload.event_type,
        location=payload.location,
        starts_at=_as_aware_utc(payload.starts_at),
        ends_at=_as_aware_utc(payload.ends_at) if payload.ends_at is not None else None,
        author_trainer_id=trainer_id,
        targets=_event_target_rows(payload.targets),
    )
    db.add(event)
    await db.flush()
    await _create_event_notification(db, event, trainer_id, now)
    await db.commit()

    return await _load_detail(db, event.id, Viewer(kind="trainer", trainer_id=trainer_id))


@router.get("/{event_id}", response_model=EventDetailRead)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> EventDetailRead:
    event = await _get_visible_event_or_404(db, event_id, viewer)
    return _event_to_detail(event, viewer)


@router.patch("/{event_id}", response_model=EventDetailRead)
async def update_event(
    event_id: int,
    payload: EventPatch,
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
    now: datetime = Depends(event_now),
) -> EventDetailRead:
    event = await db.get(Event, event_id, options=[selectinload(Event.targets)])
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    if event.author_trainer_id != trainer_id:
        raise HTTPException(status_code=403, detail="Only the author can edit this event.")

    data = payload.model_dump(exclude_unset=True)
    if data.get("targets") is not None:
        if not payload.targets:
            raise HTTPException(status_code=422, detail="Event needs at least one target.")
        await _validate_targets(db, payload.targets)

    starts = _as_aware_utc(payload.starts_at) if payload.starts_at is not None else _as_aware_utc(event.starts_at)
    ends = event.ends_at
    if "ends_at" in data:
        ends = _as_aware_utc(payload.ends_at) if payload.ends_at is not None else None
    if ends is not None and _as_aware_utc(ends) < starts:
        raise HTTPException(status_code=422, detail="ends_at must be at or after starts_at.")

    for field in ("title", "description", "event_type", "location"):
        if field in data:
            setattr(event, field, data[field])
    if payload.starts_at is not None:
        event.starts_at = starts
    if "ends_at" in data:
        event.ends_at = ends
    if data.get("targets") is not None:
        event.targets.clear()
        event.targets.extend(_event_target_rows(payload.targets))

    await _sync_event_notification(db, event, now)
    await db.commit()
    return await _load_detail(db, event_id, Viewer(kind="trainer", trainer_id=trainer_id))


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
) -> None:
    event = await db.get(Event, event_id, options=[selectinload(Event.attachments)])
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    if event.author_trainer_id != trainer_id:
        raise HTTPException(status_code=403, detail="Only the author can delete this event.")
    # Remove attachment blobs from disk (ORM cascade only clears DB rows).
    upload_dir = Path(settings.upload_dir)
    for attachment in event.attachments:
        path = upload_dir / attachment.stored_name
        if path.exists():
            path.unlink()
    # Remove the linked announcement notification(s) too, so no dangling board entry survives.
    linked = await db.execute(select(Notification).where(Notification.event_id == event_id))
    for notification in linked.scalars():
        await db.delete(notification)
    await db.delete(event)
    await db.commit()


@router.post("/{event_id}/rsvp", response_model=EventDetailRead)
async def set_rsvp(
    event_id: int,
    payload: EventRsvpSet,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> EventDetailRead:
    event = await _get_visible_event_or_404(db, event_id, viewer)

    if viewer.kind == "trainer":
        if len(payload.responses) != 1 or payload.responses[0].student_id is not None:
            raise HTTPException(status_code=422, detail="Trainers respond once, without a student_id.")
        status_value = payload.responses[0].status
        existing = next((r for r in event.rsvps if r.trainer_id == viewer.trainer_id), None)
        if existing is not None:
            existing.status = status_value
        else:
            db.add(EventRsvp(event_id=event_id, trainer_id=viewer.trainer_id, status=status_value))
    else:
        allowed_ids = {child.id for child in matched_children(viewer, event.targets)}
        for item in payload.responses:
            if item.student_id is None:
                raise HTTPException(status_code=422, detail="Parents must respond per child (student_id required).")
            if item.student_id not in allowed_ids:
                raise HTTPException(
                    status_code=403,
                    detail="You can only respond for your own children targeted by this event.",
                )
        existing_by_student = {r.student_id: r for r in event.rsvps if r.parent_id == viewer.parent_id}
        for item in payload.responses:
            existing = existing_by_student.get(item.student_id)
            if existing is not None:
                existing.status = item.status
            else:
                db.add(
                    EventRsvp(
                        event_id=event_id,
                        parent_id=viewer.parent_id,
                        student_id=item.student_id,
                        status=item.status,
                    ),
                )
    await db.commit()
    db.expire_all()
    return await _load_detail(db, event_id, viewer)


@router.post("/{event_id}/comments", response_model=EventCommentRead, status_code=status.HTTP_201_CREATED)
async def create_event_comment(
    event_id: int,
    payload: EventCommentCreate,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> EventCommentRead:
    event = await _get_visible_event_or_404(db, event_id, viewer)
    comment = EventComment(
        event_id=event_id,
        author_trainer_id=viewer.trainer_id if viewer.kind == "trainer" else None,
        author_parent_id=viewer.parent_id if viewer.kind == "parent" else None,
        body=payload.body,
    )
    db.add(comment)
    await _notify_event_comment(db, event, comment, viewer, event_now())
    await db.commit()

    result = await db.execute(
        select(EventComment)
        .where(EventComment.id == comment.id)
        .options(selectinload(EventComment.author_trainer), selectinload(EventComment.author_parent)),
    )
    return _comment_to_read(result.scalar_one(), viewer, _can_edit(event, viewer))


@router.patch("/{event_id}/comments/{comment_id}", response_model=EventCommentRead)
async def update_event_comment(
    event_id: int,
    comment_id: int,
    payload: EventCommentCreate,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> EventCommentRead:
    await _get_visible_event_or_404(db, event_id, viewer)
    comment = await db.get(
        EventComment,
        comment_id,
        options=[selectinload(EventComment.author_trainer), selectinload(EventComment.author_parent)],
    )
    if comment is None or comment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if not _authored_by_viewer(comment, viewer):
        raise HTTPException(status_code=403, detail="Only the author can edit this comment.")
    comment.body = payload.body
    await db.commit()
    result = await db.execute(
        select(EventComment)
        .where(EventComment.id == comment.id)
        .options(selectinload(EventComment.author_trainer), selectinload(EventComment.author_parent)),
    )
    event = await db.get(Event, event_id)
    return _comment_to_read(result.scalar_one(), viewer, _viewer_owns_event(event, viewer))


@router.delete("/{event_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_comment(
    event_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> None:
    event = await _get_visible_event_or_404(db, event_id, viewer)
    comment = await db.get(EventComment, comment_id)
    if comment is None or comment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if not _authored_by_viewer(comment, viewer) and not _viewer_owns_event(event, viewer):
        raise HTTPException(status_code=403, detail="You cannot delete this comment.")
    await db.delete(comment)
    await db.commit()


@router.post(
    "/{event_id}/attachments",
    response_model=EventAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    event_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> EventAttachmentRead:
    event = await _get_visible_event_or_404(db, event_id, viewer)
    if viewer.kind != "trainer":
        raise HTTPException(status_code=403, detail="Only trainers can upload attachments.")
    # Read in chunks so an oversized body is rejected without buffering it all in memory.
    max_bytes = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="File too large.")
        chunks.append(chunk)
    contents = b"".join(chunks)
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file.")

    stored_name = uuid.uuid4().hex
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / stored_name
    dest.write_bytes(contents)

    attachment = EventAttachment(
        event_id=event_id,
        filename=(file.filename or "soubor")[:255],
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(contents),
        stored_name=stored_name,
        uploaded_trainer_id=viewer.trainer_id if viewer.kind == "trainer" else None,
        uploaded_parent_id=viewer.parent_id if viewer.kind == "parent" else None,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return _attachment_to_read(attachment, viewer, _can_edit(event, viewer))


@router.get("/{event_id}/attachments/{attachment_id}/download")
async def download_attachment(
    event_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> FileResponse:
    await _get_visible_event_or_404(db, event_id, viewer)
    attachment = await db.get(EventAttachment, attachment_id)
    if attachment is None or attachment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    path = Path(settings.upload_dir) / attachment.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on server.")
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename)


@router.delete("/{event_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    event_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> None:
    event = await _get_visible_event_or_404(db, event_id, viewer)
    attachment = await db.get(EventAttachment, attachment_id)
    if attachment is None or attachment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    mine = (
        viewer.kind == "trainer" and attachment.uploaded_trainer_id == viewer.trainer_id
    ) or (viewer.kind == "parent" and attachment.uploaded_parent_id == viewer.parent_id)
    if not mine and not _viewer_owns_event(event, viewer):
        raise HTTPException(status_code=403, detail="You cannot delete this attachment.")
    path = Path(settings.upload_dir) / attachment.stored_name
    if path.exists():
        path.unlink()
    await db.delete(attachment)
    await db.commit()
