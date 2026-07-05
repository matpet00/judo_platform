from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Parent, Student
from app.schemas import (
    ParentAuthToken,
    ParentCreate,
    ParentLogin,
    ParentPatch,
    ParentRead,
    ParentSelf,
)
from app.security import create_parent_token, require_parent_token, verify_pin

router = APIRouter(prefix="/parents", tags=["parents"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("", response_model=ParentRead)
async def create_parent(
    payload: ParentCreate,
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
) -> ParentAuthToken:
    result = await db.execute(select(Parent).where(Parent.username == payload.username))
    parent = result.scalar_one_or_none()
    if parent is None or not verify_pin(payload.password, parent.password_hash):
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje.")

    token, expires_at = create_parent_token(parent.id)
    return ParentAuthToken(access_token=token, expires_at=expires_at, parent_id=parent.id)


@router.get("/me", response_model=ParentSelf)
async def parent_me(
    parent_id: int = Depends(require_parent_token),
    db: AsyncSession = Depends(get_db),
) -> Parent:
    result = await db.execute(
        select(Parent)
        .where(Parent.id == parent_id)
        .options(selectinload(Parent.children).selectinload(Student.branches)),
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    return parent


@router.get("", response_model=list[ParentRead])
async def list_parents(db: AsyncSession = Depends(get_db)) -> list[Parent]:
    result = await db.execute(select(Parent).order_by(Parent.id))
    return list(result.scalars().all())


@router.patch("/{parent_id}", response_model=ParentRead)
async def patch_parent(
    parent_id: int,
    payload: ParentPatch,
    db: AsyncSession = Depends(get_db),
) -> Parent:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")

    if "email" in data:
        normalized = _normalize_email(str(data["email"]))
        existing = await db.execute(
            select(Parent).where(Parent.email == normalized, Parent.id != parent_id),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Parent with this email already exists.")
        data["email"] = normalized

    for key, value in data.items():
        setattr(parent, key, value)

    await db.commit()
    await db.refresh(parent)
    return parent


@router.delete("/{parent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parent(parent_id: int, db: AsyncSession = Depends(get_db)) -> None:
    parent = await db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent not found.")
    await db.delete(parent)
    await db.commit()
