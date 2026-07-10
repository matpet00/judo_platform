from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Trainer
from app.schemas import (
    BranchRead,
    TrainerAuthToken,
    TrainerCreate,
    TrainerPatch,
    TrainerPinChange,
    TrainerPinVerify,
    TrainerRead,
    TrainerStudentRead,
)
from app.security import (
    check_rate_limit,
    clear_rate_limit,
    client_ip,
    create_trainer_token,
    hash_pin,
    needs_rehash,
    record_failed_attempt,
    require_admin,
    require_trainer_token,
    verify_pin,
)
from app.trainer_students import list_trainer_students

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
        created_at=trainer.created_at,
        updated_at=trainer.updated_at,
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
    _admin: bool = Depends(require_admin),
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


@router.post("/{trainer_id}/verify-pin", response_model=TrainerAuthToken)
async def verify_trainer_pin(
    trainer_id: int,
    payload: TrainerPinVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TrainerAuthToken:
    rate_key = f"{client_ip(request)}:{trainer_id}"
    check_rate_limit("trainer_pin", rate_key)
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")
    if not verify_pin(payload.pin, trainer.pin_hash):
        record_failed_attempt("trainer_pin", rate_key)
        raise HTTPException(status_code=401, detail="Invalid PIN.")

    if needs_rehash(trainer.pin_hash):
        trainer.pin_hash = hash_pin(payload.pin)
        await db.commit()

    clear_rate_limit("trainer_pin", rate_key)
    token, expires_at = create_trainer_token(trainer.id)
    return TrainerAuthToken(
        access_token=token,
        expires_at=expires_at,
        trainer_id=trainer.id,
    )


@router.post("/me/change-pin", status_code=status.HTTP_204_NO_CONTENT)
async def change_trainer_pin(
    payload: TrainerPinChange,
    trainer_id: int = Depends(require_trainer_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")
    if not verify_pin(payload.current_pin, trainer.pin_hash):
        raise HTTPException(status_code=401, detail="Invalid current PIN.")
    trainer.pin_hash = hash_pin(payload.new_pin)
    await db.commit()


@router.get("/me/students", response_model=list[TrainerStudentRead])
async def trainer_students(
    branch_id: int = Query(..., ge=1),
    trainer_id: int = Depends(require_trainer_token),
    db: AsyncSession = Depends(get_db),
) -> list[TrainerStudentRead]:
    return await list_trainer_students(db, trainer_id, branch_id)


@router.patch("/{trainer_id}", response_model=TrainerRead)
async def patch_trainer(
    trainer_id: int,
    payload: TrainerPatch,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
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

    if "pin" in data:
        pin = data.pop("pin")
        trainer.pin_hash = hash_pin(pin) if pin else None

    if "first_name" in data:
        trainer.first_name = data["first_name"]
    if "last_name" in data:
        trainer.last_name = data["last_name"]

    await db.commit()

    result = await db.execute(
        select(Trainer).where(Trainer.id == trainer_id).options(selectinload(Trainer.branches)),
    )
    return _trainer_to_read(result.scalar_one())


@router.delete("/{trainer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trainer(
    trainer_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(require_admin),
) -> None:
    trainer = await db.get(Trainer, trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")
    await db.delete(trainer)
    await db.commit()
