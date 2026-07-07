"""Shared monthly attendance report builders."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AttendanceRecord, Student, TrainingGroup, TrainingSession
from app.schemas import AttendanceMonthlyReport, AttendanceMonthlyReportRow


def month_date_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(part) for part in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


def group_active_in_month(group: TrainingGroup, month: str) -> bool:
    """Calendar groups only: weekdays set and active window overlaps month."""
    if not group.weekdays:
        return False
    start, end = month_date_bounds(month)
    if group.active_from and group.active_from > end:
        return False
    if group.active_until and group.active_until < start:
        return False
    return True


def month_datetime_bounds(month: str) -> tuple[datetime, datetime]:
    year, mon = (int(part) for part in month.split("-"))
    month_start = datetime(year, mon, 1, tzinfo=UTC)
    month_end = datetime(year + (mon == 12), (mon % 12) + 1, 1, tzinfo=UTC)
    return month_start, month_end


def build_group_attendance_report(
    group: TrainingGroup,
    sessions: list[TrainingSession],
    month: str,
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
        month=month,
        sessions=len(sessions),
        group_count=1,
        rows=rows,
    )


def build_branch_attendance_report(
    groups: list[TrainingGroup],
    sessions: list[TrainingSession],
    branch_id: int,
    month: str,
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
        month=month,
        sessions=len(sessions),
        group_count=len(groups),
        rows=rows,
    )


async def load_group_sessions(
    db: AsyncSession,
    group_id: int,
    month: str,
) -> list[TrainingSession]:
    month_start, month_end = month_datetime_bounds(month)
    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id == group_id,
            TrainingSession.starts_at >= month_start,
            TrainingSession.starts_at < month_end,
            TrainingSession.canceled.is_(False),
        )
        .options(selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student)),
    )
    return list(result.scalars().unique().all())


async def load_branch_sessions(
    db: AsyncSession,
    group_ids: list[int],
    month: str,
) -> list[TrainingSession]:
    if not group_ids:
        return []
    month_start, month_end = month_datetime_bounds(month)
    result = await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.training_group_id.in_(group_ids),
            TrainingSession.starts_at >= month_start,
            TrainingSession.starts_at < month_end,
            TrainingSession.canceled.is_(False),
        )
        .options(selectinload(TrainingSession.attendance_records).selectinload(AttendanceRecord.student)),
    )
    return list(result.scalars().unique().all())
