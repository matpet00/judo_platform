from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Branch
from app.schemas import BranchRead

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchRead])
async def list_branches(db: AsyncSession = Depends(get_db)) -> list[Branch]:
    result = await db.execute(select(Branch).order_by(Branch.id))
    return list(result.scalars().all())
