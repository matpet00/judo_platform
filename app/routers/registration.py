from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.age_group import age_at_year_end, compute_age_group
from app.database import get_db
from app.registration_service import (
    registration_status_for_email,
    submit_registration_request,
    try_send_credentials_email,
)
from app.schemas import (
    AgeGroupPreview,
    ClubRegistrationCreate,
    RegistrationStatusQuery,
    RegistrationStatusRead,
    RegistrationSubmittedRead,
)
from app.security import check_rate_limit, client_ip

router = APIRouter(tags=["registration"])


def _limit_registration_lookup(request: Request) -> None:
    check_rate_limit("register_lookup", client_ip(request))


@router.get("/age-group", response_model=AgeGroupPreview)
async def preview_age_group(
    request: Request,
    birth_date: date = Query(..., description="Datum narození dítěte (YYYY-MM-DD)."),
    reference_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
        description="Referenční rok (výchozí: aktuální kalendářní rok).",
    ),
) -> AgeGroupPreview:
    _limit_registration_lookup(request)
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


@router.post("/register/status", response_model=RegistrationStatusRead)
async def registration_status(
    payload: RegistrationStatusQuery,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegistrationStatusRead:
    _limit_registration_lookup(request)
    return await registration_status_for_email(db, str(payload.email))


@router.post("/register", response_model=RegistrationSubmittedRead)
async def register_to_club(
    payload: ClubRegistrationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegistrationSubmittedRead:
    check_rate_limit("register_submit", client_ip(request))
    return await submit_registration_request(db, payload)


# Backward-compatible alias for admin resend-credentials import path.
_try_send_credentials_email = try_send_credentials_email
