"""Shared request identity and target-visibility helpers.

A `Viewer` represents the authenticated actor (trainer or parent) together with
the data needed to evaluate targeted visibility (a trainer's branches, a
parent's children). Both notifications and events use the same targeting model
`(audience, branch_id, age_group)`, so `viewer_can_see_targets` works for any
object exposing those attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AgeGroup, NotificationAudience, Parent, Student, Trainer
from app.security import decode_any_token


@dataclass
class Viewer:
    kind: str  # "trainer" | "parent"
    trainer_id: int | None = None
    parent_id: int | None = None
    branch_ids: set[int] = field(default_factory=set)
    # For parents: one (branch_ids, age_group) tuple per child.
    children: list[tuple[set[int], AgeGroup]] = field(default_factory=list)


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
    children: list[tuple[set[int], AgeGroup]] = []
    if parent is not None:
        children = [({b.id for b in child.branches}, child.age_group) for child in parent.children]
    return Viewer(kind="parent", parent_id=subject_id, children=children)


def _parent_matches_target(viewer: Viewer, target: _Target) -> bool:
    for branch_ids, age_group in viewer.children:
        if target.branch_id is not None and target.branch_id not in branch_ids:
            continue
        if target.age_group is not None and target.age_group != age_group:
            continue
        return True
    return False


def viewer_can_see_targets(viewer: Viewer, targets: list[_Target]) -> bool:
    """True if the viewer matches at least one of the targets."""
    if viewer.kind == "trainer":
        for target in targets:
            if target.audience != NotificationAudience.trainer:
                continue
            if target.branch_id is None or target.branch_id in viewer.branch_ids:
                return True
        return False

    for target in targets:
        if target.audience != NotificationAudience.parent:
            continue
        if _parent_matches_target(viewer, target):
            return True
    return False
