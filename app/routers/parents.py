from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    ChatConversation,
    ChatMessage,
    ChatParticipant,
    EventAttachment,
    EventComment,
    EventRsvp,
    Notification,
    NotificationComment,
    NotificationReadReceipt,
    NotificationTarget,
    Parent,
    Student,
    TrainingOccurrenceComment,
    student_parents,
)
from app.schemas import (
    BranchRead,
    ParentAuthToken,
    ParentChildPatch,
    ParentChildRead,
    ParentCreate,
    ParentLogin,
    ParentPasswordChange,
    ParentPatch,
    ParentRead,
    ParentSelf,
)
from app.age_group import compute_age_group
from app.birth_number import assert_birth_numbers_available
from app.security import (
    check_rate_limit,
    clear_rate_limit,
    client_ip,
    create_parent_token,
    hash_pin,
    needs_rehash,
    record_failed_attempt,
    require_admin,
    require_parent_token,
    verify_pin,
)

router = APIRouter(prefix="/parents", tags=["parents"])


def _student_to_parent_child_read(student: Student) -> ParentChildRead:
    branches_sorted = sorted(student.branches, key=lambda branch: branch.id)
    return ParentChildRead(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        age_group=student.age_group,
        birth_date=student.birth_date,
        birth_number=student.birth_number,
        health_insurance=student.health_insurance,
        branches=[BranchRead.model_validate(branch, from_attributes=True) for branch in branches_sorted],
    )


async def _get_parent_child_or_403(
    db: AsyncSession,
    parent_id: int,
    student_id: int,
) -> Student:
    result = await db.execute(
        select(Parent)
        .where(Parent.id == parent_id)
        .options(selectinload(Parent.children).selectinload(Student.branches)),
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")

    child = next((student for student in parent.children if student.id == student_id), None)
    if child is None:
        raise HTTPException(status_code=403, detail="Child not linked to this parent.")
    return child


def _normalize_email(email: str) -> str:
    return email.strip().lower()

async def _apply_parent_patch(
    db: AsyncSession,
    parent: Parent,
    data: dict,
) -> None:
    if "email" in data:
        normalized = _normalize_email(str(data["email"]))
        existing = await db.execute(
            select(Parent).where(Parent.email == normalized, Parent.id != parent.id),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Parent with this email already exists.")
        data["email"] = normalized

    for key, value in data.items():
        setattr(parent, key, value)


async def _get_parent_with_children_or_404(db: AsyncSession, parent_id: int) -> Parent:
    result = await db.execute(
        select(Parent)
        .where(Parent.id == parent_id)
        .options(selectinload(Parent.children).selectinload(Student.branches)),
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    return parent


@router.post("", response_model=ParentRead)
async def create_parent(
    payload: ParentCreate,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> Parent:
    normalized_email = _normalize_email(str(payload.email))
    existing = await db.execute(select(Parent).where(Parent.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Parent with this email already exists.")

    parent = Parent(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=normalized_email,
        phone=payload.phone,
    )
    db.add(parent)
    await db.commit()
    await db.refresh(parent)
    return parent


@router.post("/login", response_model=ParentAuthToken)
async def parent_login(
    payload: ParentLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ParentAuthToken:
    rate_key = f"{client_ip(request)}:{payload.username}"
    check_rate_limit("parent_login", rate_key)
    result = await db.execute(select(Parent).where(Parent.username == payload.username))
    parent = result.scalar_one_or_none()
    if parent is None or not verify_pin(payload.password, parent.password_hash):
        record_failed_attempt("parent_login", rate_key)
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje.")

    if needs_rehash(parent.password_hash):
        parent.password_hash = hash_pin(payload.password)
        await db.commit()

    clear_rate_limit("parent_login", rate_key)
    token, expires_at = create_parent_token(parent.id)
    return ParentAuthToken(access_token=token, expires_at=expires_at, parent_id=parent.id)


@router.get("/me", response_model=ParentSelf)
async def parent_me(
    parent_id: int = Depends(require_parent_token),
    db: AsyncSession = Depends(get_db),
) -> Parent:
    return await _get_parent_with_children_or_404(db, parent_id)


@router.patch("/me", response_model=ParentSelf)
async def patch_parent_me(
    payload: ParentPatch,
    parent_id: int = Depends(require_parent_token),
    db: AsyncSession = Depends(get_db),
) -> Parent:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    parent = await _get_parent_with_children_or_404(db, parent_id)
    await _apply_parent_patch(db, parent, data)
    await db.commit()
    return await _get_parent_with_children_or_404(db, parent_id)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_parent_password(
    payload: ParentPasswordChange,
    parent_id: int = Depends(require_parent_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    if not verify_pin(payload.current_password, parent.password_hash):
        raise HTTPException(status_code=401, detail="Invalid current password.")
    parent.password_hash = hash_pin(payload.new_password)
    await db.commit()


@router.patch("/me/children/{student_id}", response_model=ParentChildRead)
async def patch_parent_child(
    student_id: int,
    payload: ParentChildPatch,
    parent_id: int = Depends(require_parent_token),
    db: AsyncSession = Depends(get_db),
) -> ParentChildRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    student = await _get_parent_child_or_403(db, parent_id, student_id)

    if "first_name" in data:
        student.first_name = data["first_name"]
    if "last_name" in data:
        student.last_name = data["last_name"]
    if "birth_date" in data:
        birth_date = data["birth_date"]
        student.birth_date = birth_date
        if birth_date is not None:
            student.age_group = compute_age_group(birth_date)
    if "birth_number" in data:
        birth_number = data["birth_number"]
        if birth_number is not None:
            await assert_birth_numbers_available(
                db,
                [birth_number],
                exclude_student_id=student.id,
            )
        student.birth_number = birth_number
    if "health_insurance" in data:
        student.health_insurance = data["health_insurance"]

    await db.commit()

    result = await db.execute(
        select(Student)
        .where(Student.id == student_id)
        .options(selectinload(Student.branches)),
    )
    return _student_to_parent_child_read(result.scalar_one())


@router.get("", response_model=list[ParentRead])
async def list_parents(
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> list[Parent]:
    result = await db.execute(select(Parent).order_by(Parent.id))
    return list(result.scalars().all())


@router.patch("/{parent_id}", response_model=ParentRead)
async def patch_parent(
    parent_id: int,
    payload: ParentPatch,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> Parent:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")

    await _apply_parent_patch(db, parent, data)

    await db.commit()
    await db.refresh(parent)
    return parent


async def _cleanup_parent_references(db: AsyncSession, parent_id: int) -> None:
    """Detach/remove everything referencing this parent so the row can be deleted.

    SQLite may not enforce ON DELETE actions on pre-existing schemas, so we do it
    explicitly: null out authored content, drop membership rows, and remove the
    parent's chat conversations.
    """
    # Authored content: keep the record but drop the author link.
    for model, column in (
        (TrainingOccurrenceComment, TrainingOccurrenceComment.author_parent_id),
        (Notification, Notification.author_parent_id),
        (NotificationComment, NotificationComment.author_parent_id),
        (ChatMessage, ChatMessage.sender_parent_id),
        (EventComment, EventComment.author_parent_id),
        (EventAttachment, EventAttachment.uploaded_parent_id),
    ):
        await db.execute(update(model).where(column == parent_id).values({column.key: None}))

    # Membership / targeting rows: safe to remove entirely.
    await db.execute(delete(NotificationTarget).where(NotificationTarget.parent_id == parent_id))
    await db.execute(delete(NotificationReadReceipt).where(NotificationReadReceipt.parent_id == parent_id))
    await db.execute(delete(EventRsvp).where(EventRsvp.parent_id == parent_id))
    await db.execute(delete(student_parents).where(student_parents.c.parent_id == parent_id))

    # Chat: remove the parent's conversations along with their messages/participants.
    conversation_ids = (
        await db.scalars(
            select(ChatParticipant.conversation_id).where(ChatParticipant.parent_id == parent_id),
        )
    ).all()
    if conversation_ids:
        await db.execute(delete(ChatMessage).where(ChatMessage.conversation_id.in_(conversation_ids)))
        await db.execute(delete(ChatParticipant).where(ChatParticipant.conversation_id.in_(conversation_ids)))
        await db.execute(delete(ChatConversation).where(ChatConversation.id.in_(conversation_ids)))


@router.delete("/{parent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parent(
    parent_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> None:
    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    await _cleanup_parent_references(db, parent_id)
    await db.delete(parent)
    await db.commit()
