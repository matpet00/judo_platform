from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Parent
from app.schemas import ParentCreate, ParentRead

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


@router.get("", response_model=list[ParentRead])
async def list_parents(db: AsyncSession = Depends(get_db)) -> list[Parent]:
    result = await db.execute(select(Parent).order_by(Parent.id))
    return list(result.scalars().all())
