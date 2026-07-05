from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Notification, NotificationAudience, NotificationTarget, Parent, Trainer
from app.schemas import (
    NotificationCreate,
    NotificationRead,
    NotificationTargetCreate,
    NotificationTargetRead,
    TrainerBrief,
)
from app.security import require_trainer_token

router = APIRouter(prefix="/notifications", tags=["notifications"])

DEFAULT_VISIBLE_FOR = timedelta(days=7)
EXPIRED_VISIBLE_FOR = timedelta(days=7)


def notification_now() -> datetime:
    return datetime.now(UTC)


async def _get_trainer_or_404(db: AsyncSession, trainer_id: int) -> Trainer:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail=f"Trainer id not found: {trainer_id}")
    return trainer


async def _get_parent_or_404(db: AsyncSession, parent_id: int) -> Parent:
    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"Parent id not found: {parent_id}")
    return parent


def _notification_options():
    return (
        selectinload(Notification.author_trainer),
        selectinload(Notification.targets),
    )


def _target_to_read(target: NotificationTarget) -> NotificationTargetRead:
    return NotificationTargetRead(
        id=target.id,
        audience=target.audience,
        trainer_id=target.trainer_id,
        parent_id=target.parent_id,
    )


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hide_after(notification: Notification) -> datetime:
    return _as_aware_utc(notification.visible_until) + EXPIRED_VISIBLE_FOR


def _visibility_state(notification: Notification, now: datetime) -> str:
    return "expired" if now >= _as_aware_utc(notification.visible_until) else "active"


def _notification_to_read(notification: Notification, current_trainer_id: int, now: datetime) -> NotificationRead:
    hide_after = _hide_after(notification)
    return NotificationRead(
        id=notification.id,
        title=notification.title,
        body=notification.body,
        author_trainer_id=notification.author_trainer_id,
        visible_until=notification.visible_until,
        hide_after=hide_after,
        visibility_state=_visibility_state(notification, now),
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        author_trainer=(
            TrainerBrief.model_validate(notification.author_trainer, from_attributes=True)
            if notification.author_trainer is not None
            else None
        ),
        targets=[_target_to_read(target) for target in notification.targets],
        can_delete=notification.author_trainer_id == current_trainer_id,
    )


def _visible_to_trainer(notification: Notification, trainer_id: int) -> bool:
    if notification.author_trainer_id == trainer_id:
        return True
    for target in notification.targets:
        if target.audience != NotificationAudience.trainer:
            continue
        if target.trainer_id is None or target.trainer_id == trainer_id:
            return True
    return False


def _visible_on_board(notification: Notification, now: datetime) -> bool:
    return now < _hide_after(notification)


async def _validate_targets(db: AsyncSession, payload: NotificationCreate) -> None:
    for target in payload.targets:
        if target.trainer_id is not None:
            await _get_trainer_or_404(db, target.trainer_id)
        if target.parent_id is not None:
            await _get_parent_or_404(db, target.parent_id)


def _target_rows(payload: NotificationCreate) -> list[NotificationTarget]:
    targets: list[NotificationTarget] = []
    for audience in payload.audiences:
        targets.append(NotificationTarget(audience=audience))
    targets.extend(_individual_target_row(target) for target in payload.targets)
    return targets


def _individual_target_row(target: NotificationTargetCreate) -> NotificationTarget:
    return NotificationTarget(
        audience=target.audience,
        trainer_id=target.trainer_id,
        parent_id=target.parent_id,
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


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
    now: datetime = Depends(notification_now),
) -> list[NotificationRead]:
    result = await db.execute(
        select(Notification)
        .options(*_notification_options())
        .order_by(Notification.created_at.desc(), Notification.id.desc()),
    )
    notifications = result.scalars().unique().all()
    visible = [
        row
        for row in notifications
        if _visible_to_trainer(row, trainer_id) and _visible_on_board(row, now)
    ]
    return [_notification_to_read(row, trainer_id, now) for row in visible]


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
        targets=_target_rows(payload),
    )
    db.add(notification)
    await db.commit()

    result = await db.execute(
        select(Notification).where(Notification.id == notification.id).options(*_notification_options()),
    )
    return _notification_to_read(result.scalar_one(), trainer_id, now)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    trainer_id: int = Depends(require_trainer_token),
) -> None:
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if notification.author_trainer_id != trainer_id:
        raise HTTPException(status_code=403, detail="Only the author can delete this notification.")
    await db.delete(notification)
    await db.commit()
