from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.student_delete import unlink_branch_students
from app.models import (
    AttendanceRecord,
    Branch,
    EventTarget,
    Notification,
    NotificationTarget,
    TrainerSessionAttendance,
    TrainingGroup,
    TrainingOccurrenceComment,
    TrainingSession,
    student_training_groups,
    trainer_branches,
)
from app.schemas import (
    BranchCreate,
    BranchDetailRead,
    BranchPatch,
    StudentBrief,
    TrainerBrief,
)

router = APIRouter(prefix="/branches", tags=["branches"])


def _branch_to_detail(branch: Branch) -> BranchDetailRead:
    students_sorted = sorted(branch.students, key=lambda s: s.id)
    trainers_sorted = sorted(branch.trainers, key=lambda t: t.id)
    return BranchDetailRead(
        id=branch.id,
        name=branch.name,
        address=branch.address,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
        students=[StudentBrief.model_validate(s, from_attributes=True) for s in students_sorted],
        trainers=[TrainerBrief.model_validate(t, from_attributes=True) for t in trainers_sorted],
    )


def _branch_load_options():
    return selectinload(Branch.students), selectinload(Branch.trainers)


async def _cleanup_branch_references(db: AsyncSession, branch_id: int) -> None:
    """Detach or remove rows tied to this branch (SQLite may not enforce ON DELETE)."""
    group_ids = (
        await db.scalars(select(TrainingGroup.id).where(TrainingGroup.branch_id == branch_id))
    ).all()

    session_filters = [TrainingSession.branch_id == branch_id]
    if group_ids:
        session_filters.append(TrainingSession.training_group_id.in_(group_ids))
    session_ids = (
        await db.scalars(select(TrainingSession.id).where(or_(*session_filters)))
    ).all()

    if session_ids:
        await db.execute(
            delete(TrainerSessionAttendance).where(TrainerSessionAttendance.session_id.in_(session_ids)),
        )
        await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(session_ids)))
        await db.execute(delete(TrainingSession).where(TrainingSession.id.in_(session_ids)))

    if group_ids:
        await db.execute(
            delete(TrainingOccurrenceComment).where(TrainingOccurrenceComment.training_group_id.in_(group_ids)),
        )
        await db.execute(delete(student_training_groups).where(student_training_groups.c.group_id.in_(group_ids)))
        await db.execute(
            update(Notification)
            .where(Notification.training_group_id.in_(group_ids))
            .values(training_group_id=None),
        )
        await db.execute(delete(TrainingGroup).where(TrainingGroup.id.in_(group_ids)))

    await unlink_branch_students(db, branch_id)
    await db.execute(delete(trainer_branches).where(trainer_branches.c.branch_id == branch_id))
    await db.execute(delete(NotificationTarget).where(NotificationTarget.branch_id == branch_id))
    await db.execute(delete(EventTarget).where(EventTarget.branch_id == branch_id))


@router.get("", response_model=list[BranchDetailRead])
async def list_branches(db: AsyncSession = Depends(get_db)) -> list[BranchDetailRead]:
    result = await db.execute(
        select(Branch).options(*_branch_load_options()).order_by(Branch.id),
    )
    branches = result.scalars().unique().all()
    return [_branch_to_detail(b) for b in branches]


@router.post("", response_model=BranchDetailRead, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate,
    db: AsyncSession = Depends(get_db),
) -> BranchDetailRead:
    existing = await db.execute(select(Branch).where(Branch.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Branch with this name already exists.")

    branch = Branch(name=payload.name, address=payload.address)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    result = await db.execute(
        select(Branch).where(Branch.id == branch.id).options(*_branch_load_options()),
    )
    loaded = result.scalar_one()
    return _branch_to_detail(loaded)


@router.get("/{branch_id}", response_model=BranchDetailRead)
async def get_branch(branch_id: int, db: AsyncSession = Depends(get_db)) -> BranchDetailRead:
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id).options(*_branch_load_options()),
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")
    return _branch_to_detail(branch)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: int, db: AsyncSession = Depends(get_db)) -> None:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")

    await _cleanup_branch_references(db, branch_id)
    await db.delete(branch)
    await db.commit()


@router.patch("/{branch_id}", response_model=BranchDetailRead)
async def patch_branch(
    branch_id: int,
    payload: BranchPatch,
    db: AsyncSession = Depends(get_db),
) -> BranchDetailRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")

    if "name" in data and data["name"] != branch.name:
        existing = await db.execute(
            select(Branch).where(Branch.name == data["name"], Branch.id != branch_id),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Branch with this name already exists.")

    for key, value in data.items():
        setattr(branch, key, value)

    await db.commit()
    await db.refresh(branch)

    result = await db.execute(
        select(Branch).where(Branch.id == branch_id).options(*_branch_load_options()),
    )
    loaded = result.scalar_one()
    return _branch_to_detail(loaded)
