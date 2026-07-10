from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AttendanceRecord, Student, Trainer, TrainingGroup, TrainingSession
from app.schemas import BranchRead, ParentRead, TrainerStudentRead


def _home_branch_label(student: Student) -> str | None:
    names = sorted(branch.name for branch in student.branches)
    return ", ".join(names) if names else None


def _student_to_trainer_read(
    student: Student,
    *,
    training_groups: list[str],
    is_guest: bool,
) -> TrainerStudentRead:
    branches_sorted = sorted(student.branches, key=lambda branch: branch.id)
    return TrainerStudentRead(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        age_group=student.age_group,
        birth_date=student.birth_date,
        birth_number=student.birth_number,
        health_insurance=student.health_insurance,
        branches=[BranchRead.model_validate(branch, from_attributes=True) for branch in branches_sorted],
        parents=[ParentRead.model_validate(parent, from_attributes=True) for parent in student.parents],
        training_groups=sorted(training_groups),
        is_guest=is_guest,
        home_branch=_home_branch_label(student) if is_guest else None,
    )


async def list_trainer_students(
    db: AsyncSession,
    trainer_id: int,
    branch_id: int,
) -> list[TrainerStudentRead]:
    trainer = await db.get(
        Trainer,
        trainer_id,
        options=[selectinload(Trainer.branches)],
    )
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found.")

    trainer_branch_ids = {branch.id for branch in trainer.branches}
    if branch_id not in trainer_branch_ids:
        raise HTTPException(status_code=403, detail="Branch not assigned to trainer.")

    result = await db.execute(
        select(TrainingGroup)
        .join(TrainingGroup.trainers)
        .where(Trainer.id == trainer_id, TrainingGroup.branch_id == branch_id)
        .options(
            selectinload(TrainingGroup.students).selectinload(Student.branches),
            selectinload(TrainingGroup.students).selectinload(Student.parents),
        ),
    )
    groups = result.scalars().unique().all()

    roster_groups: dict[int, list[str]] = {}
    roster_students: dict[int, Student] = {}
    group_ids: list[int] = []
    for group in groups:
        group_ids.append(group.id)
        for student in group.students:
            roster_students[student.id] = student
            roster_groups.setdefault(student.id, []).append(group.name)

    guest_ids: set[int] = set()
    if group_ids:
        attendance_result = await db.execute(
            select(AttendanceRecord)
            .join(TrainingSession, AttendanceRecord.session_id == TrainingSession.id)
            .where(TrainingSession.training_group_id.in_(group_ids))
            .options(selectinload(AttendanceRecord.student)),
        )
        for record in attendance_result.scalars().unique().all():
            if record.student_id not in roster_students:
                guest_ids.add(record.student_id)

    guest_students: dict[int, Student] = {}
    if guest_ids:
        guest_result = await db.execute(
            select(Student)
            .where(Student.id.in_(guest_ids))
            .options(
                selectinload(Student.branches),
                selectinload(Student.parents),
            ),
        )
        for student in guest_result.scalars().unique().all():
            guest_students[student.id] = student

    items: list[TrainerStudentRead] = []
    for student_id in sorted(
        roster_students,
        key=lambda sid: (
            roster_students[sid].last_name.lower(),
            roster_students[sid].first_name.lower(),
            sid,
        ),
    ):
        student = roster_students[student_id]
        items.append(
            _student_to_trainer_read(
                student,
                training_groups=roster_groups.get(student_id, []),
                is_guest=False,
            ),
        )

    for student_id in sorted(
        guest_students,
        key=lambda sid: (
            guest_students[sid].last_name.lower(),
            guest_students[sid].first_name.lower(),
            sid,
        ),
    ):
        student = guest_students[student_id]
        items.append(
            _student_to_trainer_read(
                student,
                training_groups=[],
                is_guest=True,
            ),
        )

    return items
