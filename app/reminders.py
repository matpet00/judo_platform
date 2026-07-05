"""Background sweep that reminds invited participants of upcoming events.

For each event whose start falls within the reminder lead window and that has
not been reminded yet, we create a personal notification for every targeted
parent and trainer, then flag `reminder_sent` so it fires exactly once. Parents
who still have an un-responded targeted child get a "please vote" call-to-action;
everyone else gets a plain "event is coming up" reminder.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_maker
from app.deps import Viewer, ViewerChild, matched_children, participants_matching_targets
from app.models import Event, Notification, NotificationAudience, NotificationTarget

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Europe/Prague")
REMINDER_VISIBLE_DAYS = 7


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _when_label(starts_at: datetime) -> str:
    local = _as_aware_utc(starts_at).astimezone(LOCAL_TZ)
    return f"{local.day}. {local.month}. {local.year} {local:%H:%M}"


async def run_reminder_sweep() -> int:
    """Create reminder notifications for events entering the lead window. Returns count of events processed."""
    async with async_session_maker() as db:
        now = datetime.now(UTC)
        lead_cutoff = now + timedelta(hours=settings.event_reminder_lead_hours)

        result = await db.execute(
            select(Event)
            .where(Event.reminder_sent.is_(False))
            .options(selectinload(Event.targets), selectinload(Event.rsvps)),
        )
        events = result.scalars().unique().all()
        due = [e for e in events if now < _as_aware_utc(e.starts_at) <= lead_cutoff]

        for event in due:
            parents, trainers = await participants_matching_targets(db, event.targets)
            responded = {rsvp.student_id for rsvp in event.rsvps if rsvp.student_id is not None}
            when = _when_label(event.starts_at)
            visible_until = now + timedelta(days=REMINDER_VISIBLE_DAYS)

            for parent in parents:
                child_views = [
                    ViewerChild(
                        id=c.id,
                        name=f"{c.first_name} {c.last_name}",
                        branch_ids={b.id for b in c.branches},
                        age_group=c.age_group,
                    )
                    for c in parent.children
                ]
                viewer = Viewer(kind="parent", parent_id=parent.id, children=child_views)
                pending = [c for c in matched_children(viewer, event.targets) if c.id not in responded]
                if pending:
                    body = (
                        f"Akce {event.title} se blíží ({when}). "
                        "Potvrďte prosím účast svých dětí."
                    )
                else:
                    body = f"Akce {event.title} se blíží ({when})."
                db.add(
                    Notification(
                        title=f"Připomínka: {event.title}",
                        body=body,
                        author_trainer_id=None,
                        event_id=event.id,
                        visible_until=visible_until,
                        grace_seconds=0,
                        last_activity_at=now,
                        targets=[NotificationTarget(audience=NotificationAudience.parent, parent_id=parent.id)],
                    ),
                )

            for trainer in trainers:
                db.add(
                    Notification(
                        title=f"Připomínka: {event.title}",
                        body=f"Akce {event.title} se blíží ({when}).",
                        author_trainer_id=None,
                        event_id=event.id,
                        visible_until=visible_until,
                        grace_seconds=0,
                        last_activity_at=now,
                        targets=[NotificationTarget(audience=NotificationAudience.trainer, trainer_id=trainer.id)],
                    ),
                )

            event.reminder_sent = True

        await db.commit()
        return len(due)


async def reminder_loop() -> None:
    interval = max(30, settings.reminder_sweep_interval_seconds)
    while True:
        try:
            await run_reminder_sweep()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - never let the loop die on a transient error
            logger.exception("Reminder sweep failed")
        await asyncio.sleep(interval)
