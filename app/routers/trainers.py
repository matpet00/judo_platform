from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Trainer
from app.schemas import BranchRead, TrainerCreate, TrainerRead

router = APIRouter(prefix="/trainers", tags=["trainers"])


@router.get("", response_model=list[TrainerRead])
async def list_trainers(db: AsyncSession = Depends(get_db)) -> list[TrainerRead]:
    result = await db.execute(
        select(Trainer).options(selectinload(Trainer.branch)).order_by(Trainer.id),
    )
    trainers = result.scalars().unique().all()
    return [
        TrainerRead(
            id=t.id,
            first_name=t.first_name,
            last_name=t.last_name,
            branch=BranchRead.model_validate(t.branch, from_attributes=True),
        )
        for t in trainers
    ]


@router.post("", response_model=TrainerRead)
async def create_trainer(
    payload: TrainerCreate,
    db: AsyncSession = Depends(get_db),
) -> TrainerRead:
    branch_name = payload.branch.value
    br = await db.execute(select(Branch).where(Branch.name == branch_name))
    branch = br.scalar_one_or_none()
    if branch is None:
        raise HTTPException(
            status_code=500,
            detail=f"Branch '{branch_name}' is missing in the database. Restart the app to run seed.",
        )

    trainer = Trainer(
        first_name=payload.first_name,
        last_name=payload.last_name,
        branch_id=branch.id,
    )
    db.add(trainer)
    await db.commit()
    await db.refresh(trainer, attribute_names=["branch"])

    return TrainerRead(
        id=trainer.id,
        first_name=trainer.first_name,
        last_name=trainer.last_name,
        branch=BranchRead.model_validate(trainer.branch, from_attributes=True),
    )
