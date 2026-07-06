from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.age_group import age_at_year_end, compute_age_group
from app.database import get_db
from app.mail import _smtp_configured, send_email
from app.models import Parent, Student
from app.parent_credentials import allocate_username, generate_password
from app.routers.students import _student_to_read, get_branches_by_ids, get_or_create_parent
from app.schemas import (
    AgeGroupPreview,
    ClubRegistrationCreate,
    ClubRegistrationRead,
    GuardianCredentialsRead,
    ParentEmailStatus,
    StudentParentInput,
)
from app.security import create_parent_token, hash_pin

router = APIRouter(tags=["registration"])

CLUB_NAME = "JUDO KLUB ORLOVÁ"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _credentials_email_body(
    *,
    first_name: str,
    username: str,
    password: str,
    children: list[Student],
) -> str:
    child_lines = "\n".join(
        f"- {child.first_name} {child.last_name} ({child.age_group.value})" for child in children
    )
    return (
        f"Dobrý den, {first_name},\n\n"
        f"registrace do {CLUB_NAME} proběhla úspěšně.\n\n"
        "Přihlašovací údaje do rodičovské aplikace:\n"
        f"Uživatelské jméno: {username}\n"
        f"Heslo: {password}\n\n"
        "Registrované děti:\n"
        f"{child_lines}\n\n"
        "Heslo si prosím uložte. V případě potřeby vám klub může údaje znovu předat.\n\n"
        f"{CLUB_NAME}"
    )


async def _try_send_credentials_email(
    *,
    parent: Parent,
    password: str,
    children: list[Student],
) -> tuple[bool, str | None]:
    if not parent.username:
        return False, "Rodič nemá vygenerované uživatelské jméno."
    if not _smtp_configured():
        return False, "SMTP není nastavené; e-mail s přihlašovacími údaji nebyl odeslán."

    try:
        await send_email(
            [parent.email],
            f"{CLUB_NAME} - přihlašovací údaje",
            _credentials_email_body(
                first_name=parent.first_name,
                username=parent.username,
                password=password,
                children=children,
            ),
        )
    except Exception as exc:
        return False, f"Nepodařilo se odeslat e-mail: {exc}"
    return True, None


async def _ensure_parent_credentials(
    db: AsyncSession,
    parent: Parent,
    first_name: str,
    last_name: str,
) -> tuple[str, str] | None:
    """Vygeneruje username/heslo, pokud rodič ještě nemá přihlášení."""
    if parent.username and parent.password_hash:
        return None
    username = await allocate_username(
        db,
        first_name,
        last_name,
        exclude_parent_id=parent.id,
    )
    password = generate_password()
    parent.username = username
    parent.password_plain = password
    parent.password_hash = hash_pin(password)
    if not parent.first_name:
        parent.first_name = first_name
    if not parent.last_name:
        parent.last_name = last_name
    return username, password


def _guardian_credentials_read(
    parent: Parent,
    *,
    created: tuple[str, str] | None,
) -> GuardianCredentialsRead:
    return GuardianCredentialsRead(
        parent_id=parent.id,
        first_name=parent.first_name,
        last_name=parent.last_name,
        email=parent.email,
        username=parent.username or (created[0] if created else ""),
        password=created[1] if created else None,
        credentials_created=created is not None,
    )


async def _link_second_guardian(
    db: AsyncSession,
    row: StudentParentInput,
    students: list[Student],
) -> tuple[Parent, GuardianCredentialsRead]:
    second_parent = await get_or_create_parent(db, row)
    created = await _ensure_parent_credentials(db, second_parent, row.first_name, row.last_name)
    for student in students:
        if second_parent not in student.parents:
            student.parents.append(second_parent)
    return second_parent, _guardian_credentials_read(second_parent, created=created)


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
    normalized = _normalize_email(email)
    result = await db.execute(select(Parent).where(Parent.email == normalized))
    parent = result.scalar_one_or_none()
    if parent is None:
        return ParentEmailStatus(exists=False)
    return ParentEmailStatus(
        exists=True,
        has_login=bool(parent.username and parent.password_hash),
    )


@router.post("/register", response_model=ClubRegistrationRead)
async def register_to_club(
    payload: ClubRegistrationCreate,
    db: AsyncSession = Depends(get_db),
) -> ClubRegistrationRead:
    normalized_email = _normalize_email(str(payload.email))
    result = await db.execute(select(Parent).where(Parent.email == normalized_email))
    parent = result.scalar_one_or_none()
    existing_parent = parent is not None
    created_credentials: tuple[str, str] | None = None

    if existing_parent:
        parent.phone = payload.phone
        if not parent.first_name:
            parent.first_name = payload.parent_first_name
        if not parent.last_name:
            parent.last_name = payload.parent_last_name
        created_credentials = await _ensure_parent_credentials(
            db,
            parent,
            payload.parent_first_name,
            payload.parent_last_name,
        )
    else:
        username = await allocate_username(db, payload.parent_first_name, payload.parent_last_name)
        password = generate_password()
        parent = Parent(
            first_name=payload.parent_first_name,
            last_name=payload.parent_last_name,
            email=normalized_email,
            phone=payload.phone,
            username=username,
            password_plain=password,
            password_hash=hash_pin(password),
        )
        db.add(parent)
        await db.flush()
        created_credentials = (username, password)

    created_students: list[Student] = []
    for child in payload.children:
        try:
            age_group = compute_age_group(child.birth_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{child.first_name} {child.last_name}: {exc}",
            ) from exc

        branches_list = await get_branches_by_ids(db, child.branch_ids)
        student = Student(
            first_name=child.first_name,
            last_name=child.last_name,
            age_group=age_group,
            birth_date=child.birth_date,
        )
        student.branches.extend(branches_list)
        student.parents.append(parent)
        db.add(student)
        created_students.append(student)

    second_guardian_read: GuardianCredentialsRead | None = None
    second_parent: Parent | None = None
    if payload.second_guardian is not None:
        second_parent, second_guardian_read = await _link_second_guardian(
            db,
            payload.second_guardian,
            created_students,
        )

    await db.commit()

    for student in created_students:
        await db.refresh(student, attribute_names=["parents", "branches"])

    students_read = [_student_to_read(s) for s in created_students]

    response = ClubRegistrationRead(
        parent_id=parent.id,
        students=students_read,
        existing_parent=existing_parent,
        username=parent.username,
        second_guardian=second_guardian_read,
    )

    message_parts: list[str] = ["Registrace proběhla úspěšně."]
    email_sent_parts: list[str] = []
    credential_parts: list[str] = []

    if created_credentials is not None:
        response.credentials_created = True
        response.username, response.password = created_credentials
        sent, error = await _try_send_credentials_email(
            parent=parent,
            password=created_credentials[1],
            children=created_students,
        )
        response.credentials_email_sent = sent
        response.credentials_email_error = error
        token, expires_at = create_parent_token(parent.id)
        response.access_token = token
        response.token_type = "bearer"
        response.expires_at = expires_at
        response.parent_id_token = parent.id
        if sent:
            email_sent_parts.append("1. zástupce")
        else:
            credential_parts.append(
                f"1. zástupce — uživatel {created_credentials[0]}, heslo {created_credentials[1]}.",
            )
    elif existing_parent:
        message_parts = [
            "Dítě bylo přidáno k existujícímu účtu 1. zástupce.",
            "Přihlas se svým uživatelským jménem a heslem.",
        ]

    if second_guardian_read is not None:
        if second_guardian_read.credentials_created and second_guardian_read.password:
            if second_parent is not None:
                sent, error = await _try_send_credentials_email(
                    parent=second_parent,
                    password=second_guardian_read.password,
                    children=created_students,
                )
                second_guardian_read.credentials_email_sent = sent
                second_guardian_read.credentials_email_error = error
            if second_guardian_read.credentials_email_sent:
                email_sent_parts.append("2. zástupce")
            else:
                credential_parts.append(
                    f"2. zástupce — uživatel {second_guardian_read.username}, "
                    f"heslo {second_guardian_read.password}.",
                )
        elif second_guardian_read.username:
            message_parts.append(
                f"2. zástupce už má účet (uživatel {second_guardian_read.username}).",
            )

    if email_sent_parts:
        message_parts.append(
            f"Přihlašovací údaje jsme poslali e-mailem ({', '.join(email_sent_parts)}). "
            "Zkontrolujte prosím doručenou poštu i spam.",
        )

    if credential_parts:
        message_parts.extend(credential_parts)
        message_parts.append("Uložte si přihlašovací údaje — zobrazí se jen teď.")

    response.message = " ".join(message_parts)
    return response
