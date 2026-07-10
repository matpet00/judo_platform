from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.birth_number import assert_birth_numbers_available
from app.age_group import compute_age_group
from app.config import settings
from app.mail import _smtp_configured, send_email
from app.models import Branch, Parent, RegistrationRequest, RegistrationRequestStatus, Student
from app.parent_credentials import allocate_username, generate_password
from app.routers.students import _student_to_read, get_branches_by_ids, get_or_create_parent
from app.schemas import (
    ClubRegistrationCreate,
    ClubRegistrationRead,
    GuardianCredentialsRead,
    RegistrationRequestChildRead,
    RegistrationRequestDetail,
    RegistrationRequestListItem,
    RegistrationStatusRead,
    RegistrationSubmittedRead,
    StudentParentInput,
)
from app.security import create_parent_token, hash_pin

CLUB_NAME = "JUDO KLUB ORLOVÁ"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_page_url() -> str:
    base = settings.allowed_origins[0] if settings.allowed_origins else "http://127.0.0.1:5173"
    return f"{base.rstrip('/')}/register"


def club_contact_line() -> str:
    if settings.smtp_from:
        return settings.smtp_from
    return CLUB_NAME


def credentials_email_body(
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
        f"registrace do {CLUB_NAME} byla schválena.\n\n"
        "Přihlašovací údaje do rodičovské aplikace:\n"
        f"Uživatelské jméno: {username}\n"
        f"Heslo: {password}\n\n"
        "Registrované děti:\n"
        f"{child_lines}\n\n"
        "Heslo si prosím uložte. V případě potřeby vám klub může údaje znovu předat.\n\n"
        f"{CLUB_NAME}"
    )


def pending_email_body(*, first_name: str) -> str:
    return (
        f"Dobrý den, {first_name},\n\n"
        f"obdrželi jsme vaši registraci do {CLUB_NAME}.\n"
        "Žádost nyní čeká na schválení klubem.\n\n"
        "Stav registrace můžete kdykoli zkontrolovat na stránce registrace "
        f"({register_page_url()}) podle e-mailu, který jste uvedli.\n\n"
        "Po schválení vám zašleme přihlašovací údaje do rodičovské aplikace.\n\n"
        f"{CLUB_NAME}"
    )


def rejection_email_body(*, first_name: str, reason: str) -> str:
    return (
        f"Dobrý den, {first_name},\n\n"
        f"vaše registrace do {CLUB_NAME} bohužel nebyla schválena.\n\n"
        f"Důvod: {reason}\n\n"
        "Můžete podat novou registraci s opravenými údaji:\n"
        f"{register_page_url()}\n\n"
        f"V případě dotazů nás kontaktujte: {club_contact_line()}\n\n"
        f"{CLUB_NAME}"
    )


async def try_send_email(*, recipients: list[str], subject: str, body: str) -> tuple[bool, str | None]:
    if not _smtp_configured():
        return False, "SMTP není nastavené; e-mail nebyl odeslán."
    try:
        await send_email(recipients, subject, body)
    except Exception as exc:
        return False, f"Nepodařilo se odeslat e-mail: {exc}"
    return True, None


async def try_send_credentials_email(
    *,
    parent: Parent,
    password: str,
    children: list[Student],
) -> tuple[bool, str | None]:
    if not parent.username:
        return False, "Rodič nemá vygenerované uživatelské jméno."
    return await try_send_email(
        recipients=[parent.email],
        subject=f"{CLUB_NAME} - přihlašovací údaje",
        body=credentials_email_body(
            first_name=parent.first_name,
            username=parent.username,
            password=password,
            children=children,
        ),
    )


async def ensure_parent_credentials(
    db: AsyncSession,
    parent: Parent,
    first_name: str,
    last_name: str,
) -> tuple[str, str] | None:
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
    parent.password_hash = hash_pin(password)
    if not parent.first_name:
        parent.first_name = first_name
    if not parent.last_name:
        parent.last_name = last_name
    return username, password


def guardian_credentials_read(
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


async def link_second_guardian(
    db: AsyncSession,
    row: StudentParentInput,
    students: list[Student],
) -> tuple[Parent, GuardianCredentialsRead]:
    second_parent = await get_or_create_parent(db, row)
    created = await ensure_parent_credentials(db, second_parent, row.first_name, row.last_name)
    for student in students:
        if second_parent not in student.parents:
            student.parents.append(second_parent)
    return second_parent, guardian_credentials_read(second_parent, created=created)


async def apply_registration(
    db: AsyncSession,
    payload: ClubRegistrationCreate,
    *,
    issue_token: bool = False,
) -> ClubRegistrationRead:
    normalized_email = normalize_email(str(payload.email))
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
        created_credentials = await ensure_parent_credentials(
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
            password_hash=hash_pin(password),
        )
        db.add(parent)
        await db.flush()
        created_credentials = (username, password)

    created_students: list[Student] = []
    await assert_birth_numbers_available(
        db,
        [child.birth_number for child in payload.children],
    )
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
            birth_number=child.birth_number,
            health_insurance=child.health_insurance,
        )
        student.branches.extend(branches_list)
        student.parents.append(parent)
        db.add(student)
        created_students.append(student)

    second_guardian_read: GuardianCredentialsRead | None = None
    second_parent: Parent | None = None
    if payload.second_guardian is not None:
        second_parent, second_guardian_read = await link_second_guardian(
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
        sent, error = await try_send_credentials_email(
            parent=parent,
            password=created_credentials[1],
            children=created_students,
        )
        response.credentials_email_sent = sent
        response.credentials_email_error = error
        if issue_token:
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
                sent, error = await try_send_credentials_email(
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
        if issue_token:
            message_parts.append("Uložte si přihlašovací údaje — zobrazí se jen teď.")

    response.message = " ".join(message_parts)
    return response


async def pending_request_for_email(db: AsyncSession, email: str) -> RegistrationRequest | None:
    result = await db.execute(
        select(RegistrationRequest)
        .where(
            RegistrationRequest.parent_email == email,
            RegistrationRequest.status == RegistrationRequestStatus.pending,
        )
        .order_by(RegistrationRequest.created_at.desc())
        .limit(1),
    )
    return result.scalar_one_or_none()


async def submit_registration_request(
    db: AsyncSession,
    payload: ClubRegistrationCreate,
) -> RegistrationSubmittedRead:
    normalized_email = normalize_email(str(payload.email))
    pending = await pending_request_for_email(db, normalized_email)
    if pending is not None:
        raise HTTPException(
            status_code=409,
            detail="Registrace s tímto e-mailem už čeká na schválení.",
        )

    await assert_birth_numbers_available(
        db,
        [child.birth_number for child in payload.children],
    )

    request = RegistrationRequest(
        status=RegistrationRequestStatus.pending,
        parent_email=normalized_email,
        payload_json=payload.model_dump(mode="json"),
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    sent, error = await try_send_email(
        recipients=[normalized_email],
        subject=f"{CLUB_NAME} - registrace přijata",
        body=pending_email_body(first_name=payload.parent_first_name),
    )

    message = (
        "Registrace přijata. Klub ji zkontroluje. "
        "Stav můžete sledovat podle e-mailu na stránce registrace."
    )
    if sent:
        message += " Potvrzení jsme poslali e-mailem."

    return RegistrationSubmittedRead(
        request_id=request.id,
        message=message,
        confirmation_email_sent=sent,
        confirmation_email_error=error,
    )


async def registration_status_for_email(db: AsyncSession, email: str) -> RegistrationStatusRead:
    normalized = normalize_email(email)
    result = await db.execute(
        select(RegistrationRequest)
        .where(RegistrationRequest.parent_email == normalized)
        .order_by(RegistrationRequest.created_at.desc())
        .limit(1),
    )
    request = result.scalar_one_or_none()
    if request is None:
        return RegistrationStatusRead(
            status="none",
            message="Pro tento e-mail nemáme žádnou registraci. Můžete podat novou žádost.",
        )

    if request.status == RegistrationRequestStatus.pending:
        return RegistrationStatusRead(
            status="pending",
            message="Registrace čeká na schválení klubem.",
            request_id=request.id,
        )

    if request.status == RegistrationRequestStatus.rejected:
        return RegistrationStatusRead(
            status="rejected",
            message="Registrace byla zamítnuta. Můžete podat novou žádost s opravenými údaji.",
            rejection_reason=request.rejection_reason,
            request_id=request.id,
            reviewed_at=request.reviewed_at,
        )

    return RegistrationStatusRead(
        status="approved",
        message="Registrace byla schválena. Přihlašovací údaje jsme poslali e-mailem.",
        request_id=request.id,
        reviewed_at=request.reviewed_at,
    )


def payload_from_request(request: RegistrationRequest) -> ClubRegistrationCreate:
    return ClubRegistrationCreate.model_validate(request.payload_json)


async def branch_names_by_ids(db: AsyncSession, branch_ids: list[int]) -> list[str]:
    if not branch_ids:
        return []
    result = await db.execute(select(Branch).where(Branch.id.in_(branch_ids)))
    by_id = {branch.id: branch.name for branch in result.scalars().all()}
    return [by_id[bid] for bid in branch_ids if bid in by_id]


async def request_to_list_item(db: AsyncSession, request: RegistrationRequest) -> RegistrationRequestListItem:
    payload = payload_from_request(request)
    return RegistrationRequestListItem(
        id=request.id,
        status=request.status.value,
        parent_first_name=payload.parent_first_name,
        parent_last_name=payload.parent_last_name,
        parent_email=request.parent_email,
        parent_phone=payload.phone,
        children_count=len(payload.children),
        has_second_guardian=payload.second_guardian is not None,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
    )


async def request_to_detail(db: AsyncSession, request: RegistrationRequest) -> RegistrationRequestDetail:
    payload = payload_from_request(request)
    children: list[RegistrationRequestChildRead] = []
    for child in payload.children:
        age_group = compute_age_group(child.birth_date)
        children.append(
            RegistrationRequestChildRead(
                first_name=child.first_name,
                last_name=child.last_name,
                birth_date=child.birth_date,
                birth_number=child.birth_number,
                health_insurance=child.health_insurance,
                branch_names=await branch_names_by_ids(db, child.branch_ids),
                age_group=age_group,
            ),
        )
    base = await request_to_list_item(db, request)
    return RegistrationRequestDetail(
        **base.model_dump(),
        children=children,
        second_guardian=payload.second_guardian,
        rejection_reason=request.rejection_reason,
        approved_parent_id=request.approved_parent_id,
    )


async def approve_registration_request(db: AsyncSession, request_id: int) -> ClubRegistrationRead:
    request = await db.get(RegistrationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Registration request not found.")
    if request.status != RegistrationRequestStatus.pending:
        raise HTTPException(status_code=409, detail="Registration request is not pending.")

    payload = payload_from_request(request)
    result = await apply_registration(db, payload, issue_token=False)
    request.status = RegistrationRequestStatus.approved
    request.reviewed_at = datetime.now(UTC)
    request.approved_parent_id = result.parent_id
    await db.commit()
    return result


async def reject_registration_request(
    db: AsyncSession,
    request_id: int,
    reason: str,
) -> RegistrationRequestDetail:
    request = await db.get(RegistrationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Registration request not found.")
    if request.status != RegistrationRequestStatus.pending:
        raise HTTPException(status_code=409, detail="Registration request is not pending.")

    payload = payload_from_request(request)
    request.status = RegistrationRequestStatus.rejected
    request.rejection_reason = reason.strip()
    request.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)

    await try_send_email(
        recipients=[request.parent_email],
        subject=f"{CLUB_NAME} - registrace zamítnuta",
        body=rejection_email_body(first_name=payload.parent_first_name, reason=reason.strip()),
    )

    return await request_to_detail(db, request)
