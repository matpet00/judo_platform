import csv
import io
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.attendance_report import (
    build_branch_attendance_report,
    date_range_datetime_bounds,
    group_active_in_range,
    load_branch_sessions,
    resolve_attendance_range,
)
from app.config import settings
from app.database import get_db
from app.models import (
    AttendanceRecord,
    Branch,
    Event,
    EventRsvp,
    Parent,
    RegistrationRequest,
    RegistrationRequestStatus,
    RsvpStatus,
    Student,
    Trainer,
    TrainingGroup,
    TrainingSession,
)
from app.parent_credentials import allocate_username, generate_password
from app.registration_service import (
    approve_registration_request,
    reject_registration_request,
    request_to_detail,
    request_to_list_item,
    try_send_credentials_email,
)
from app.schemas import (
    AttendanceMonthlyReport,
    ClubRegistrationRead,
    RegistrationRejectBody,
    RegistrationRequestDetail,
    RegistrationRequestListItem,
)
from app.security import (
    check_rate_limit,
    clear_rate_limit,
    client_ip,
    create_admin_token,
    hash_pin,
    record_failed_attempt,
    require_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"])

LOCAL_TZ = ZoneInfo("Europe/Prague")

_EVENT_TYPE_LABELS = {
    "tournament": "Turnaj",
    "training": "Trénink",
    "meeting": "Schůzka",
    "seminar": "Školení",
    "other": "Akce",
}

_RSVP_LABELS = {
    "yes": "Ano",
    "no": "Ne",
    "maybe": "Možná",
}


class AdminLogin(BaseModel):
    username: str
    password: str


class AdminAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminCountRow(BaseModel):
    label: str
    count: int


class AdminStats(BaseModel):
    trainers: int
    students: int
    parents: int
    branches: int
    training_groups: int
    parents_without_login: int
    pending_registrations: int
    students_per_branch: list[AdminCountRow]
    students_per_age_group: list[AdminCountRow]


class ResendCredentialsRead(BaseModel):
    parent_id: int
    username: str
    email: str
    email_sent: bool
    email_error: str | None


class AdminEventParticipantRow(BaseModel):
    kind: str = Field(description="trainer nebo student")
    person_id: int
    name: str
    status: RsvpStatus
    age_group: str | None = None
    parent_name: str | None = None


class AdminEventParticipationRead(BaseModel):
    event_id: int
    title: str
    event_type: str
    starts_at: datetime
    location: str
    yes_count: int = 0
    no_count: int = 0
    maybe_count: int = 0
    trainer_yes: int = 0
    student_yes: int = 0
    participants: list[AdminEventParticipantRow] = Field(default_factory=list)


def _event_load_options():
    return (
        selectinload(Event.rsvps).selectinload(EventRsvp.trainer),
        selectinload(Event.rsvps).selectinload(EventRsvp.parent),
        selectinload(Event.rsvps).selectinload(EventRsvp.student),
    )


def _participants_for_event(event: Event) -> list[AdminEventParticipantRow]:
    rows: list[AdminEventParticipantRow] = []
    for rsvp in event.rsvps:
        if rsvp.trainer is not None:
            rows.append(
                AdminEventParticipantRow(
                    kind="trainer",
                    person_id=rsvp.trainer_id,
                    name=f"{rsvp.trainer.first_name} {rsvp.trainer.last_name}",
                    status=rsvp.status,
                ),
            )
        elif rsvp.student is not None:
            age = rsvp.student.age_group.value if hasattr(rsvp.student.age_group, "value") else str(rsvp.student.age_group)
            parent_name = (
                f"{rsvp.parent.first_name} {rsvp.parent.last_name}" if rsvp.parent is not None else None
            )
            rows.append(
                AdminEventParticipantRow(
                    kind="student",
                    person_id=rsvp.student_id,
                    name=f"{rsvp.student.first_name} {rsvp.student.last_name}",
                    status=rsvp.status,
                    age_group=age,
                    parent_name=parent_name,
                ),
            )
    rows.sort(key=lambda r: (0 if r.kind == "trainer" else 1, r.name.lower()))
    return rows


def _event_to_participation_read(event: Event) -> AdminEventParticipationRead:
    participants = _participants_for_event(event)
    yes = sum(1 for p in participants if p.status == RsvpStatus.yes)
    no = sum(1 for p in participants if p.status == RsvpStatus.no)
    maybe = sum(1 for p in participants if p.status == RsvpStatus.maybe)
    trainer_yes = sum(1 for p in participants if p.kind == "trainer" and p.status == RsvpStatus.yes)
    student_yes = sum(1 for p in participants if p.kind == "student" and p.status == RsvpStatus.yes)
    event_type = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
    return AdminEventParticipationRead(
        event_id=event.id,
        title=event.title,
        event_type=event_type,
        starts_at=event.starts_at,
        location=event.location,
        yes_count=yes,
        no_count=no,
        maybe_count=maybe,
        trainer_yes=trainer_yes,
        student_yes=student_yes,
        participants=participants,
    )


@router.post("/login", response_model=AdminAuthToken)
async def admin_login(payload: AdminLogin, request: Request) -> AdminAuthToken:
    rate_key = f"{client_ip(request)}:{payload.username.strip().lower()}"
    check_rate_limit("admin_login", rate_key)
    valid = (
        settings.admin_password
        and payload.username.strip().lower() == settings.admin_username.strip().lower()
        and payload.password == settings.admin_password
    )
    if not valid:
        record_failed_attempt("admin_login", rate_key)
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje.")
    clear_rate_limit("admin_login", rate_key)
    token, expires_at = create_admin_token()
    return AdminAuthToken(access_token=token, expires_at=expires_at)


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> AdminStats:
    trainers = await db.scalar(select(func.count()).select_from(Trainer)) or 0
    students = await db.scalar(select(func.count()).select_from(Student)) or 0
    parents = await db.scalar(select(func.count()).select_from(Parent)) or 0
    branches = await db.scalar(select(func.count()).select_from(Branch)) or 0
    groups = await db.scalar(select(func.count()).select_from(TrainingGroup)) or 0
    parents_without_login = (
        await db.scalar(
            select(func.count()).select_from(Parent).where(Parent.username.is_(None)),
        )
        or 0
    )
    pending_registrations = (
        await db.scalar(
            select(func.count())
            .select_from(RegistrationRequest)
            .where(RegistrationRequest.status == RegistrationRequestStatus.pending),
        )
        or 0
    )

    branch_rows_result = await db.execute(
        select(Branch.name, func.count(Student.id))
        .select_from(Branch)
        .outerjoin(Branch.students)
        .group_by(Branch.id)
        .order_by(Branch.name),
    )
    students_per_branch = [
        AdminCountRow(label=name, count=count) for name, count in branch_rows_result.all()
    ]

    age_rows_result = await db.execute(
        select(Student.age_group, func.count(Student.id))
        .group_by(Student.age_group)
        .order_by(Student.age_group),
    )
    students_per_age_group = [
        AdminCountRow(
            label=age.value if hasattr(age, "value") else str(age),
            count=count,
        )
        for age, count in age_rows_result.all()
    ]

    return AdminStats(
        trainers=trainers,
        students=students,
        parents=parents,
        branches=branches,
        training_groups=groups,
        parents_without_login=parents_without_login,
        pending_registrations=pending_registrations,
        students_per_branch=students_per_branch,
        students_per_age_group=students_per_age_group,
    )


def _month_range(month: str) -> tuple[datetime, datetime]:
    """Legacy helper — prefer resolve_attendance_range + date_range_datetime_bounds."""
    try:
        range_from, range_to = resolve_attendance_range(month=month)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Neplatný měsíc (očekávám YYYY-MM).") from exc
    return date_range_datetime_bounds(range_from, range_to)


@router.get("/attendance-report", response_model=AttendanceMonthlyReport)
async def admin_branch_attendance_report(
    branch_id: int = Query(..., ge=1),
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
    date_from: date | None = Query(default=None, description="Inclusive start (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Inclusive end (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> AttendanceMonthlyReport:
    range_from, range_to = resolve_attendance_range(month=month, date_from=date_from, date_to=date_to)
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")

    result = await db.execute(
        select(TrainingGroup)
        .where(TrainingGroup.branch_id == branch_id)
        .options(
            selectinload(TrainingGroup.students),
            selectinload(TrainingGroup.branch),
        ),
    )
    groups = [g for g in result.scalars().unique().all() if group_active_in_range(g, range_from, range_to)]
    group_ids = [g.id for g in groups]
    sessions = await load_branch_sessions(db, group_ids, range_from, range_to)
    return build_branch_attendance_report(groups, sessions, branch_id, range_from, range_to)


@router.get("/attendance.csv")
async def export_attendance_csv(
    month: str | None = Query(default=None, description="Měsíc ve formátu YYYY-MM."),
    date_from: date | None = Query(default=None, description="Inclusive start (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Inclusive end (YYYY-MM-DD)"),
    branch_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> StreamingResponse:
    range_from, range_to = resolve_attendance_range(month=month, date_from=date_from, date_to=date_to)
    start, end = date_range_datetime_bounds(range_from, range_to)

    stmt = (
        select(AttendanceRecord)
        .join(TrainingSession, AttendanceRecord.session_id == TrainingSession.id)
        .where(TrainingSession.starts_at >= start, TrainingSession.starts_at < end)
        .options(
            selectinload(AttendanceRecord.session).selectinload(TrainingSession.training_group),
            selectinload(AttendanceRecord.session).selectinload(TrainingSession.branch),
            selectinload(AttendanceRecord.student),
        )
        .order_by(TrainingSession.starts_at, AttendanceRecord.id)
    )
    if branch_id is not None:
        stmt = stmt.where(TrainingSession.branch_id == branch_id)

    records = (await db.execute(stmt)).scalars().unique().all()

    status_labels = {"present": "přítomen", "absent": "nepřítomen", "excused": "omluven"}

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Datum", "Pobočka", "Trénink", "Dítě", "Věk. kategorie", "Docházka"])
    for rec in records:
        session = rec.session
        group = session.training_group if session is not None else None
        branch = session.branch if session is not None else None
        student = rec.student
        starts_at = session.starts_at if session is not None else None
        age = student.age_group.value if student and hasattr(student.age_group, "value") else ""
        status_value = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
        writer.writerow(
            [
                starts_at.date().isoformat() if starts_at else "",
                branch.name if branch else "",
                group.name if group else "",
                f"{student.first_name} {student.last_name}" if student else "",
                age,
                status_labels.get(status_value, status_value),
            ],
        )

    buffer.seek(0)
    filename = f"dochazka-{range_from.isoformat()}_{range_to.isoformat()}.csv"
    # Prepend BOM so Excel opens UTF-8 with diacritics correctly.
    content = "\ufeff" + buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/event-participation", response_model=list[AdminEventParticipationRead])
async def admin_event_participation(
    month: str | None = Query(default=None, description="Měsíc ve formátu YYYY-MM."),
    date_from: date | None = Query(default=None, description="Inclusive start (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Inclusive end (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> list[AdminEventParticipationRead]:
    range_from, range_to = resolve_attendance_range(month=month, date_from=date_from, date_to=date_to)
    start, end = date_range_datetime_bounds(range_from, range_to)
    result = await db.execute(
        select(Event)
        .where(Event.starts_at >= start, Event.starts_at < end)
        .options(*_event_load_options())
        .order_by(Event.starts_at.desc(), Event.id.desc()),
    )
    events = result.scalars().unique().all()
    return [_event_to_participation_read(event) for event in events]


@router.get("/event-participation.csv")
async def export_event_participation_csv(
    month: str | None = Query(default=None, description="Měsíc ve formátu YYYY-MM."),
    date_from: date | None = Query(default=None, description="Inclusive start (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Inclusive end (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> StreamingResponse:
    range_from, range_to = resolve_attendance_range(month=month, date_from=date_from, date_to=date_to)
    start, end = date_range_datetime_bounds(range_from, range_to)
    result = await db.execute(
        select(Event)
        .where(Event.starts_at >= start, Event.starts_at < end)
        .options(*_event_load_options())
        .order_by(Event.starts_at.asc(), Event.id.asc()),
    )
    events = result.scalars().unique().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Datum", "Čas", "Akce", "Typ", "Místo", "Role", "Jméno", "Věk. kategorie", "Rodič", "Účast"],
    )
    for event in events:
        local = event.starts_at.astimezone(LOCAL_TZ)
        type_label = _EVENT_TYPE_LABELS.get(
            event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            "Akce",
        )
        for participant in _participants_for_event(event):
            status_value = participant.status.value if hasattr(participant.status, "value") else str(participant.status)
            writer.writerow(
                [
                    local.date().isoformat(),
                    local.strftime("%H:%M"),
                    event.title,
                    type_label,
                    event.location,
                    "Trenér" if participant.kind == "trainer" else "Dítě",
                    participant.name,
                    participant.age_group or "",
                    participant.parent_name or "",
                    _RSVP_LABELS.get(status_value, status_value),
                ],
            )

    buffer.seek(0)
    filename = f"ucast-akce-{range_from.isoformat()}_{range_to.isoformat()}.csv"
    content = "\ufeff" + buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/parents/{parent_id}/resend-credentials", response_model=ResendCredentialsRead)
async def resend_parent_credentials(
    parent_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> ResendCredentialsRead:
    result = await db.execute(
        select(Parent).where(Parent.id == parent_id).options(selectinload(Parent.children)),
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Rodič nenalezen.")

    if not parent.username:
        parent.username = await allocate_username(
            db,
            parent.first_name,
            parent.last_name,
            exclude_parent_id=parent.id,
        )

    password = generate_password()
    parent.password_hash = hash_pin(password)
    await db.commit()
    await db.refresh(parent, attribute_names=["children"])

    sent, error = await try_send_credentials_email(
        parent=parent,
        password=password,
        children=list(parent.children),
    )

    return ResendCredentialsRead(
        parent_id=parent.id,
        username=parent.username or "",
        email=parent.email,
        email_sent=sent,
        email_error=error,
    )


@router.get("/registration-requests", response_model=list[RegistrationRequestListItem])
async def list_registration_requests(
    status: RegistrationRequestStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> list[RegistrationRequestListItem]:
    query = select(RegistrationRequest).order_by(RegistrationRequest.created_at.desc())
    if status is not None:
        query = query.where(RegistrationRequest.status == status)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [await request_to_list_item(db, row) for row in rows]


@router.get("/registration-requests/{request_id}", response_model=RegistrationRequestDetail)
async def get_registration_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> RegistrationRequestDetail:
    request = await db.get(RegistrationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Registration request not found.")
    return await request_to_detail(db, request)


@router.post("/registration-requests/{request_id}/approve", response_model=ClubRegistrationRead)
async def approve_registration(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> ClubRegistrationRead:
    return await approve_registration_request(db, request_id)


@router.post("/registration-requests/{request_id}/reject", response_model=RegistrationRequestDetail)
async def reject_registration(
    request_id: int,
    payload: RegistrationRejectBody,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> RegistrationRequestDetail:
    return await reject_registration_request(db, request_id, payload.reason)
