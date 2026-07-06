from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AttendanceRecord, Branch, Parent, Student, TrainingSession
from app.schemas import (
    AttendanceRecordWithSessionRead,
    BranchRead,
    ParentRead,
    StudentCreate,
    StudentParentInput,
    StudentPatch,
    StudentRead,
)
from app.routers.training_sessions import attendance_with_session_to_read

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


async def get_branches_by_ids(db: AsyncSession, branch_ids: list[int]) -> list[Branch]:
    branches: list[Branch] = []
    for bid in branch_ids:
        b = await db.get(Branch, bid)
        if b is None:
            raise HTTPException(status_code=404, detail=f"Branch id not found: {bid}")
        branches.append(b)
    return branches


def _student_to_read(student: Student) -> StudentRead:
    branches_sorted = sorted(student.branches, key=lambda br: br.id)
    return StudentRead(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        age_group=student.age_group,
        birth_date=student.birth_date,
        created_at=student.created_at,
        updated_at=student.updated_at,
        branches=[BranchRead.model_validate(b, from_attributes=True) for b in branches_sorted],
        parents=[ParentRead.model_validate(p, from_attributes=True) for p in student.parents],
    )


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

    branches_list = await get_branches_by_ids(db, payload.branch_ids)

    parents: list[Parent] = []
    for p in payload.parents:
        parents.append(await get_or_create_parent(db, p))

    student = Student(
        first_name=payload.first_name,
        last_name=payload.last_name,
        age_group=payload.age_group,
        birth_date=payload.birth_date,
    )
    student.branches.extend(branches_list)
    student.parents.extend(parents)
    db.add(student)
    await db.commit()
    await db.refresh(student, attribute_names=["parents", "branches"])

    return _student_to_read(student)


@router.get("", response_model=list[StudentRead])
async def list_students(db: AsyncSession = Depends(get_db)) -> list[StudentRead]:
    result = await db.execute(
        select(Student)
        .options(
            selectinload(Student.parents),
            selectinload(Student.branches),
        )
        .order_by(Student.id),
    )
    students = result.scalars().unique().all()
    return [_student_to_read(s) for s in students]


@router.patch("/{student_id}", response_model=StudentRead)
async def patch_student(
    student_id: int,
    payload: StudentPatch,
    db: AsyncSession = Depends(get_db),
) -> StudentRead:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    result = await db.execute(
        select(Student)
        .where(Student.id == student_id)
        .options(selectinload(Student.parents), selectinload(Student.branches)),
    )
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    if "parents" in data:
        parents_payload = data.pop("parents")
        if parents_payload is None:
            raise HTTPException(
                status_code=400,
                detail="Field 'parents' cannot be null; omit it or use an array (possibly empty).",
            )
        if len(parents_payload) > MAX_PARENTS_PER_STUDENT:
            raise HTTPException(
                status_code=400,
                detail=f"At most {MAX_PARENTS_PER_STUDENT} parents per student.",
            )
        emails = [_normalize_email(str(p["email"])) for p in parents_payload]
        if len(set(emails)) != len(emails):
            raise HTTPException(status_code=400, detail="Duplicate parent emails in one request are not allowed.")
        student.parents.clear()
        for raw in parents_payload:
            row = StudentParentInput.model_validate(raw)
            student.parents.append(await get_or_create_parent(db, row))

    if "branch_ids" in data:
        branch_ids = data.pop("branch_ids")
        if branch_ids is None:
            raise HTTPException(
                status_code=400,
                detail="Field 'branch_ids' cannot be null; omit it or use a non-empty array.",
            )
        branches_list = await get_branches_by_ids(db, branch_ids)
        student.branches.clear()
        student.branches.extend(branches_list)

    if "first_name" in data:
        student.first_name = data["first_name"]
    if "last_name" in data:
        student.last_name = data["last_name"]
    if "age_group" in data:
        student.age_group = data["age_group"]
    if "birth_date" in data:
        student.birth_date = data["birth_date"]

    await db.commit()
    await db.refresh(student, attribute_names=["parents", "branches"])

    return _student_to_read(student)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db)) -> None:
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    await db.delete(student)
    await db.commit()


@router.get("/{student_id}/attendance", response_model=list[AttendanceRecordWithSessionRead])
async def list_student_attendance(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    session_id: int | None = Query(default=None, ge=1),
) -> list[AttendanceRecordWithSessionRead]:
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    stmt = (
        select(AttendanceRecord)
        .where(AttendanceRecord.student_id == student_id)
        .options(
            selectinload(AttendanceRecord.student),
            selectinload(AttendanceRecord.recorded_by),
            selectinload(AttendanceRecord.session).selectinload(TrainingSession.branch),
            selectinload(AttendanceRecord.session).selectinload(TrainingSession.training_group),
            selectinload(AttendanceRecord.session).selectinload(TrainingSession.trainer),
        )
        .order_by(AttendanceRecord.updated_at.desc(), AttendanceRecord.id.desc())
    )
    if session_id is not None:
        stmt = stmt.where(AttendanceRecord.session_id == session_id)

    result = await db.execute(stmt)
    records = result.scalars().unique().all()
    return [attendance_with_session_to_read(r) for r in records]
