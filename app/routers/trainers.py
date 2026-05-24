from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Trainer
from app.schemas import BranchRead, TrainerCreate, TrainerPatch, TrainerRead

router = APIRouter(prefix="/trainers", tags=["trainers"])


async def get_branches_by_ids(db: AsyncSession, branch_ids: list[int]) -> list[Branch]:
    branches: list[Branch] = []
    for bid in branch_ids:
        b = await db.get(Branch, bid)
        if b is None:
            raise HTTPException(status_code=404, detail=f"Branch id not found: {bid}")
        branches.append(b)
    return branches


def _trainer_to_read(trainer: Trainer) -> TrainerRead:
    branches_sorted = sorted(trainer.branches, key=lambda br: br.id)
    return TrainerRead(
        id=trainer.id,
        first_name=trainer.first_name,
        last_name=trainer.last_name,
        branches=[BranchRead.model_validate(b, from_attributes=True) for b in branches_sorted],
    )


@router.get("", response_model=list[TrainerRead])
async def list_trainers(db: AsyncSession = Depends(get_db)) -> list[TrainerRead]:
    result = await db.execute(
        select(Trainer).options(selectinload(Trainer.branches)).order_by(Trainer.id),
    )
    trainers = result.scalars().unique().all()
    return [_trainer_to_read(t) for t in trainers]


@router.post("", response_model=TrainerRead)
async def create_trainer(
    payload: TrainerCreate,
    db: AsyncSession = Depends(get_db),
) -> TrainerRead:
    branches_list = await get_branches_by_ids(db, payload.branch_ids)

    trainer = Trainer(
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    trainer.branches.extend(branches_list)
    db.add(trainer)
    await db.commit()
    await db.refresh(trainer, attribute_names=["branches"])

    return _trainer_to_read(trainer)


@router.patch("/{trainer_id}", response_model=TrainerRead)
async def patch_trainer(
    trainer_id: int,
    payload: TrainerPatch,
    db: AsyncSession = Depends(get_db),
) -> TrainerRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    result = await db.execute(
        select(Trainer).where(Trainer.id == trainer_id).options(selectinload(Trainer.branches)),
    )
    trainer = result.scalar_one_or_none()
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")

    if "branch_ids" in data:
        branch_ids = data.pop("branch_ids")
        if branch_ids is None:
            raise HTTPException(
                status_code=400,
                detail="Field 'branch_ids' cannot be null; omit it or use a non-empty array.",
            )
        branches_list = await get_branches_by_ids(db, branch_ids)
        trainer.branches.clear()
        trainer.branches.extend(branches_list)

    if "first_name" in data:
        trainer.first_name = data["first_name"]
    if "last_name" in data:
        trainer.last_name = data["last_name"]

    await db.commit()
    await db.refresh(trainer, attribute_names=["branches"])

    return _trainer_to_read(trainer)


@router.delete("/{trainer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trainer(trainer_id: int, db: AsyncSession = Depends(get_db)) -> None:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")
    await db.delete(trainer)
    await db.commit()
