from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.birth_number import validate_birth_number
from app.age_group import age_at_year_end, compute_age_group
from app.database import get_db
from app.models import Parent, Student
from app.registration_service import (
    normalize_email,
    registration_status_for_email,
    submit_registration_request,
    try_send_credentials_email,
)
from app.schemas import (
    AgeGroupPreview,
    BirthNumberStatus,
    ClubRegistrationCreate,
    ParentEmailStatus,
    RegistrationStatusRead,
    RegistrationSubmittedRead,
)

router = APIRouter(tags=["registration"])


@router.get("/age-group", response_model=AgeGroupPreview)
async def preview_age_group(
    birth_date: date = Query(..., description="Datum narození dítěte (YYYY-MM-DD)."),
    reference_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
        description="Referenční rok (výchozí: aktuální kalendářní rok).",
    ),
) -> AgeGroupPreview:
    year = reference_year if reference_year is not None else date.today().year
    try:
        age = age_at_year_end(birth_date, year)
        group = compute_age_group(birth_date, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgeGroupPreview(
        birth_date=birth_date,
        reference_year=year,
        age_at_year_end=age,
        age_group=group,
    )


@router.get("/register/parent-status", response_model=ParentEmailStatus)
async def parent_email_status(
    email: str = Query(..., min_length=3),
    db: AsyncSession = Depends(get_db),
) -> ParentEmailStatus:
    normalized = normalize_email(email)
    result = await db.execute(select(Parent).where(Parent.email == normalized))
    parent = result.scalar_one_or_none()
    if parent is None:
        return ParentEmailStatus(exists=False)
    return ParentEmailStatus(
        exists=True,
        has_login=bool(parent.username and parent.password_hash),
    )


@router.get("/register/birth-number-status", response_model=BirthNumberStatus)
async def birth_number_status(
    birth_number: str = Query(..., min_length=10, max_length=11),
    db: AsyncSession = Depends(get_db),
) -> BirthNumberStatus:
    try:
        normalized = validate_birth_number(birth_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await db.execute(select(Student.id).where(Student.birth_number == normalized))
    return BirthNumberStatus(available=result.scalar_one_or_none() is None)


@router.get("/register/status", response_model=RegistrationStatusRead)
async def registration_status(
    email: str = Query(..., min_length=3),
    db: AsyncSession = Depends(get_db),
) -> RegistrationStatusRead:
    return await registration_status_for_email(db, email)


@router.post("/register", response_model=RegistrationSubmittedRead)
async def register_to_club(
    payload: ClubRegistrationCreate,
    db: AsyncSession = Depends(get_db),
) -> RegistrationSubmittedRead:
    return await submit_registration_request(db, payload)


# Backward-compatible alias for admin resend-credentials import path.
_try_send_credentials_email = try_send_credentials_email
