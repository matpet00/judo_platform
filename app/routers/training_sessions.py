from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AttendanceRecord, Branch, Student, Trainer, TrainingGroup, TrainingSession
from app.schemas import (
    AttendanceBulkReplace,
    AttendanceRecordCreate,
    AttendanceRecordPatch,
    AttendanceRecordRead,
    AttendanceRecordWithSessionRead,
    AttendanceSummary,
    BranchRead,
    SessionStudentWithAttendance,
    TrainingGroupBrief,
    TrainingSessionCreate,
    TrainingSessionDetailRead,
    TrainingSessionPatch,
    TrainingSessionRead,
    TrainerBrief,
    StudentBrief,
)
from app.security import require_trainer_token

router = APIRouter(prefix="/training-sessions", tags=["training-sessions"])


def _session_load_options():
    return (
        selectinload(TrainingSession.branch),
        selectinload(TrainingSession.training_group),
        selectinload(TrainingSession.trainer),
        selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student),
        selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.recorded_by),
    )


def _starts_at_from_group(session_date: date, group: TrainingGroup) -> datetime:
    return datetime.combine(session_date, group.start_time, tzinfo=timezone.utc)


def _session_date_from_starts_at(starts_at: datetime) -> date:
    return starts_at.date()


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


def _attendance_to_summary(record: AttendanceRecord) -> AttendanceSummary:
    return AttendanceSummary(
        id=record.id,
        status=record.status,
        recorded_by_id=record.recorded_by_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def attendance_with_session_to_read(record: AttendanceRecord) -> AttendanceRecordWithSessionRead:
    return AttendanceRecordWithSessionRead(
        **_attendance_to_read(record).model_dump(),
        session=_session_to_read(record.session),
    )


def _session_to_read(session: TrainingSession) -> TrainingSessionRead:
    if session.training_group is None:
        raise HTTPException(status_code=500, detail="Training group not loaded for session.")
    return TrainingSessionRead(
        id=session.id,
        branch_id=session.branch_id,
        training_group_id=session.training_group_id,
        trainer_id=session.trainer_id,
        starts_at=session.starts_at,
        notes=session.notes,
        created_at=session.created_at,
        updated_at=session.updated_at,
        branch=BranchRead.model_validate(session.branch, from_attributes=True),
        training_group=TrainingGroupBrief.model_validate(session.training_group, from_attributes=True),
        trainer=(
            TrainerBrief.model_validate(session.trainer, from_attributes=True)
            if session.trainer is not None
            else None
        ),
    )


def _session_students_with_attendance(session: TrainingSession) -> list[SessionStudentWithAttendance]:
    if session.training_group is None:
        raise HTTPException(status_code=500, detail="Training group not loaded for session.")
    by_student_id = {r.student_id: r for r in session.attendance_records}
    students_sorted = sorted(
        session.training_group.students,
        key=lambda s: (s.last_name, s.first_name, s.id),
    )
    return [
        SessionStudentWithAttendance(
            id=student.id,
            first_name=student.first_name,
            last_name=student.last_name,
            age_group=student.age_group,
            attendance=(
                _attendance_to_summary(by_student_id[student.id])
                if student.id in by_student_id
                else None
            ),
        )
        for student in students_sorted
    ]


def _session_to_detail(session: TrainingSession) -> TrainingSessionDetailRead:
    records_sorted = sorted(session.attendance_records, key=lambda r: r.student_id)
    return TrainingSessionDetailRead(
        **_session_to_read(session).model_dump(),
        students=_session_students_with_attendance(session),
        attendance_records=[_attendance_to_read(r) for r in records_sorted],
    )


async def _get_trainer_or_404(db: AsyncSession, trainer_id: int) -> Trainer:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail=f"Trainer id not found: {trainer_id}")
    return trainer


async def get_training_group_or_404(db: AsyncSession, group_id: int) -> TrainingGroup:
    result = await db.execute(
        select(TrainingGroup)
        .where(TrainingGroup.id == group_id)
        .options(selectinload(TrainingGroup.students)),
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"Training group id not found: {group_id}")
    return group


async def _get_session_or_404(db: AsyncSession, session_id: int) -> TrainingSession:
    result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.id == session_id)
        .options(
            *_session_load_options(),
            selectinload(TrainingSession.training_group).selectinload(TrainingGroup.students),
        ),
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Training session not found.")
    return session


async def _get_existing_session_for_group_date(
    db: AsyncSession,
    group_id: int,
    session_date: date,
) -> TrainingSession | None:
    group = await get_training_group_or_404(db, group_id)
    starts_at = _starts_at_from_group(session_date, group)
    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id == group_id,
            TrainingSession.starts_at == starts_at,
        )
        .options(*_session_load_options(), selectinload(TrainingSession.training_group).selectinload(TrainingGroup.students)),
    )
    return result.scalar_one_or_none()


async def create_session_for_group(
    db: AsyncSession,
    *,
    training_group_id: int,
    session_date: date,
    trainer_id: int | None = None,
    notes: str | None = None,
) -> tuple[TrainingSession, bool]:
    """Create session; returns (session, created). If duplicate, returns existing with created=False."""
    existing = await _get_existing_session_for_group_date(db, training_group_id, session_date)
    if existing is not None:
        return existing, False

    group = await get_training_group_or_404(db, training_group_id)
    if trainer_id is not None:
        await _get_trainer_or_404(db, trainer_id)

    session = TrainingSession(
        branch_id=group.branch_id,
        training_group_id=training_group_id,
        trainer_id=trainer_id,
        starts_at=_starts_at_from_group(session_date, group),
        notes=notes,
    )
    db.add(session)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "uq_training_session_group_starts_at" in str(exc).lower() or "unique" in str(exc).lower():
            existing = await _get_existing_session_for_group_date(db, training_group_id, session_date)
            if existing is not None:
                return existing, False
            raise HTTPException(
                status_code=409,
                detail="Training session for this group and session_date already exists.",
            ) from exc
        raise

    loaded = await _get_session_or_404(db, session.id)
    return loaded, True


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
    if session.training_group is None:
        raise HTTPException(status_code=500, detail="Training group not loaded for session.")
    group_student_ids = {s.id for s in session.training_group.students}
    if student.id not in group_student_ids:
        raise HTTPException(
            status_code=400,
            detail="Student is not a member of the session training group.",
        )


@router.get("", response_model=list[TrainingSessionRead])
async def list_training_sessions(
    db: AsyncSession = Depends(get_db),
    branch_id: int | None = Query(default=None, ge=1),
    trainer_id: int | None = Query(default=None, ge=1),
    training_group_id: int | None = Query(default=None, ge=1),
    session_date: date | None = Query(default=None, description="Filter by session calendar date (UTC, YYYY-MM-DD)"),
) -> list[TrainingSessionRead]:
    stmt = (
        select(TrainingSession)
        .options(
            selectinload(TrainingSession.branch),
            selectinload(TrainingSession.training_group),
            selectinload(TrainingSession.trainer),
        )
        .order_by(TrainingSession.starts_at.desc(), TrainingSession.id.desc())
    )
    if branch_id is not None:
        stmt = stmt.where(TrainingSession.branch_id == branch_id)
    if trainer_id is not None:
        stmt = stmt.where(TrainingSession.trainer_id == trainer_id)
    if training_group_id is not None:
        stmt = stmt.where(TrainingSession.training_group_id == training_group_id)
    if session_date is not None:
        day_start = datetime.combine(session_date, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        stmt = stmt.where(
            TrainingSession.starts_at >= day_start,
            TrainingSession.starts_at < day_end,
        )

    result = await db.execute(stmt)
    sessions = result.scalars().unique().all()
    return [_session_to_read(s) for s in sessions]


@router.post("", response_model=TrainingSessionRead, status_code=status.HTTP_201_CREATED)
async def create_training_session(
    payload: TrainingSessionCreate,
    db: AsyncSession = Depends(get_db),
    _trainer_id: int = Depends(require_trainer_token),
) -> TrainingSessionRead:
    session, created = await create_session_for_group(
        db,
        training_group_id=payload.training_group_id,
        session_date=payload.session_date,
        trainer_id=payload.trainer_id,
        notes=payload.notes,
    )
    if not created:
        raise HTTPException(
            status_code=409,
            detail="Training session for this group and session_date already exists.",
        )
    return _session_to_read(session)


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
    _trainer_id: int = Depends(require_trainer_token),
) -> TrainingSessionRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    session = await _get_session_or_404(db, session_id)

    group_id = data.get("training_group_id", session.training_group_id)
    session_date = data.get("session_date", _session_date_from_starts_at(session.starts_at))

    if "training_group_id" in data:
        await get_training_group_or_404(db, group_id)

    group = await get_training_group_or_404(db, group_id)

    if "trainer_id" in data and data["trainer_id"] is not None:
        await _get_trainer_or_404(db, data["trainer_id"])

    if "training_group_id" in data:
        session.training_group_id = group_id
        session.branch_id = group.branch_id

    if "session_date" in data or "training_group_id" in data:
        session.starts_at = _starts_at_from_group(session_date, group)

    if "trainer_id" in data:
        session.trainer_id = data["trainer_id"]
    if "notes" in data:
        session.notes = data["notes"]

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "uq_training_session_group_starts_at" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Training session for this group and session_date already exists.",
            ) from exc
        raise

    return _session_to_read(await _get_session_or_404(db, session_id))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer_id: int = Depends(require_trainer_token),
) -> None:
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


@router.put("/{session_id}/attendance", response_model=list[AttendanceRecordRead])
async def replace_session_attendance(
    session_id: int,
    payload: AttendanceBulkReplace,
    db: AsyncSession = Depends(get_db),
    _trainer_id: int = Depends(require_trainer_token),
) -> list[AttendanceRecordRead]:
    session = await _get_session_or_404(db, session_id)
    roster_ids = {s.id for s in session.training_group.students}

    for item in payload.records:
        if item.student_id not in roster_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Student {item.student_id} is not in the session training group roster.",
            )
        if item.recorded_by_id is not None:
            await _get_trainer_or_404(db, item.recorded_by_id)

    by_student_id = {r.student_id: r for r in session.attendance_records}
    for item in payload.records:
        existing = by_student_id.get(item.student_id)
        if existing is not None:
            existing.status = item.status
            existing.recorded_by_id = item.recorded_by_id
        else:
            db.add(
                AttendanceRecord(
                    session_id=session_id,
                    student_id=item.student_id,
                    status=item.status,
                    recorded_by_id=item.recorded_by_id,
                ),
            )

    await db.commit()
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
    _trainer_id: int = Depends(require_trainer_token),
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
            detail="Attendance for this student in this session already exists. Use PATCH or PUT bulk.",
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
    _trainer_id: int = Depends(require_trainer_token),
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
    record = await _get_attendance_in_session_or_404(db, session_id, attendance_id)
    return _attendance_to_read(record)


@router.delete("/{session_id}/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_record(
    session_id: int,
    attendance_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer_id: int = Depends(require_trainer_token),
) -> None:
    record = await _get_attendance_in_session_or_404(db, session_id, attendance_id)
    await db.delete(record)
    await db.commit()
