from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import Viewer, get_viewer, viewer_can_see_targets
from app.models import (
    Branch,
    Notification,
    NotificationAudience,
    NotificationComment,
    NotificationReadReceipt,
    NotificationTarget,
    Parent,
    Trainer,
)
from app.schemas import (
    NotificationCommentCreate,
    NotificationCommentRead,
    NotificationCreate,
    NotificationPatch,
    NotificationRead,
    NotificationTargetCreate,
    NotificationTargetRead,
    ParentBrief,
    ParentNotificationCreate,
    TrainerBrief,
)
from app.security import require_trainer_token

PARENT_MESSAGE_VISIBLE_FOR = timedelta(days=30)
from app.training_notify import TRAINING_SCHEDULE_ALERT_TITLES

router = APIRouter(prefix="/notifications", tags=["notifications"])

DEFAULT_VISIBLE_FOR = timedelta(days=7)


def notification_now() -> datetime:
    return datetime.now(UTC)


async def _get_trainer_or_404(db: AsyncSession, trainer_id: int) -> Trainer:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail=f"Trainer id not found: {trainer_id}")
    return trainer


async def _get_branch_or_404(db: AsyncSession, branch_id: int) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch id not found: {branch_id}")
    return branch


def _notification_options():
    return (
        selectinload(Notification.author_trainer),
        selectinload(Notification.author_parent),
        selectinload(Notification.targets),
        selectinload(Notification.comments).selectinload(NotificationComment.author_trainer),
        selectinload(Notification.comments).selectinload(NotificationComment.author_parent),
        selectinload(Notification.reads),
    )


async def _get_visible_notification_or_404(
    db: AsyncSession,
    notification_id: int,
    viewer: Viewer,
    now: datetime,
) -> Notification:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id).options(*_notification_options()),
    )
    notification = result.scalar_one_or_none()
    if (
        notification is None
        or not _visible_to_viewer(notification, viewer)
        or not _visible_on_board(notification, now)
    ):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return notification


def _authored_by_viewer(comment: NotificationComment, viewer: Viewer) -> bool:
    if viewer.kind == "trainer":
        return comment.author_trainer_id is not None and comment.author_trainer_id == viewer.trainer_id
    return comment.author_parent_id is not None and comment.author_parent_id == viewer.parent_id


def _comment_to_read(comment: NotificationComment, viewer: Viewer) -> NotificationCommentRead:
    created_at = _as_aware_utc(comment.created_at)
    updated_at = _as_aware_utc(comment.updated_at) if comment.updated_at is not None else created_at
    mine = _authored_by_viewer(comment, viewer)
    return NotificationCommentRead(
        id=comment.id,
        notification_id=comment.notification_id,
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
        can_delete=mine,
        can_edit=mine,
    )


def _receipt_matches_viewer(receipt: NotificationReadReceipt, viewer: Viewer) -> bool:
    if viewer.kind == "trainer":
        return receipt.trainer_id == viewer.trainer_id
    return receipt.parent_id == viewer.parent_id


def _touch_read_receipt(notification: Notification, viewer: Viewer, now: datetime) -> None:
    receipt = next((row for row in notification.reads if _receipt_matches_viewer(row, viewer)), None)
    if receipt is not None:
        receipt.last_read_at = now
        return
    # Avoid duplicate pending rows in the same unit of work (unique on viewer).
    if viewer.kind == "trainer":
        if any(row.trainer_id == viewer.trainer_id for row in notification.reads):
            return
        notification.reads.append(NotificationReadReceipt(trainer_id=viewer.trainer_id, last_read_at=now))
    else:
        if any(row.parent_id == viewer.parent_id for row in notification.reads):
            return
        notification.reads.append(NotificationReadReceipt(parent_id=viewer.parent_id, last_read_at=now))


def _is_unread(notification: Notification, viewer: Viewer) -> bool:
    activity = _as_aware_utc(notification.last_activity_at)
    for receipt in notification.reads:
        if _receipt_matches_viewer(receipt, viewer):
            return _as_aware_utc(receipt.last_read_at) < activity
    return True


def _has_read(notification: Notification, viewer: Viewer) -> bool:
    return any(_receipt_matches_viewer(receipt, viewer) for receipt in notification.reads)


def _target_to_read(target: NotificationTarget) -> NotificationTargetRead:
    return NotificationTargetRead(
        id=target.id,
        audience=target.audience,
        branch_id=target.branch_id,
        age_group=target.age_group,
    )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hide_after(notification: Notification) -> datetime:
    return _as_aware_utc(notification.visible_until) + timedelta(seconds=notification.grace_seconds)


def _visibility_state(notification: Notification, now: datetime) -> str:
    return "expired" if now >= _as_aware_utc(notification.visible_until) else "active"


def _last_comment_summary(notification: Notification) -> tuple[str | None, str | None]:
    if not notification.comments:
        return None, None
    latest = max(notification.comments, key=lambda c: c.created_at)
    if latest.author_trainer is not None:
        who = f"{latest.author_trainer.first_name} {latest.author_trainer.last_name}"
    elif latest.author_parent is not None:
        who = f"{latest.author_parent.first_name} {latest.author_parent.last_name} (rodič)"
    else:
        who = "Neznámý"
    preview = latest.body.strip()
    if len(preview) > 120:
        preview = preview[:119] + "…"
    return who, preview


def _notification_to_read(notification: Notification, viewer: Viewer, now: datetime) -> NotificationRead:
    hide_after = _hide_after(notification)
    can_modify = _can_modify_notification(notification, viewer)
    last_comment_author, last_comment_preview = _last_comment_summary(notification)
    return NotificationRead(
        id=notification.id,
        title=notification.title,
        body=notification.body,
        author_trainer_id=notification.author_trainer_id,
        author_parent_id=notification.author_parent_id,
        event_id=notification.event_id,
        training_group_id=notification.training_group_id,
        training_date=notification.training_date,
        visible_until=_as_aware_utc(notification.visible_until),
        hide_after=hide_after,
        visibility_state=_visibility_state(notification, now),
        created_at=_as_aware_utc(notification.created_at),
        updated_at=_as_aware_utc(notification.updated_at),
        last_activity_at=_as_aware_utc(notification.last_activity_at),
        author_trainer=(
            TrainerBrief.model_validate(notification.author_trainer, from_attributes=True)
            if notification.author_trainer is not None
            else None
        ),
        author_parent=(
            ParentBrief.model_validate(notification.author_parent, from_attributes=True)
            if notification.author_parent is not None
            else None
        ),
        targets=[_target_to_read(target) for target in notification.targets],
        can_delete=can_modify,
        can_edit=can_modify,
        unread=_is_unread(notification, viewer),
        has_read=_has_read(notification, viewer),
        comment_count=len(notification.comments),
        last_comment_author=last_comment_author,
        last_comment_preview=last_comment_preview,
    )


def _can_modify_notification(notification: Notification, viewer: Viewer) -> bool:
    """Who may edit/delete a notification.

    - Parent-authored ("napsat trenérům"): the author parent, or any trainer.
    - Trainer-authored: only the author trainer (unchanged behavior).
    """
    if viewer.kind == "trainer":
        if notification.author_parent_id is not None:
            return True
        return notification.author_trainer_id == viewer.trainer_id
    return notification.author_parent_id is not None and notification.author_parent_id == viewer.parent_id


def _is_parent_only_personal(notification: Notification) -> bool:
    if not notification.targets:
        return False
    return all(
        target.audience == NotificationAudience.parent and target.parent_id is not None
        for target in notification.targets
    )


def _is_training_schedule_alert(notification: Notification) -> bool:
    return notification.title in TRAINING_SCHEDULE_ALERT_TITLES


def _visible_to_viewer(notification: Notification, viewer: Viewer) -> bool:
    if (
        viewer.kind == "trainer"
        and notification.author_trainer_id == viewer.trainer_id
        and not _is_training_schedule_alert(notification)
        and not _is_parent_only_personal(notification)
    ):
        return True
    # A parent always sees the message they sent to trainers, even though it only
    # targets the trainer audience.
    if (
        viewer.kind == "parent"
        and notification.author_parent_id is not None
        and notification.author_parent_id == viewer.parent_id
    ):
        return True
    return viewer_can_see_targets(viewer, notification.targets)


def _visible_on_board(notification: Notification, now: datetime) -> bool:
    return now < _hide_after(notification)


async def _validate_targets(db: AsyncSession, payload: NotificationCreate) -> None:
    for target in payload.targets:
        if target.branch_id is not None:
            await _get_branch_or_404(db, target.branch_id)


def _target_rows(payload: NotificationCreate) -> list[NotificationTarget]:
    return [_target_row(target) for target in payload.targets]


def _target_row(target: NotificationTargetCreate) -> NotificationTarget:
    return NotificationTarget(
        audience=target.audience,
        branch_id=target.branch_id,
        age_group=target.age_group,
    )


def _duration_delta(amount: int, unit: str) -> timedelta:
    if unit == "seconds":
        return timedelta(seconds=amount)
    if unit == "minutes":
        return timedelta(minutes=amount)
    if unit == "hours":
        return timedelta(hours=amount)
    if unit == "days":
        return timedelta(days=amount)
    if unit == "weeks":
        return timedelta(weeks=amount)
    if unit == "months":
        return timedelta(days=amount * 30)
    raise HTTPException(status_code=422, detail="Invalid duration_unit.")


def _resolve_visible_until(payload: NotificationCreate, now: datetime) -> datetime:
    if payload.visible_until is not None:
        return _as_aware_utc(payload.visible_until)
    if payload.duration_amount is not None and payload.duration_unit is not None:
        return now + _duration_delta(payload.duration_amount, payload.duration_unit)
    return now + DEFAULT_VISIBLE_FOR


def _resolve_grace_seconds(payload: NotificationCreate) -> int:
    if not payload.keep_after_expiry or payload.grace_amount is None or payload.grace_unit is None:
        return 0
    return int(_duration_delta(payload.grace_amount, payload.grace_unit).total_seconds())


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> list[NotificationRead]:
    result = await db.execute(
        select(Notification)
        .options(*_notification_options())
        .order_by(Notification.created_at.desc(), Notification.id.desc()),
    )
    notifications = result.scalars().unique().all()

    stale = [row for row in notifications if now >= _hide_after(row)]
    if stale:
        for row in stale:
            await db.delete(row)
        await db.commit()
        stale_ids = {row.id for row in stale}
        notifications = [row for row in notifications if row.id not in stale_ids]

    visible = [
        row
        for row in notifications
        if _visible_to_viewer(row, viewer) and _visible_on_board(row, now)
    ]
    return [_notification_to_read(row, viewer, now) for row in visible]


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
    now: datetime = Depends(notification_now),
) -> NotificationRead:
    await _get_trainer_or_404(db, trainer_id)
    await _validate_targets(db, payload)

    notification = Notification(
        title=payload.title,
        body=payload.body,
        author_trainer_id=trainer_id,
        visible_until=_resolve_visible_until(payload, now),
        grace_seconds=_resolve_grace_seconds(payload),
        last_activity_at=now,
        targets=_target_rows(payload),
        reads=[NotificationReadReceipt(trainer_id=trainer_id, last_read_at=now)],
    )
    db.add(notification)
    await db.commit()

    result = await db.execute(
        select(Notification).where(Notification.id == notification.id).options(*_notification_options()),
    )
    return _notification_to_read(result.scalar_one(), Viewer(kind="trainer", trainer_id=trainer_id), now)


@router.post("/to-trainers", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_parent_notification(
    payload: ParentNotificationCreate,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> NotificationRead:
    if viewer.kind != "parent" or viewer.parent_id is None:
        raise HTTPException(status_code=403, detail="Only parents can write to trainers.")
    parent = await db.get(Parent, viewer.parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    if payload.branch_id is not None:
        await _get_branch_or_404(db, payload.branch_id)

    notification = Notification(
        title=payload.title,
        body=payload.body,
        author_parent_id=viewer.parent_id,
        visible_until=now + PARENT_MESSAGE_VISIBLE_FOR,
        grace_seconds=0,
        last_activity_at=now,
        targets=[NotificationTarget(audience=NotificationAudience.trainer, branch_id=payload.branch_id)],
        reads=[NotificationReadReceipt(parent_id=viewer.parent_id, last_read_at=now)],
    )
    db.add(notification)
    await db.commit()

    result = await db.execute(
        select(Notification).where(Notification.id == notification.id).options(*_notification_options()),
    )
    return _notification_to_read(result.scalar_one(), viewer, now)


@router.patch("/{notification_id}", response_model=NotificationRead)
async def update_notification(
    notification_id: int,
    payload: NotificationPatch,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> NotificationRead:
    notification = await _get_visible_notification_or_404(db, notification_id, viewer, now)
    if not _can_modify_notification(notification, viewer):
        raise HTTPException(status_code=403, detail="You cannot edit this notification.")

    if payload.title is not None:
        notification.title = payload.title
    if payload.body is not None:
        notification.body = payload.body
    await db.commit()

    result = await db.execute(
        select(Notification).where(Notification.id == notification.id).options(*_notification_options()),
    )
    return _notification_to_read(result.scalar_one(), viewer, now)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
) -> None:
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if not _can_modify_notification(notification, viewer):
        raise HTTPException(status_code=403, detail="You cannot delete this notification.")
    await db.delete(notification)
    await db.commit()


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> NotificationRead:
    notification = await _get_visible_notification_or_404(db, notification_id, viewer, now)

    _touch_read_receipt(notification, viewer, now)
    await db.commit()

    return _notification_to_read(notification, viewer, now)


_COMMENT_AUTHOR_OPTIONS = (
    selectinload(NotificationComment.author_trainer),
    selectinload(NotificationComment.author_parent),
)


@router.get("/{notification_id}/comments", response_model=list[NotificationCommentRead])
async def list_comments(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> list[NotificationCommentRead]:
    await _get_visible_notification_or_404(db, notification_id, viewer, now)

    result = await db.execute(
        select(NotificationComment)
        .where(NotificationComment.notification_id == notification_id)
        .options(*_COMMENT_AUTHOR_OPTIONS)
        .order_by(NotificationComment.created_at.asc(), NotificationComment.id.asc()),
    )
    comments = result.scalars().all()
    return [_comment_to_read(comment, viewer) for comment in comments]


@router.post(
    "/{notification_id}/comments",
    response_model=NotificationCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    notification_id: int,
    payload: NotificationCommentCreate,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> NotificationCommentRead:
    notification = await _get_visible_notification_or_404(db, notification_id, viewer, now)
    if notification.event_id is not None:
        raise HTTPException(
            status_code=409,
            detail="K této akci pište komentáře v plánovači akcí.",
        )
    if _visibility_state(notification, now) == "expired":
        raise HTTPException(status_code=409, detail="Notification expired; reactions are closed.")

    comment = NotificationComment(
        notification_id=notification_id,
        author_trainer_id=viewer.trainer_id if viewer.kind == "trainer" else None,
        author_parent_id=viewer.parent_id if viewer.kind == "parent" else None,
        body=payload.body,
    )
    db.add(comment)
    notification.last_activity_at = now
    _touch_read_receipt(notification, viewer, now)
    await db.commit()

    result = await db.execute(
        select(NotificationComment)
        .where(NotificationComment.id == comment.id)
        .options(*_COMMENT_AUTHOR_OPTIONS),
    )
    return _comment_to_read(result.scalar_one(), viewer)


@router.patch("/{notification_id}/comments/{comment_id}", response_model=NotificationCommentRead)
async def update_comment(
    notification_id: int,
    comment_id: int,
    payload: NotificationCommentCreate,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> NotificationCommentRead:
    notification = await _get_visible_notification_or_404(db, notification_id, viewer, now)
    comment = await db.get(NotificationComment, comment_id, options=list(_COMMENT_AUTHOR_OPTIONS))
    if comment is None or comment.notification_id != notification_id:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if not _authored_by_viewer(comment, viewer):
        raise HTTPException(status_code=403, detail="Only the author can edit this comment.")

    comment.body = payload.body
    notification.last_activity_at = now
    _touch_read_receipt(notification, viewer, now)
    await db.commit()

    result = await db.execute(
        select(NotificationComment)
        .where(NotificationComment.id == comment.id)
        .options(*_COMMENT_AUTHOR_OPTIONS),
    )
    return _comment_to_read(result.scalar_one(), viewer)


@router.delete("/{notification_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    notification_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    viewer: Viewer = Depends(get_viewer),
    now: datetime = Depends(notification_now),
) -> None:
    notification = await _get_visible_notification_or_404(db, notification_id, viewer, now)
    comment = await db.get(NotificationComment, comment_id)
    if comment is None or comment.notification_id != notification_id:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if not _authored_by_viewer(comment, viewer):
        raise HTTPException(status_code=403, detail="Only the author can delete this comment.")
    await db.delete(comment)
    await db.flush()
    remaining = [c for c in notification.comments if c.id != comment_id]
    if remaining:
        notification.last_activity_at = max(_as_aware_utc(c.created_at) for c in remaining)
    else:
        notification.last_activity_at = _as_aware_utc(notification.created_at)
    await db.commit()
