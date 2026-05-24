from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Branch, Parent, Student
from app.schemas import BranchRead, ParentRead, StudentCreate, StudentParentInput, StudentRead

router = APIRouter(prefix="/students", tags=["students"])

MAX_PARENTS_PER_STUDENT = 2


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_or_create_parent(db: AsyncSession, row: StudentParentInput) -> Parent:
    normalized_email = _normalize_email(str(row.email))
    result = await db.execute(select(Parent).where(Parent.email == normalized_email))
    parent = result.scalar_one_or_none()
    if parent is not None:
        parent.phone = row.phone
        return parent
    parent = Parent(
        first_name=row.first_name,
        last_name=row.last_name,
        email=normalized_email,
        phone=row.phone,
    )
    db.add(parent)
    await db.flush()
    return parent


@router.post("", response_model=StudentRead)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
) -> StudentRead:
    if len(payload.parents) > MAX_PARENTS_PER_STUDENT:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_PARENTS_PER_STUDENT} parents per student.",
        )
    emails = [_normalize_email(str(p.email)) for p in payload.parents]
    if len(set(emails)) != len(emails):
        raise HTTPException(status_code=400, detail="Duplicate parent emails in one request are not allowed.")

    branch_name = payload.branch.value
    br = await db.execute(select(Branch).where(Branch.name == branch_name))
    branch = br.scalar_one_or_none()
    if branch is None:
        raise HTTPException(
            status_code=500,
            detail=f"Branch '{branch_name}' is missing in the database. Restart the app to run seed.",
        )

    parents: list[Parent] = []
    for p in payload.parents:
        parents.append(await get_or_create_parent(db, p))

    student = Student(
        first_name=payload.first_name,
        last_name=payload.last_name,
        age_group=payload.age_group,
        branch_id=branch.id,
    )
    student.parents.extend(parents)
    db.add(student)
    await db.commit()
    await db.refresh(student, attribute_names=["parents", "branch"])

    return StudentRead(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        age_group=student.age_group,
        branch=BranchRead.model_validate(student.branch, from_attributes=True),
        parents=[
            ParentRead.model_validate(x, from_attributes=True) for x in student.parents
        ],
    )


@router.get("", response_model=list[StudentRead])
async def list_students(db: AsyncSession = Depends(get_db)) -> list[StudentRead]:
    result = await db.execute(
        select(Student)
        .options(
            selectinload(Student.parents),
            selectinload(Student.branch),
        )
        .order_by(Student.id),
    )
    students = result.scalars().unique().all()
    return [
        StudentRead(
            id=s.id,
            first_name=s.first_name,
            last_name=s.last_name,
            age_group=s.age_group,
            branch=BranchRead.model_validate(s.branch, from_attributes=True),
            parents=[ParentRead.model_validate(p, from_attributes=True) for p in s.parents],
        )
        for s in students
    ]
