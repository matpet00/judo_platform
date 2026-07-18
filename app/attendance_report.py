"""Shared attendance report builders (month or arbitrary date range)."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AttendanceRecord, AttendanceStatus, Student, TrainingGroup, TrainingSession
from app.schemas import (
    AttendanceMonthlyReport,
    AttendanceMonthlyReportRow,
    ParentChildAttendanceEntry,
    ParentChildAttendanceReport,
)

MAX_RANGE_DAYS = 450  # ~14 months (full season + buffer)


def month_date_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(part) for part in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


def season_start_year_for_date(d: date) -> int:
    """Judo season Sep–Jun; Jul–Aug belong to the season that just ended."""
    if d.month >= 9:
        return d.year
    return d.year - 1


def season_bounds(start_year: int) -> tuple[date, date]:
    return date(start_year, 9, 1), date(start_year + 1, 6, 30)


def half_bounds(start_year: int, half: int) -> tuple[date, date]:
    if half == 1:
        return date(start_year, 9, 1), date(start_year + 1, 1, 31)
    if half == 2:
        return date(start_year + 1, 2, 1), date(start_year + 1, 6, 30)
    raise ValueError("half must be 1 or 2")


def quarter_bounds(start_year: int, quarter: int) -> tuple[date, date]:
    """School-style quarters within Sep–Jun season."""
    if quarter == 1:
        return date(start_year, 9, 1), date(start_year, 11, 30)
    if quarter == 2:
        return date(start_year, 12, 1), date(start_year + 1, 1, 31)
    if quarter == 3:
        return date(start_year + 1, 2, 1), date(start_year + 1, 4, 30)
    if quarter == 4:
        return date(start_year + 1, 5, 1), date(start_year + 1, 6, 30)
    raise ValueError("quarter must be 1..4")


def month_label_for_range(date_from: date, date_to: date) -> str:
    """YYYY-MM only when the range is exactly one calendar month."""
    if date_from.year != date_to.year or date_from.month != date_to.month:
        return ""
    if date_from.day != 1:
        return ""
    last = calendar.monthrange(date_from.year, date_from.month)[1]
    if date_to.day != last:
        return ""
    return f"{date_from.year}-{date_from.month:02d}"


def validate_date_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range too long (max {MAX_RANGE_DAYS} days).",
        )


def resolve_attendance_range(
    *,
    month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[date, date]:
    """Resolve legacy month=YYYY-MM or date_from+date_to into an inclusive date range."""
    has_dates = date_from is not None or date_to is not None
    if has_dates:
        if date_from is None or date_to is None:
            raise HTTPException(
                status_code=400,
                detail="Provide both date_from and date_to, or use month=YYYY-MM.",
            )
        if month is not None:
            raise HTTPException(
                status_code=400,
                detail="Use either month or date_from/date_to, not both.",
            )
        validate_date_range(date_from, date_to)
        return date_from, date_to

    if month is None:
        raise HTTPException(
            status_code=400,
            detail="Provide month=YYYY-MM or date_from and date_to.",
        )
    try:
        start, end = month_date_bounds(month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid month (expected YYYY-MM).") from exc
    return start, end


def group_active_in_range(group: TrainingGroup, date_from: date, date_to: date) -> bool:
    """Calendar groups only: weekdays set and active window overlaps range."""
    if not group.weekdays:
        return False
    if group.active_from and group.active_from > date_to:
        return False
    if group.active_until and group.active_until < date_from:
        return False
    return True


def group_active_in_month(group: TrainingGroup, month: str) -> bool:
    start, end = month_date_bounds(month)
    return group_active_in_range(group, start, end)


def date_range_datetime_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
    end_day = date_to + timedelta(days=1)
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=UTC)
    return start, end


def month_datetime_bounds(month: str) -> tuple[datetime, datetime]:
    start, end = month_date_bounds(month)
    return date_range_datetime_bounds(start, end)


def build_group_attendance_report(
    group: TrainingGroup,
    sessions: list[TrainingSession],
    date_from: date,
    date_to: date,
) -> AttendanceMonthlyReport:
    roster_ids = {s.id for s in group.students}
    counts: dict[int, dict[str, int]] = {
        s.id: {"present": 0, "absent": 0, "excused": 0} for s in group.students
    }
    guest_counts: dict[int, dict[str, int]] = {}
    guest_students: dict[int, Student] = {}

    for session in sessions:
        for record in session.attendance_records:
            if record.student_id in roster_ids:
                counts[record.student_id][record.status.value] += 1
            else:
                bucket = guest_counts.setdefault(
                    record.student_id,
                    {"present": 0, "absent": 0, "excused": 0},
                )
                bucket[record.status.value] += 1
                if record.student is not None:
                    guest_students[record.student_id] = record.student

    rows = [
        AttendanceMonthlyReportRow(
            student_id=student.id,
            name=f"{student.first_name} {student.last_name}",
            present=counts[student.id]["present"],
            absent=counts[student.id]["absent"],
            excused=counts[student.id]["excused"],
            sessions=len(sessions),
            is_guest=False,
        )
        for student in sorted(group.students, key=lambda s: (s.last_name, s.first_name, s.id))
    ]

    guest_rows = []
    for student_id, bucket in guest_counts.items():
        student = guest_students.get(student_id)
        name = f"{student.first_name} {student.last_name}" if student is not None else f"#{student_id}"
        guest_rows.append(
            AttendanceMonthlyReportRow(
                student_id=student_id,
                name=name,
                present=bucket["present"],
                absent=bucket["absent"],
                excused=bucket["excused"],
                sessions=bucket["present"] + bucket["absent"] + bucket["excused"],
                is_guest=True,
            ),
        )
    guest_rows.sort(key=lambda r: r.name.lower())
    rows.extend(guest_rows)

    return AttendanceMonthlyReport(
        group_id=group.id,
        month=month_label_for_range(date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        sessions=len(sessions),
        group_count=1,
        rows=rows,
    )


def build_branch_attendance_report(
    groups: list[TrainingGroup],
    sessions: list[TrainingSession],
    branch_id: int,
    date_from: date,
    date_to: date,
) -> AttendanceMonthlyReport:
    roster_by_group = {g.id: {s.id for s in g.students} for g in groups}
    roster_students: dict[int, Student] = {}
    for group in groups:
        for student in group.students:
            roster_students[student.id] = student

    counts: dict[int, dict[str, int]] = {
        sid: {"present": 0, "absent": 0, "excused": 0} for sid in roster_students
    }
    session_denominator: dict[int, int] = {sid: 0 for sid in roster_students}
    guest_counts: dict[int, dict[str, int]] = {}
    guest_students: dict[int, Student] = {}

    for session in sessions:
        group_id = session.training_group_id
        roster_ids = roster_by_group.get(group_id, set())
        for sid in roster_ids:
            session_denominator[sid] += 1

        for record in session.attendance_records:
            status_key = record.status.value
            if record.student_id in roster_ids:
                counts[record.student_id][status_key] += 1
            else:
                bucket = guest_counts.setdefault(
                    record.student_id,
                    {"present": 0, "absent": 0, "excused": 0},
                )
                bucket[status_key] += 1
                if record.student is not None:
                    guest_students[record.student_id] = record.student

    rows = [
        AttendanceMonthlyReportRow(
            student_id=student.id,
            name=f"{student.first_name} {student.last_name}",
            present=counts[student.id]["present"],
            absent=counts[student.id]["absent"],
            excused=counts[student.id]["excused"],
            sessions=session_denominator[student.id],
            is_guest=False,
        )
        for student in sorted(roster_students.values(), key=lambda s: (s.last_name, s.first_name, s.id))
    ]

    guest_rows = []
    for student_id, bucket in guest_counts.items():
        student = guest_students.get(student_id)
        name = f"{student.first_name} {student.last_name}" if student is not None else f"#{student_id}"
        guest_rows.append(
            AttendanceMonthlyReportRow(
                student_id=student_id,
                name=name,
                present=bucket["present"],
                absent=bucket["absent"],
                excused=bucket["excused"],
                sessions=bucket["present"] + bucket["absent"] + bucket["excused"],
                is_guest=True,
            ),
        )
    guest_rows.sort(key=lambda r: r.name.lower())
    rows.extend(guest_rows)

    return AttendanceMonthlyReport(
        branch_id=branch_id,
        month=month_label_for_range(date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        sessions=len(sessions),
        group_count=len(groups),
        rows=rows,
    )


async def load_group_sessions(
    db: AsyncSession,
    group_id: int,
    date_from: date,
    date_to: date,
) -> list[TrainingSession]:
    range_start, range_end = date_range_datetime_bounds(date_from, date_to)
    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id == group_id,
            TrainingSession.starts_at >= range_start,
            TrainingSession.starts_at < range_end,
            TrainingSession.canceled.is_(False),
        )
        .options(selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student)),
    )
    return list(result.scalars().unique().all())


async def load_branch_sessions(
    db: AsyncSession,
    group_ids: list[int],
    date_from: date,
    date_to: date,
) -> list[TrainingSession]:
    if not group_ids:
        return []
    range_start, range_end = date_range_datetime_bounds(date_from, date_to)
    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id.in_(group_ids),
            TrainingSession.starts_at >= range_start,
            TrainingSession.starts_at < range_end,
            TrainingSession.canceled.is_(False),
        )
        .options(selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student)),
    )
    return list(result.scalars().unique().all())


def build_student_attendance_report(
    student: Student,
    sessions: list[TrainingSession],
    date_from: date,
    date_to: date,
    *,
    roster_group_ids: set[int],
) -> ParentChildAttendanceReport:
    """Aggregate one child's range: roster sessions + guest appearances."""
    by_id: dict[int, TrainingSession] = {session.id: session for session in sessions}
    status_by_session: dict[int, AttendanceStatus] = {}
    for session in sessions:
        for record in session.attendance_records:
            if record.student_id == student.id:
                status_by_session[session.id] = record.status
                break

    present = absent = excused = 0
    entries: list[ParentChildAttendanceEntry] = []
    for session in sorted(by_id.values(), key=lambda s: (s.starts_at, s.id)):
        status = status_by_session.get(session.id)
        if status == AttendanceStatus.present:
            present += 1
        elif status == AttendanceStatus.absent:
            absent += 1
        elif status == AttendanceStatus.excused:
            excused += 1
        group = session.training_group
        group_name = group.name if group is not None else f"Skupina #{session.training_group_id}"
        entries.append(
            ParentChildAttendanceEntry(
                session_id=session.id,
                starts_at=session.starts_at,
                group_name=group_name,
                status=status,
                is_guest=session.training_group_id not in roster_group_ids,
            ),
        )

    sessions_count = len(entries)
    marked = present + absent + excused
    unmarked = max(0, sessions_count - marked)
    rate = round((present / sessions_count) * 100, 1) if sessions_count else 0.0

    return ParentChildAttendanceReport(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        month=month_label_for_range(date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        sessions=sessions_count,
        present=present,
        absent=absent,
        excused=excused,
        unmarked=unmarked,
        attendance_rate=rate,
        entries=entries,
    )


async def load_student_range_sessions(
    db: AsyncSession,
    student: Student,
    date_from: date,
    date_to: date,
) -> tuple[list[TrainingSession], set[int]]:
    """Roster-group sessions in range plus any guest sessions with a record for the student."""
    roster_group_ids = {group.id for group in student.training_groups}
    range_start, range_end = date_range_datetime_bounds(date_from, date_to)
    sessions_by_id: dict[int, TrainingSession] = {}

    if roster_group_ids:
        roster_sessions = await load_branch_sessions(db, list(roster_group_ids), date_from, date_to)
        for session in roster_sessions:
            sessions_by_id[session.id] = session

    guest_result = await db.execute(
        select(TrainingSession)
        .join(AttendanceRecord, AttendanceRecord.session_id == TrainingSession.id)
        .where(
            AttendanceRecord.student_id == student.id,
            TrainingSession.starts_at >= range_start,
            TrainingSession.starts_at < range_end,
            TrainingSession.canceled.is_(False),
        )
        .options(
            selectinload(TrainingSession.attendance_records),
            selectinload(TrainingSession.training_group),
        ),
    )
    for session in guest_result.scalars().unique().all():
        if session.id not in sessions_by_id:
            sessions_by_id[session.id] = session

    missing_group = [s for s in sessions_by_id.values() if s.training_group is None]
    if missing_group:
        result = await db.execute(
            select(TrainingSession)
            .where(TrainingSession.id.in_([s.id for s in missing_group]))
            .options(
                selectinload(TrainingSession.attendance_records),
                selectinload(TrainingSession.training_group),
            ),
        )
        for session in result.scalars().unique().all():
            sessions_by_id[session.id] = session

    return list(sessions_by_id.values()), roster_group_ids


# Back-compat alias used by older imports/tests.
async def load_student_month_sessions(
    db: AsyncSession,
    student: Student,
    month: str,
) -> tuple[list[TrainingSession], set[int]]:
    date_from, date_to = month_date_bounds(month)
    return await load_student_range_sessions(db, student, date_from, date_to)
