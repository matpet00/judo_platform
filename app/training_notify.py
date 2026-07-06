"""Parent notifications for training schedule changes."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Notification,
    NotificationAudience,
    NotificationTarget,
    Parent,
    Student,
    Trainer,
    TrainingGroup,
)

CANCEL_NOTICE_DAYS = 30
TRAINING_SCHEDULE_ALERT_TITLES = frozenset({"Zrušený trénink", "Trénink zrušen"})


def _format_training_when(session_date: date, start: time, end: time) -> str:
    return f"{session_date.strftime('%d.%m.%Y')} {start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


async def _parents_on_roster(db: AsyncSession, group: TrainingGroup) -> list[Parent]:
    if not group.students:
        return []
    student_ids = [s.id for s in group.students]
    result = await db.execute(
        select(Student).where(Student.id.in_(student_ids)).options(selectinload(Student.parents)),
    )
    seen: dict[int, Parent] = {}
    for student in result.scalars().unique().all():
        for parent in student.parents:
            seen[parent.id] = parent
    return list(seen.values())


async def _other_trainers_on_branch(
    db: AsyncSession,
    branch_id: int,
    exclude_trainer_id: int | None,
) -> list[Trainer]:
    result = await db.execute(select(Trainer).options(selectinload(Trainer.branches)))
    trainers: list[Trainer] = []
    for trainer in result.scalars().unique().all():
        if exclude_trainer_id is not None and trainer.id == exclude_trainer_id:
            continue
        if any(branch.id == branch_id for branch in trainer.branches):
            trainers.append(trainer)
    return trainers


def _schedule_alert_targets(
    parents: list[Parent],
    other_trainers: list[Trainer],
) -> list[NotificationTarget]:
    targets = [
        NotificationTarget(audience=NotificationAudience.parent, parent_id=parent.id)
        for parent in parents
    ]
    targets.extend(
        NotificationTarget(audience=NotificationAudience.trainer, trainer_id=trainer.id)
        for trainer in other_trainers
    )
    return targets


async def notify_training_term_canceled(
    db: AsyncSession,
    group: TrainingGroup,
    session_date: date,
    trainer_id: int | None = None,
) -> None:
    parents = await _parents_on_roster(db, group)
    other_trainers = await _other_trainers_on_branch(db, group.branch_id, exclude_trainer_id=trainer_id)
    if not parents and not other_trainers:
        return
    now = datetime.now(UTC)
    visible_until = now + timedelta(days=CANCEL_NOTICE_DAYS)
    branch_name = group.branch.name if group.branch is not None else ""
    where = f" ({branch_name})" if branch_name else ""
    when = _format_training_when(session_date, group.start_time, group.end_time)
    notification = Notification(
        title="Zrušený trénink",
        body=f"Trénink {group.name}{where} dne {when} byl zrušen.",
        author_trainer_id=trainer_id,
        training_group_id=group.id,
        training_date=session_date,
        visible_until=visible_until,
        grace_seconds=0,
        last_activity_at=now,
        targets=_schedule_alert_targets(parents, other_trainers),
    )
    db.add(notification)


async def notify_training_series_deleted(
    db: AsyncSession,
    group: TrainingGroup,
    trainer_id: int | None = None,
) -> None:
    parents = await _parents_on_roster(db, group)
    other_trainers = await _other_trainers_on_branch(db, group.branch_id, exclude_trainer_id=trainer_id)
    if not parents and not other_trainers:
        return
    now = datetime.now(UTC)
    visible_until = now + timedelta(days=CANCEL_NOTICE_DAYS)
    branch_name = group.branch.name if group.branch is not None else ""
    where = f" ({branch_name})" if branch_name else ""
    notification = Notification(
        title="Trénink zrušen",
        body=f"Opakovaný trénink {group.name}{where} byl trvale zrušen (včetně budoucích termínů).",
        author_trainer_id=trainer_id,
        visible_until=visible_until,
        grace_seconds=0,
        last_activity_at=now,
        targets=_schedule_alert_targets(parents, other_trainers),
    )
    db.add(notification)
