"""Public share pages for events and training series (no auth required)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import Viewer, ViewerChild, viewer_can_see_targets
from app.models import AgeGroup, Event, EventTarget, NotificationAudience, Parent, Student, TrainingGroup
from app.schemas import PublicEventShare, PublicTrainingShare
from app.security import decode_any_token

router = APIRouter(prefix="/public", tags=["public"])


def _age_label(age_group: AgeGroup | None) -> str | None:
    if age_group is None:
        return None
    if age_group == AgeGroup.Over21:
        return "Over 21"
    return age_group.value


def _audience_labels(targets: list[EventTarget]) -> list[str]:
    labels: list[str] = []
    for target in targets:
        if target.audience == NotificationAudience.parent:
            parts = ["Rodiče"]
            age = _age_label(target.age_group)
            if age:
                parts.append(age)
            if target.branch is not None:
                parts.append(target.branch.name)
            elif target.branch_id is None and target.age_group is None:
                parts.append("všichni")
            labels.append(" · ".join(parts))
        elif target.audience == NotificationAudience.trainer:
            parts = ["Trenéři"]
            if target.branch is not None:
                parts.append(target.branch.name)
            labels.append(" · ".join(parts))
    seen: set[str] = set()
    unique: list[str] = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            unique.append(label)
    return unique


async def _optional_parent_intended(
    db: AsyncSession,
    event: Event,
    authorization: str | None,
) -> bool | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        return None
    try:
        kind, subject_id = decode_any_token(raw)
    except HTTPException:
        return None
    except Exception:
        return None
    if kind != "parent":
        return None
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
    viewer = Viewer(kind="parent", parent_id=subject_id, children=children)
    return viewer_can_see_targets(viewer, event.targets)


@router.get("/events/{token}", response_model=PublicEventShare)
async def public_event_share(
    token: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> PublicEventShare:
    result = await db.execute(
        select(Event)
        .where(Event.share_token == token)
        .options(selectinload(Event.targets).selectinload(EventTarget.branch)),
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Odkaz na akci neexistuje nebo už není platný.")
    return PublicEventShare(
        title=event.title,
        description=event.description or "",
        event_type=event.event_type,
        location=event.location or "",
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        share_token=event.share_token or token,
        audience_labels=_audience_labels(list(event.targets)),
        intended_for_you=await _optional_parent_intended(db, event, authorization),
    )


@router.get("/trainings/{token}", response_model=PublicTrainingShare)
async def public_training_share(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicTrainingShare:
    result = await db.execute(
        select(TrainingGroup)
        .where(TrainingGroup.share_token == token)
        .options(selectinload(TrainingGroup.branch)),
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Odkaz na trénink neexistuje nebo už není platný.")
    return PublicTrainingShare(
        name=group.name,
        branch_name=group.branch.name if group.branch else "",
        start_time=group.start_time,
        end_time=group.end_time,
        weekdays=group.weekdays,
        active_from=group.active_from,
        active_until=group.active_until,
        share_token=group.share_token or token,
    )
