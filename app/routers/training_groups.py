from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Student, TrainingGroup, TrainingSession
from app.schemas import (
    BranchRead,
    StudentBrief,
    TrainingGroupCreate,
    TrainingGroupDetailRead,
    TrainingGroupPatch,
    TrainingGroupRead,
    TrainingGroupSessionCreate,
    TrainingGroupStudentsReplace,
    TrainingSessionRead,
)
from app.routers.training_sessions import _session_to_read, create_session_for_group

router = APIRouter(prefix="/training-groups", tags=["training-groups"])


def _group_load_options():
    return selectinload(TrainingGroup.branch), selectinload(TrainingGroup.students)


def _group_to_read(group: TrainingGroup) -> TrainingGroupRead:
    return TrainingGroupRead(
        id=group.id,
        branch_id=group.branch_id,
        name=group.name,
        start_time=group.start_time,
        end_time=group.end_time,
        weekdays=group.weekdays,
        created_at=group.created_at,
        updated_at=group.updated_at,
        branch=BranchRead.model_validate(group.branch, from_attributes=True),
    )


def _group_to_detail(group: TrainingGroup) -> TrainingGroupDetailRead:
    students_sorted = sorted(group.students, key=lambda s: (s.last_name, s.first_name, s.id))
    return TrainingGroupDetailRead(
        **_group_to_read(group).model_dump(),
        students=[StudentBrief.model_validate(s, from_attributes=True) for s in students_sorted],
    )


async def _get_branch_or_404(db: AsyncSession, branch_id: int) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch id not found: {branch_id}")
    return branch


async def _get_group_or_404(db: AsyncSession, group_id: int) -> TrainingGroup:
    result = await db.execute(
        select(TrainingGroup).where(TrainingGroup.id == group_id).options(*_group_load_options()),
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Training group not found.")
    return group


def _validate_slot_times(start_time, end_time) -> None:
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time.")


async def _get_students_for_group(
    db: AsyncSession,
    group: TrainingGroup,
    student_ids: list[int],
) -> list[Student]:
    if not student_ids:
        return []

    result = await db.execute(
        select(Student).where(Student.id.in_(student_ids)).options(selectinload(Student.branches)),
    )
    students = result.scalars().unique().all()
    found_ids = {s.id for s in students}
    missing = [sid for sid in student_ids if sid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Student id not found: {missing[0]}")

    for student in students:
        branch_ids = {b.id for b in student.branches}
        if group.branch_id not in branch_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Student {student.id} is not assigned to the group branch.",
            )

    return sorted(students, key=lambda s: student_ids.index(s.id))


@router.get("", response_model=list[TrainingGroupDetailRead])
async def list_training_groups(
    db: AsyncSession = Depends(get_db),
    branch_id: int | None = Query(default=None, ge=1),
) -> list[TrainingGroupDetailRead]:
    stmt = (
        select(TrainingGroup)
        .options(*_group_load_options())
        .order_by(TrainingGroup.branch_id, TrainingGroup.start_time, TrainingGroup.id)
    )
    if branch_id is not None:
        stmt = stmt.where(TrainingGroup.branch_id == branch_id)

    result = await db.execute(stmt)
    groups = result.scalars().unique().all()
    return [_group_to_detail(g) for g in groups]


@router.post("", response_model=TrainingGroupRead, status_code=status.HTTP_201_CREATED)
async def create_training_group(
    payload: TrainingGroupCreate,
    db: AsyncSession = Depends(get_db),
) -> TrainingGroupRead:
    await _get_branch_or_404(db, payload.branch_id)
    _validate_slot_times(payload.start_time, payload.end_time)

    group = TrainingGroup(
        branch_id=payload.branch_id,
        name=payload.name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        weekdays=payload.weekdays,
    )
    db.add(group)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "uq_training_group_branch_slot" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Training group with this branch, name, and time slot already exists.",
            ) from exc
        raise

    return _group_to_read(await _get_group_or_404(db, group.id))


@router.get("/{group_id}", response_model=TrainingGroupDetailRead)
async def get_training_group(group_id: int, db: AsyncSession = Depends(get_db)) -> TrainingGroupDetailRead:
    group = await _get_group_or_404(db, group_id)
    return _group_to_detail(group)


@router.post("/{group_id}/sessions", response_model=TrainingSessionRead)
async def create_training_group_session(
    group_id: int,
    payload: TrainingGroupSessionCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionRead:
    session, created = await create_session_for_group(
        db,
        training_group_id=group_id,
        session_date=payload.session_date,
        trainer_id=payload.trainer_id,
        notes=payload.notes,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _session_to_read(session)


@router.patch("/{group_id}", response_model=TrainingGroupRead)
async def patch_training_group(
    group_id: int,
    payload: TrainingGroupPatch,
    db: AsyncSession = Depends(get_db),
) -> TrainingGroupRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    group = await _get_group_or_404(db, group_id)

    if "branch_id" in data:
        await _get_branch_or_404(db, data["branch_id"])

    start_time = data.get("start_time", group.start_time)
    end_time = data.get("end_time", group.end_time)
    _validate_slot_times(start_time, end_time)

    for key, value in data.items():
        setattr(group, key, value)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "uq_training_group_branch_slot" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Training group with this branch, name, and time slot already exists.",
            ) from exc
        raise

    return _group_to_read(await _get_group_or_404(db, group_id))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_group(group_id: int, db: AsyncSession = Depends(get_db)) -> None:
    group = await db.get(TrainingGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Training group not found.")

    n_sessions = await db.scalar(
        select(func.count()).select_from(TrainingSession).where(TrainingSession.training_group_id == group_id),
    )
    if (n_sessions or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="Training group has training sessions. Delete them first.",
        )

    await db.delete(group)
    await db.commit()


@router.put("/{group_id}/students", response_model=TrainingGroupDetailRead)
async def replace_training_group_students(
    group_id: int,
    payload: TrainingGroupStudentsReplace,
    db: AsyncSession = Depends(get_db),
) -> TrainingGroupDetailRead:
    group = await _get_group_or_404(db, group_id)
    students = await _get_students_for_group(db, group, payload.student_ids)
    group.students.clear()
    group.students.extend(students)
    await db.commit()
    return _group_to_detail(await _get_group_or_404(db, group_id))
