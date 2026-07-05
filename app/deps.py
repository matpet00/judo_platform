"""Shared request identity and target-visibility helpers.

A `Viewer` represents the authenticated actor (trainer or parent) together with
the data needed to evaluate targeted visibility (a trainer's branches, a
parent's children). Both notifications and events use the same targeting model
`(audience, branch_id, age_group)`, so `viewer_can_see_targets` works for any
object exposing those attributes. Notification targets may additionally carry a
direct `parent_id` / `trainer_id` for personal (single-recipient) delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AgeGroup, NotificationAudience, Parent, Student, Trainer
from app.security import decode_any_token


@dataclass
class ViewerChild:
    id: int
    name: str
    branch_ids: set[int]
    age_group: AgeGroup


@dataclass
class Viewer:
    kind: str  # "trainer" | "parent"
    trainer_id: int | None = None
    parent_id: int | None = None
    branch_ids: set[int] = field(default_factory=set)
    children: list[ViewerChild] = field(default_factory=list)


class _Target(Protocol):
    audience: NotificationAudience
    branch_id: int | None
    age_group: AgeGroup | None


async def get_viewer(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Viewer:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token.")
    kind, subject_id = decode_any_token(authorization.removeprefix("Bearer ").strip())
    if kind == "trainer":
        trainer = await db.get(Trainer, subject_id, options=[selectinload(Trainer.branches)])
        branch_ids = {branch.id for branch in trainer.branches} if trainer is not None else set()
        return Viewer(kind="trainer", trainer_id=subject_id, branch_ids=branch_ids)
    parent = await db.get(
        Parent,
        subject_id,
        options=[selectinload(Parent.children).selectinload(Student.branches)],
    )
    children: list[ViewerChild] = []
    if parent is not None:
        children = [
            ViewerChild(
                id=child.id,
                name=f"{child.first_name} {child.last_name}",
                branch_ids={b.id for b in child.branches},
                age_group=child.age_group,
            )
            for child in parent.children
        ]
    return Viewer(kind="parent", parent_id=subject_id, children=children)


def _child_matches_target(child: ViewerChild, target: _Target) -> bool:
    if target.branch_id is not None and target.branch_id not in child.branch_ids:
        return False
    if target.age_group is not None and target.age_group != child.age_group:
        return False
    return True


def _parent_matches_target(viewer: Viewer, target: _Target) -> bool:
    return any(_child_matches_target(child, target) for child in viewer.children)


def viewer_can_see_targets(viewer: Viewer, targets: list[_Target]) -> bool:
    """True if the viewer matches at least one of the targets (group or personal)."""
    if viewer.kind == "trainer":
        for target in targets:
            if getattr(target, "trainer_id", None) == viewer.trainer_id and viewer.trainer_id is not None:
                return True
            if target.audience != NotificationAudience.trainer:
                continue
            if getattr(target, "parent_id", None) is not None or getattr(target, "trainer_id", None) is not None:
                continue  # personal target for someone else
            if target.branch_id is None or target.branch_id in viewer.branch_ids:
                return True
        return False

    for target in targets:
        if getattr(target, "parent_id", None) == viewer.parent_id and viewer.parent_id is not None:
            return True
        if target.audience != NotificationAudience.parent:
            continue
        if getattr(target, "parent_id", None) is not None or getattr(target, "trainer_id", None) is not None:
            continue  # personal target for someone else
        if _parent_matches_target(viewer, target):
            return True
    return False


def matched_children(viewer: Viewer, targets: list[_Target]) -> list[ViewerChild]:
    """The parent viewer's children that are addressed by the event's parent targets."""
    if viewer.kind != "parent":
        return []
    matched: list[ViewerChild] = []
    for child in viewer.children:
        for target in targets:
            if target.audience != NotificationAudience.parent:
                continue
            if getattr(target, "parent_id", None) is not None or getattr(target, "trainer_id", None) is not None:
                continue
            if _child_matches_target(child, target):
                matched.append(child)
                break
    return matched


async def participants_matching_targets(
    db: AsyncSession,
    targets: list[_Target],
) -> tuple[list[Parent], list[Trainer]]:
    """Expand group targets into concrete parents and trainers reached by them.

    Personal `parent_id`/`trainer_id` targets are also honored. Returned parents
    have `children` (with branches) loaded so callers can reason per-child.
    """
    parent_audience = any(
        t.audience == NotificationAudience.parent
        and getattr(t, "parent_id", None) is None
        and getattr(t, "trainer_id", None) is None
        for t in targets
    )
    trainer_audience = any(
        t.audience == NotificationAudience.trainer
        and getattr(t, "parent_id", None) is None
        and getattr(t, "trainer_id", None) is None
        for t in targets
    )
    direct_parent_ids = {pid for t in targets if (pid := getattr(t, "parent_id", None)) is not None}
    direct_trainer_ids = {tid for t in targets if (tid := getattr(t, "trainer_id", None)) is not None}

    parents: dict[int, Parent] = {}
    trainers: dict[int, Trainer] = {}

    if parent_audience or direct_parent_ids:
        result = await db.execute(
            select(Parent).options(selectinload(Parent.children).selectinload(Student.branches)),
        )
        for parent in result.scalars().unique().all():
            if parent.id in direct_parent_ids:
                parents[parent.id] = parent
                continue
            if not parent_audience:
                continue
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
            if viewer_can_see_targets(viewer, targets):
                parents[parent.id] = parent

    if trainer_audience or direct_trainer_ids:
        result = await db.execute(select(Trainer).options(selectinload(Trainer.branches)))
        for trainer in result.scalars().unique().all():
            if trainer.id in direct_trainer_ids:
                trainers[trainer.id] = trainer
                continue
            if not trainer_audience:
                continue
            viewer = Viewer(kind="trainer", trainer_id=trainer.id, branch_ids={b.id for b in trainer.branches})
            if viewer_can_see_targets(viewer, targets):
                trainers[trainer.id] = trainer

    return list(parents.values()), list(trainers.values())
