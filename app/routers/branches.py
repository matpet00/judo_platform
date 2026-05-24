from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Trainer, student_branches, trainer_branches
from app.schemas import (
    BranchCreate,
    BranchDetailRead,
    BranchPatch,
    StudentBrief,
    TrainerBrief,
)

router = APIRouter(prefix="/branches", tags=["branches"])


def _branch_to_detail(branch: Branch) -> BranchDetailRead:
    students_sorted = sorted(branch.students, key=lambda s: s.id)
    trainers_sorted = sorted(branch.trainers, key=lambda t: t.id)
    return BranchDetailRead(
        id=branch.id,
        name=branch.name,
        address=branch.address,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
        students=[StudentBrief.model_validate(s, from_attributes=True) for s in students_sorted],
        trainers=[TrainerBrief.model_validate(t, from_attributes=True) for t in trainers_sorted],
    )


def _branch_load_options():
    return selectinload(Branch.students), selectinload(Branch.trainers)


@router.get("", response_model=list[BranchDetailRead])
async def list_branches(db: AsyncSession = Depends(get_db)) -> list[BranchDetailRead]:
    result = await db.execute(
        select(Branch).options(*_branch_load_options()).order_by(Branch.id),
    )
    branches = result.scalars().unique().all()
    return [_branch_to_detail(b) for b in branches]


@router.post("", response_model=BranchDetailRead, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate,
    db: AsyncSession = Depends(get_db),
) -> BranchDetailRead:
    existing = await db.execute(select(Branch).where(Branch.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Branch with this name already exists.")

    branch = Branch(name=payload.name, address=payload.address)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    result = await db.execute(
        select(Branch).where(Branch.id == branch.id).options(*_branch_load_options()),
    )
    loaded = result.scalar_one()
    return _branch_to_detail(loaded)


@router.get("/{branch_id}", response_model=BranchDetailRead)
async def get_branch(branch_id: int, db: AsyncSession = Depends(get_db)) -> BranchDetailRead:
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id).options(*_branch_load_options()),
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")
    return _branch_to_detail(branch)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: int, db: AsyncSession = Depends(get_db)) -> None:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")

    n_trainers = await db.scalar(
        select(func.count()).select_from(trainer_branches).where(trainer_branches.c.branch_id == branch_id),
    )
    n_students = await db.scalar(
        select(func.count()).select_from(student_branches).where(student_branches.c.branch_id == branch_id),
    )
    if (n_trainers or 0) > 0 or (n_students or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="Branch has assigned trainers or students. Reassign or delete them first.",
        )

    await db.delete(branch)
    await db.commit()


@router.patch("/{branch_id}", response_model=BranchDetailRead)
async def patch_branch(
    branch_id: int,
    payload: BranchPatch,
    db: AsyncSession = Depends(get_db),
) -> BranchDetailRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found.")

    if "name" in data and data["name"] != branch.name:
        existing = await db.execute(
            select(Branch).where(Branch.name == data["name"], Branch.id != branch_id),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Branch with this name already exists.")

    for key, value in data.items():
        setattr(branch, key, value)

    await db.commit()
    await db.refresh(branch)

    result = await db.execute(
        select(Branch).where(Branch.id == branch_id).options(*_branch_load_options()),
    )
    loaded = result.scalar_one()
    return _branch_to_detail(loaded)
