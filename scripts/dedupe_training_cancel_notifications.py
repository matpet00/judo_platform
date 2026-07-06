"""One-off: merge duplicate training-cancel notifications (same body/term)."""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Notification, NotificationAudience, NotificationTarget

DEDUPE_TITLES = ("Zrušený trénink", "Trénink zrušen")


def _group_key(notification: Notification) -> tuple:
    return (
        notification.title,
        notification.body.strip(),
        notification.training_group_id,
        notification.training_date,
        notification.author_trainer_id,
    )


async def dedupe() -> int:
    removed = 0
    async with async_session_maker() as session:
        result = await session.execute(
            select(Notification)
            .where(Notification.title.in_(DEDUPE_TITLES))
            .options(selectinload(Notification.targets))
            .order_by(Notification.id),
        )
        rows = result.scalars().unique().all()
        groups: dict[tuple, list[Notification]] = defaultdict(list)
        for row in rows:
            groups[_group_key(row)].append(row)

        for group in groups.values():
            if len(group) < 2:
                continue
            keep = group[0]
            parent_ids: set[int] = set()
            for row in group:
                for target in row.targets:
                    if target.audience == NotificationAudience.parent and target.parent_id is not None:
                        parent_ids.add(target.parent_id)

            keep.targets = [
                NotificationTarget(
                    audience=NotificationAudience.parent,
                    parent_id=parent_id,
                )
                for parent_id in sorted(parent_ids)
            ]

            for row in group[1:]:
                await session.delete(row)
                removed += 1

        if removed:
            await session.commit()
    return removed


def main() -> None:
    removed = asyncio.run(dedupe())
    print(f"Removed {removed} duplicate training-cancel notification(s).")


if __name__ == "__main__":
    main()
