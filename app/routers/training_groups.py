from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import Viewer, get_viewer
from app.models import (
    AttendanceRecord,
    Branch,
    Notification,
    NotificationAudience,
    NotificationTarget,
    Parent,
    Student,
    TrainingGroup,
    TrainingSession,
)
from app.schemas import (
    AttendanceMonthlyReport,
    AttendanceMonthlyReportRow,
    BranchRead,
    StudentBrief,
    TrainingGroupCreate,
    TrainingGroupDetailRead,
    TrainingGroupPatch,
    TrainingGroupRead,
    TrainingGroupSessionCreate,
    TrainingGroupStudentsReplace,
    TrainingOccurrence,
    TrainingSessionRead,
)
from app.routers.training_sessions import _session_to_read, create_session_for_group
from app.security import require_trainer_token

router = APIRouter(prefix="/training-groups", tags=["training-groups"])

ENROLLMENT_NOTICE_DAYS = 30


async def _notify_enrollment(db: AsyncSession, group: TrainingGroup, students: list[Student]) -> None:
    """Personal notification to each enrolled child's parents when added to a group's roster."""
    if not students:
        return
    student_ids = [s.id for s in students]
    result = await db.execute(
        select(Student).where(Student.id.in_(student_ids)).options(selectinload(Student.parents)),
    )
    now = datetime.now(UTC)
    visible_until = now + timedelta(days=ENROLLMENT_NOTICE_DAYS)
    branch_name = group.branch.name if group.branch is not None else ""
    for student in result.scalars().unique().all():
        parents = list(student.parents)
        if not parents:
            continue
        child = f"{student.first_name} {student.last_name}"
        where = f" ({branch_name})" if branch_name else ""
        notification = Notification(
            title="Zařazení do tréninku",
            body=f"Dítě {child} bylo zařazeno do tréninku {group.name}{where}.",
            author_trainer_id=None,
            visible_until=visible_until,
            grace_seconds=0,
            last_activity_at=now,
            targets=[
                NotificationTarget(audience=NotificationAudience.parent, parent_id=parent.id)
                for parent in parents
            ],
        )
        db.add(notification)


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
        active_from=group.active_from,
        active_until=group.active_until,
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


def _occurrence_dates(group: TrainingGroup, from_date: date, to_date: date) -> list[date]:
    if not group.weekdays:
        return []
    lo = from_date
    hi = to_date
    if group.active_from is not None and group.active_from > lo:
        lo = group.active_from
    if group.active_until is not None and group.active_until < hi:
        hi = group.active_until
    dates: list[date] = []
    current = lo
    while current <= hi:
        if current.isoweekday() in group.weekdays:
            dates.append(current)
        current += timedelta(days=1)
    return dates


@router.get("/occurrences", response_model=list[TrainingOccurrence])
async def list_training_occurrences(
    db: AsyncSession = Depends(get_db),
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    viewer: Viewer = Depends(get_viewer),
) -> list[TrainingOccurrence]:
    if to_date < from_date:
        raise HTTPException(status_code=422, detail="'to' must be on or after 'from'.")
    if (to_date - from_date).days > 366:
        raise HTTPException(status_code=422, detail="Range too large (max 366 days).")

    result = await db.execute(select(TrainingGroup).options(*_group_load_options()))
    groups = result.scalars().unique().all()
    if viewer.kind == "parent":
        child_ids = {child.id for child in viewer.children}
        groups = [g for g in groups if child_ids & {s.id for s in g.students}]

    group_ids = [g.id for g in groups]
    session_by_group_date: dict[tuple[int, date], TrainingSession] = {}
    if group_ids:
        day_start = datetime.combine(from_date, datetime.min.time(), tzinfo=UTC)
        day_end = datetime.combine(to_date, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
        sessions_result = await db.execute(
            select(TrainingSession)
            .where(
                TrainingSession.training_group_id.in_(group_ids),
                TrainingSession.starts_at >= day_start,
                TrainingSession.starts_at < day_end,
            )
            .options(selectinload(TrainingSession.attendance_records)),
        )
        for session in sessions_result.scalars().unique().all():
            session_by_group_date[(session.training_group_id, session.starts_at.date())] = session

    occurrences: list[TrainingOccurrence] = []
    for group in groups:
        roster_count = len(group.students)
        for occ_date in _occurrence_dates(group, from_date, to_date):
            session = session_by_group_date.get((group.id, occ_date))
            if session is not None and session.canceled:
                continue
            occurrences.append(
                TrainingOccurrence(
                    group_id=group.id,
                    name=group.name,
                    branch_id=group.branch_id,
                    date=occ_date,
                    start_time=group.start_time,
                    end_time=group.end_time,
                    session_id=session.id if session is not None else None,
                    canceled=bool(session.canceled) if session is not None else False,
                    roster_count=roster_count,
                    marked_count=len(session.attendance_records) if session is not None else 0,
                ),
            )
    occurrences.sort(key=lambda o: (o.date, o.start_time, o.group_id))
    return occurrences


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
        active_from=payload.active_from,
        active_until=payload.active_until,
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

    if payload.student_ids:
        loaded = await _get_group_or_404(db, group.id)
        students = await _get_students_for_group(db, loaded, payload.student_ids)
        loaded.students.extend(students)
        await _notify_enrollment(db, loaded, students)
        await db.commit()

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
    _trainer_id: int = Depends(require_trainer_token),
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
async def delete_training_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer_id: int = Depends(require_trainer_token),
) -> None:
    group = await db.get(TrainingGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Training group not found.")

    # Cascade-delete the whole series: attendance records, then sessions, then the group.
    # (SQLite doesn't enforce ON DELETE CASCADE, so we clear children explicitly.)
    session_ids = (
        await db.scalars(
            select(TrainingSession.id).where(TrainingSession.training_group_id == group_id),
        )
    ).all()
    if session_ids:
        await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(session_ids)))
        await db.execute(delete(TrainingSession).where(TrainingSession.id.in_(session_ids)))

    await db.delete(group)
    await db.commit()


@router.get("/{group_id}/attendance-report", response_model=AttendanceMonthlyReport)
async def training_group_attendance_report(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
    _trainer_id: int = Depends(require_trainer_token),
) -> AttendanceMonthlyReport:
    group = await _get_group_or_404(db, group_id)
    year, mon = (int(part) for part in month.split("-"))
    month_start = datetime(year, mon, 1, tzinfo=UTC)
    month_end = datetime(year + (mon == 12), (mon % 12) + 1, 1, tzinfo=UTC)

    sessions_result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id == group_id,
            TrainingSession.starts_at >= month_start,
            TrainingSession.starts_at < month_end,
            TrainingSession.canceled.is_(False),
        )
        .options(selectinload(TrainingSession.attendance_records)),
    )
    sessions = sessions_result.scalars().unique().all()

    counts: dict[int, dict[str, int]] = {
        s.id: {"present": 0, "absent": 0, "excused": 0} for s in group.students
    }
    for session in sessions:
        for record in session.attendance_records:
            bucket = counts.get(record.student_id)
            if bucket is not None:
                bucket[record.status.value] += 1

    rows = [
        AttendanceMonthlyReportRow(
            student_id=student.id,
            name=f"{student.first_name} {student.last_name}",
            present=counts[student.id]["present"],
            absent=counts[student.id]["absent"],
            excused=counts[student.id]["excused"],
            sessions=len(sessions),
        )
        for student in sorted(group.students, key=lambda s: (s.last_name, s.first_name, s.id))
    ]
    return AttendanceMonthlyReport(group_id=group_id, month=month, sessions=len(sessions), rows=rows)


@router.put("/{group_id}/students", response_model=TrainingGroupDetailRead)
async def replace_training_group_students(
    group_id: int,
    payload: TrainingGroupStudentsReplace,
    db: AsyncSession = Depends(get_db),
) -> TrainingGroupDetailRead:
    group = await _get_group_or_404(db, group_id)
    students = await _get_students_for_group(db, group, payload.student_ids)
    previous_ids = {s.id for s in group.students}
    added = [s for s in students if s.id not in previous_ids]
    group.students.clear()
    group.students.extend(students)
    await _notify_enrollment(db, group, added)
    await db.commit()
    return _group_to_detail(await _get_group_or_404(db, group_id))
