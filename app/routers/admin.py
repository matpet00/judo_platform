import csv
import io
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    AttendanceRecord,
    Branch,
    Parent,
    Student,
    Trainer,
    TrainingGroup,
    TrainingSession,
)
from app.parent_credentials import allocate_username, generate_password
from app.routers.registration import _try_send_credentials_email
from app.security import create_admin_token, hash_pin, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


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
    students_per_branch: list[AdminCountRow]
    students_per_age_group: list[AdminCountRow]


class ResendCredentialsRead(BaseModel):
    parent_id: int
    username: str
    password: str | None
    email: str
    email_sent: bool
    email_error: str | None


@router.post("/login", response_model=AdminAuthToken)
async def admin_login(payload: AdminLogin) -> AdminAuthToken:
    valid = (
        settings.admin_password
        and payload.username.strip().lower() == settings.admin_username.strip().lower()
        and payload.password == settings.admin_password
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje.")
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
        students_per_branch=students_per_branch,
        students_per_age_group=students_per_age_group,
    )


def _month_range(month: str) -> tuple[datetime, datetime]:
    try:
        year_s, month_s = month.split("-")
        year, month_n = int(year_s), int(month_s)
        start = date(year, month_n, 1)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail="Neplatný měsíc (očekávám YYYY-MM).") from exc
    end = date(year + 1, 1, 1) if month_n == 12 else date(year, month_n + 1, 1)
    return (
        datetime(start.year, start.month, start.day, tzinfo=UTC),
        datetime(end.year, end.month, end.day, tzinfo=UTC),
    )


@router.get("/attendance.csv")
async def export_attendance_csv(
    month: str = Query(..., description="Měsíc ve formátu YYYY-MM."),
    branch_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> StreamingResponse:
    start, end = _month_range(month)

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
    filename = f"dochazka-{month}.csv"
    # Prepend BOM so Excel opens UTF-8 with diacritics correctly.
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
    parent.password_plain = password
    parent.password_hash = hash_pin(password)
    await db.commit()
    await db.refresh(parent, attribute_names=["children"])

    sent, error = await _try_send_credentials_email(
        parent=parent,
        password=password,
        children=list(parent.children),
    )

    return ResendCredentialsRead(
        parent_id=parent.id,
        username=parent.username or "",
        password=password,
        email=parent.email,
        email_sent=sent,
        email_error=error,
    )
