from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AttendanceRecord, Branch, Student, Trainer, TrainingSession
from app.schemas import (
    AttendanceRecordCreate,
    AttendanceRecordPatch,
    AttendanceRecordRead,
    AttendanceRecordWithSessionRead,
    BranchRead,
    TrainingSessionCreate,
    TrainingSessionDetailRead,
    TrainingSessionPatch,
    TrainingSessionRead,
    TrainerBrief,
    StudentBrief,
)

router = APIRouter(prefix="/training-sessions", tags=["training-sessions"])


def _session_load_options():
    return (
        selectinload(TrainingSession.branch),
        selectinload(TrainingSession.trainer),
        selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student),
        selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.recorded_by),
    )


def _attendance_to_read(record: AttendanceRecord) -> AttendanceRecordRead:
    return AttendanceRecordRead(
        id=record.id,
        session_id=record.session_id,
        student_id=record.student_id,
        status=record.status,
        recorded_by_id=record.recorded_by_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        student=StudentBrief.model_validate(record.student, from_attributes=True),
        recorded_by=(
            TrainerBrief.model_validate(record.recorded_by, from_attributes=True)
            if record.recorded_by is not None
            else None
        ),
    )


def attendance_with_session_to_read(record: AttendanceRecord) -> AttendanceRecordWithSessionRead:
    return AttendanceRecordWithSessionRead(
        **_attendance_to_read(record).model_dump(),
        session=_session_to_read(record.session),
    )


def _session_to_read(session: TrainingSession) -> TrainingSessionRead:
    return TrainingSessionRead(
        id=session.id,
        branch_id=session.branch_id,
        trainer_id=session.trainer_id,
        starts_at=session.starts_at,
        age_group=session.age_group,
        notes=session.notes,
        created_at=session.created_at,
        updated_at=session.updated_at,
        branch=BranchRead.model_validate(session.branch, from_attributes=True),
        trainer=(
            TrainerBrief.model_validate(session.trainer, from_attributes=True)
            if session.trainer is not None
            else None
        ),
    )


def _session_to_detail(session: TrainingSession) -> TrainingSessionDetailRead:
    records_sorted = sorted(session.attendance_records, key=lambda r: r.student_id)
    return TrainingSessionDetailRead(
        **_session_to_read(session).model_dump(),
        attendance_records=[_attendance_to_read(r) for r in records_sorted],
    )


async def _get_branch_or_404(db: AsyncSession, branch_id: int) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch id not found: {branch_id}")
    return branch


async def _get_trainer_or_404(db: AsyncSession, trainer_id: int) -> Trainer:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail=f"Trainer id not found: {trainer_id}")
    return trainer


async def _get_session_or_404(db: AsyncSession, session_id: int) -> TrainingSession:
    result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.id == session_id)
        .options(*_session_load_options()),
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Training session not found.")
    return session


async def _get_student_with_branches_or_404(db: AsyncSession, student_id: int) -> Student:
    result = await db.execute(
        select(Student).where(Student.id == student_id).options(selectinload(Student.branches)),
    )
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail=f"Student id not found: {student_id}")
    return student


def _validate_student_for_session(student: Student, session: TrainingSession) -> None:
    branch_ids = {b.id for b in student.branches}
    if session.branch_id not in branch_ids:
        raise HTTPException(
            status_code=400,
            detail="Student is not assigned to the session branch.",
        )
    if session.age_group is not None and student.age_group != session.age_group:
        raise HTTPException(
            status_code=400,
            detail=f"Student age group {student.age_group.value} does not match session {session.age_group.value}.",
        )


@router.get("", response_model=list[TrainingSessionRead])
async def list_training_sessions(
    db: AsyncSession = Depends(get_db),
    branch_id: int | None = Query(default=None, ge=1),
    trainer_id: int | None = Query(default=None, ge=1),
) -> list[TrainingSessionRead]:
    stmt = (
        select(TrainingSession)
        .options(
            selectinload(TrainingSession.branch),
            selectinload(TrainingSession.trainer),
        )
        .order_by(TrainingSession.starts_at.desc(), TrainingSession.id.desc())
    )
    if branch_id is not None:
        stmt = stmt.where(TrainingSession.branch_id == branch_id)
    if trainer_id is not None:
        stmt = stmt.where(TrainingSession.trainer_id == trainer_id)

    result = await db.execute(stmt)
    sessions = result.scalars().unique().all()
    return [_session_to_read(s) for s in sessions]


@router.post("", response_model=TrainingSessionRead, status_code=status.HTTP_201_CREATED)
async def create_training_session(
    payload: TrainingSessionCreate,
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionRead:
    await _get_branch_or_404(db, payload.branch_id)
    if payload.trainer_id is not None:
        await _get_trainer_or_404(db, payload.trainer_id)

    session = TrainingSession(
        branch_id=payload.branch_id,
        trainer_id=payload.trainer_id,
        starts_at=payload.starts_at,
        age_group=payload.age_group,
        notes=payload.notes,
    )
    db.add(session)
    await db.commit()

    return _session_to_read(await _get_session_or_404(db, session.id))


@router.get("/{session_id}", response_model=TrainingSessionDetailRead)
async def get_training_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionDetailRead:
    session = await _get_session_or_404(db, session_id)
    return _session_to_detail(session)


@router.patch("/{session_id}", response_model=TrainingSessionRead)
async def patch_training_session(
    session_id: int,
    payload: TrainingSessionPatch,
    db: AsyncSession = Depends(get_db),
) -> TrainingSessionRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    session = await _get_session_or_404(db, session_id)

    if "branch_id" in data:
        await _get_branch_or_404(db, data["branch_id"])
    if "trainer_id" in data and data["trainer_id"] is not None:
        await _get_trainer_or_404(db, data["trainer_id"])

    for key, value in data.items():
        setattr(session, key, value)

    await db.commit()
    return _session_to_read(await _get_session_or_404(db, session_id))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_session(session_id: int, db: AsyncSession = Depends(get_db)) -> None:
    session = await db.get(TrainingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Training session not found.")
    await db.delete(session)
    await db.commit()


@router.get("/{session_id}/attendance", response_model=list[AttendanceRecordRead])
async def list_session_attendance(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceRecordRead]:
    session = await _get_session_or_404(db, session_id)
    records_sorted = sorted(session.attendance_records, key=lambda r: r.student_id)
    return [_attendance_to_read(r) for r in records_sorted]


@router.post(
    "/{session_id}/attendance",
    response_model=AttendanceRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attendance_record(
    session_id: int,
    payload: AttendanceRecordCreate,
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecordRead:
    session = await _get_session_or_404(db, session_id)
    student = await _get_student_with_branches_or_404(db, payload.student_id)
    _validate_student_for_session(student, session)

    if payload.recorded_by_id is not None:
        await _get_trainer_or_404(db, payload.recorded_by_id)

    existing = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == payload.student_id,
        ),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Attendance for this student in this session already exists. Use PATCH to update.",
        )

    record = AttendanceRecord(
        session_id=session_id,
        student_id=payload.student_id,
        status=payload.status,
        recorded_by_id=payload.recorded_by_id,
    )
    db.add(record)
    await db.commit()

    result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.id == record.id)
        .options(
            selectinload(AttendanceRecord.student),
            selectinload(AttendanceRecord.recorded_by),
        ),
    )
    loaded = result.scalar_one()
    return _attendance_to_read(loaded)


@router.get("/{session_id}/attendance/{attendance_id}", response_model=AttendanceRecordRead)
async def get_attendance_record(
    session_id: int,
    attendance_id: int,
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecordRead:
    record = await _get_attendance_in_session_or_404(db, session_id, attendance_id)
    return _attendance_to_read(record)


async def _get_attendance_in_session_or_404(
    db: AsyncSession,
    session_id: int,
    attendance_id: int,
) -> AttendanceRecord:
    result = await db.execute(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.id == attendance_id,
            AttendanceRecord.session_id == session_id,
        )
        .options(
            selectinload(AttendanceRecord.student),
            selectinload(AttendanceRecord.recorded_by),
        ),
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    return record


@router.patch("/{session_id}/attendance/{attendance_id}", response_model=AttendanceRecordRead)
async def patch_attendance_record(
    session_id: int,
    attendance_id: int,
    payload: AttendanceRecordPatch,
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecordRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    record = await _get_attendance_in_session_or_404(db, session_id, attendance_id)

    if "recorded_by_id" in data and data["recorded_by_id"] is not None:
        await _get_trainer_or_404(db, data["recorded_by_id"])

    for key, value in data.items():
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record, attribute_names=["student", "recorded_by"])
    return _attendance_to_read(record)


@router.delete("/{session_id}/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_record(
    session_id: int,
    attendance_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    record = await _get_attendance_in_session_or_404(db, session_id, attendance_id)
    await db.delete(record)
    await db.commit()
