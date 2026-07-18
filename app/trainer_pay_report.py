"""Trainer pay-attendance reports from training sessions + event RSVPs."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.attendance_report import date_range_datetime_bounds, month_label_for_range
from app.models import (
    AttendanceStatus,
    Event,
    EventRsvp,
    EventType,
    RsvpStatus,
    Trainer,
    TrainerSessionAttendance,
    TrainingSession,
)
from app.schemas import (
    AdminTrainerPayAttendanceReport,
    TrainerPayAttendanceEntry,
    TrainerPayAttendanceReport,
    TrainerPayAttendanceSummaryRow,
)

LOCAL_TZ = ZoneInfo("Europe/Prague")

STATUS_LABELS_CS = {
    AttendanceStatus.present: "přítomen",
    AttendanceStatus.absent: "nepřítomen",
    AttendanceStatus.excused: "omluven",
}

EVENT_TYPE_LABELS_CS = {
    EventType.tournament: "Turnaj",
    EventType.training: "Trénink (akce)",
    EventType.meeting: "Schůzka",
    EventType.seminar: "Školení",
    EventType.other: "Jiné",
}

RSVP_TO_ATTENDANCE = {
    RsvpStatus.yes: AttendanceStatus.present,
    RsvpStatus.no: AttendanceStatus.absent,
    RsvpStatus.maybe: AttendanceStatus.excused,
}


def _entry_from_training(record: TrainerSessionAttendance) -> TrainerPayAttendanceEntry:
    session = record.session
    group = session.training_group if session is not None else None
    branch = session.branch if session is not None else None
    trainer = record.trainer
    starts_at = session.starts_at if session is not None else None
    local = starts_at.astimezone(LOCAL_TZ) if starts_at is not None else None
    return TrainerPayAttendanceEntry(
        source="training",
        session_id=record.session_id,
        event_id=None,
        event_type=None,
        trainer_id=record.trainer_id,
        trainer_name=(
            f"{trainer.first_name} {trainer.last_name}" if trainer is not None else f"#{record.trainer_id}"
        ),
        starts_at=starts_at,
        session_date=local.date() if local is not None else None,
        start_time=local.time().replace(second=0, microsecond=0) if local is not None else None,
        branch_name=branch.name if branch is not None else "",
        group_name=group.name if group is not None else "",
        status=record.status,
    )


def _entry_from_event_rsvp(rsvp: EventRsvp) -> TrainerPayAttendanceEntry:
    event = rsvp.event
    trainer = rsvp.trainer
    starts_at = event.starts_at if event is not None else None
    local = starts_at.astimezone(LOCAL_TZ) if starts_at is not None else None
    event_type = event.event_type.value if event is not None and hasattr(event.event_type, "value") else (
        str(event.event_type) if event is not None else None
    )
    return TrainerPayAttendanceEntry(
        source="event",
        session_id=None,
        event_id=rsvp.event_id,
        event_type=event_type,
        trainer_id=rsvp.trainer_id or 0,
        trainer_name=(
            f"{trainer.first_name} {trainer.last_name}" if trainer is not None else f"#{rsvp.trainer_id}"
        ),
        starts_at=starts_at,
        session_date=local.date() if local is not None else None,
        start_time=local.time().replace(second=0, microsecond=0) if local is not None else None,
        branch_name=event.location if event is not None else "",
        group_name=event.title if event is not None else "",
        status=RSVP_TO_ATTENDANCE.get(rsvp.status, AttendanceStatus.excused),
    )


async def load_trainer_pay_records(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    *,
    trainer_id: int | None = None,
) -> list[TrainerSessionAttendance]:
    range_start, range_end = date_range_datetime_bounds(date_from, date_to)
    stmt = (
        select(TrainerSessionAttendance)
        .join(TrainingSession, TrainerSessionAttendance.session_id == TrainingSession.id)
        .where(
            TrainingSession.starts_at >= range_start,
            TrainingSession.starts_at < range_end,
            TrainingSession.canceled.is_(False),
        )
        .options(
            selectinload(TrainerSessionAttendance.session).selectinload(TrainingSession.training_group),
            selectinload(TrainerSessionAttendance.session).selectinload(TrainingSession.branch),
            selectinload(TrainerSessionAttendance.trainer),
        )
        .order_by(TrainingSession.starts_at, TrainerSessionAttendance.trainer_id)
    )
    if trainer_id is not None:
        stmt = stmt.where(TrainerSessionAttendance.trainer_id == trainer_id)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def load_trainer_event_rsvps(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    *,
    trainer_id: int | None = None,
    event_types: list[EventType] | None = None,
) -> list[EventRsvp]:
    if not event_types:
        return []
    range_start, range_end = date_range_datetime_bounds(date_from, date_to)
    stmt = (
        select(EventRsvp)
        .join(Event, EventRsvp.event_id == Event.id)
        .where(
            EventRsvp.trainer_id.is_not(None),
            Event.starts_at >= range_start,
            Event.starts_at < range_end,
            Event.event_type.in_(event_types),
        )
        .options(
            selectinload(EventRsvp.event),
            selectinload(EventRsvp.trainer),
        )
        .order_by(Event.starts_at, EventRsvp.trainer_id)
    )
    if trainer_id is not None:
        stmt = stmt.where(EventRsvp.trainer_id == trainer_id)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


def parse_event_types(raw: list[str] | None) -> list[EventType]:
    if not raw:
        return []
    out: list[EventType] = []
    for value in raw:
        try:
            out.append(EventType(value))
        except ValueError as exc:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Invalid event_type '{value}'. Expected one of: {[e.value for e in EventType]}",
            ) from exc
    return list(dict.fromkeys(out))


def _aggregate_entries(entries: list[TrainerPayAttendanceEntry]) -> tuple[int, int, int]:
    present = absent = excused = 0
    for entry in entries:
        if entry.status == AttendanceStatus.present:
            present += 1
        elif entry.status == AttendanceStatus.absent:
            absent += 1
        elif entry.status == AttendanceStatus.excused:
            excused += 1
    return present, absent, excused


def collect_pay_entries(
    training_records: list[TrainerSessionAttendance],
    event_rsvps: list[EventRsvp],
    *,
    include_trainings: bool,
) -> list[TrainerPayAttendanceEntry]:
    entries: list[TrainerPayAttendanceEntry] = []
    if include_trainings:
        entries.extend(_entry_from_training(r) for r in training_records)
    entries.extend(_entry_from_event_rsvp(r) for r in event_rsvps)
    entries.sort(
        key=lambda e: (
            e.starts_at or datetime.min.replace(tzinfo=timezone.utc),
            e.trainer_id,
            e.source,
            e.session_id or 0,
            e.event_id or 0,
        ),
    )
    return entries


def build_trainer_pay_report(
    trainer: Trainer,
    entries: list[TrainerPayAttendanceEntry],
    date_from: date,
    date_to: date,
) -> TrainerPayAttendanceReport:
    mine = [e for e in entries if e.trainer_id == trainer.id]
    present, absent, excused = _aggregate_entries(mine)
    return TrainerPayAttendanceReport(
        trainer_id=trainer.id,
        trainer_name=f"{trainer.first_name} {trainer.last_name}",
        month=month_label_for_range(date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        present=present,
        absent=absent,
        excused=excused,
        payable_sessions=present,
        entries=mine,
    )


def build_admin_trainer_pay_report(
    entries: list[TrainerPayAttendanceEntry],
    date_from: date,
    date_to: date,
) -> AdminTrainerPayAttendanceReport:
    by_trainer: dict[int, list[TrainerPayAttendanceEntry]] = {}
    names: dict[int, str] = {}
    for entry in entries:
        by_trainer.setdefault(entry.trainer_id, []).append(entry)
        names[entry.trainer_id] = entry.trainer_name

    rows: list[TrainerPayAttendanceSummaryRow] = []
    for trainer_id, trainer_entries in by_trainer.items():
        present, absent, excused = _aggregate_entries(trainer_entries)
        rows.append(
            TrainerPayAttendanceSummaryRow(
                trainer_id=trainer_id,
                trainer_name=names.get(trainer_id, f"#{trainer_id}"),
                present=present,
                absent=absent,
                excused=excused,
                payable_sessions=present,
            ),
        )
    rows.sort(key=lambda r: r.trainer_name.lower())

    return AdminTrainerPayAttendanceReport(
        month=month_label_for_range(date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        trainers=rows,
        entries=entries,
    )


def filter_entries_for_export(
    entries: list[TrainerPayAttendanceEntry],
    *,
    include_all_statuses: bool,
) -> list[TrainerPayAttendanceEntry]:
    if include_all_statuses:
        return entries
    return [e for e in entries if e.status == AttendanceStatus.present]


def write_trainer_pay_csv(
    entries: list[TrainerPayAttendanceEntry],
    *,
    include_trainer_name: bool,
) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["Zdroj", "Typ akce", "Datum", "Čas", "Místo / pobočka", "Název", "Status"]
    if include_trainer_name:
        header = ["Trenér", *header]
    writer.writerow(header)
    for entry in entries:
        status_label = STATUS_LABELS_CS.get(
            entry.status,
            str(entry.status.value if hasattr(entry.status, "value") else entry.status),
        )
        source_label = "Trénink" if entry.source == "training" else "Akce"
        event_type_label = ""
        if entry.event_type:
            try:
                event_type_label = EVENT_TYPE_LABELS_CS.get(EventType(entry.event_type), entry.event_type)
            except ValueError:
                event_type_label = entry.event_type
        row = [
            source_label,
            event_type_label,
            entry.session_date.isoformat() if entry.session_date else "",
            entry.start_time.strftime("%H:%M") if entry.start_time else "",
            entry.branch_name,
            entry.group_name,
            status_label,
        ]
        if include_trainer_name:
            row = [entry.trainer_name, *row]
        writer.writerow(row)
    return "\ufeff" + buffer.getvalue()
