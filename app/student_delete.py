"""Cascade helpers for students and branch reassignment fallbacks."""

from __future__ import annotations

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, Branch, EventRsvp, Student, student_branches

FALLBACK_BRANCH_NAME = "Pobocka1"


async def get_fallback_branch(db: AsyncSession, deleted_branch_id: int) -> Branch:
    """Default home branch for students left without a pobočka."""
    primary = await db.scalar(select(Branch).where(Branch.name == FALLBACK_BRANCH_NAME))
    if primary is not None and primary.id != deleted_branch_id:
        return primary

    fallback = await db.scalar(
        select(Branch).where(Branch.id != deleted_branch_id).order_by(Branch.id),
    )
    if fallback is None:
        raise ValueError("No fallback branch available for orphaned students.")
    return fallback


async def delete_student_cascade(db: AsyncSession, student_id: int) -> None:
    await db.execute(delete(AttendanceRecord).where(AttendanceRecord.student_id == student_id))
    await db.execute(delete(EventRsvp).where(EventRsvp.student_id == student_id))
    student = await db.get(Student, student_id)
    if student is not None:
        await db.delete(student)


async def orphan_student_ids_on_branch(db: AsyncSession, branch_id: int) -> list[int]:
    """Students assigned only to this branch (would have zero branches after unlink)."""
    also_elsewhere = select(student_branches.c.student_id).where(student_branches.c.branch_id != branch_id)
    return list(
        await db.scalars(
            select(student_branches.c.student_id)
            .where(student_branches.c.branch_id == branch_id)
            .where(student_branches.c.student_id.not_in(also_elsewhere)),
        ),
    )


async def unlink_branch_students(db: AsyncSession, branch_id: int) -> None:
    """Unlink students from a deleted branch; orphans move to fallback branch."""
    orphan_ids = await orphan_student_ids_on_branch(db, branch_id)
    fallback = await get_fallback_branch(db, branch_id) if orphan_ids else None

    await db.execute(delete(student_branches).where(student_branches.c.branch_id == branch_id))

    if not orphan_ids or fallback is None:
        return

    for student_id in orphan_ids:
        already_linked = await db.scalar(
            select(student_branches.c.student_id).where(
                student_branches.c.student_id == student_id,
                student_branches.c.branch_id == fallback.id,
            ),
        )
        if already_linked is None:
            await db.execute(
                insert(student_branches).values(student_id=student_id, branch_id=fallback.id),
            )


async def cleanup_students_without_branches(conn) -> None:
    """Assign legacy students with no branch to the fallback branch."""
    fallback_row = await conn.execute(
        text("SELECT id FROM branches WHERE name = :name LIMIT 1"),
        {"name": FALLBACK_BRANCH_NAME},
    )
    fallback = fallback_row.first()
    if fallback is None:
        return
    orlova_id = fallback[0]

    result = await conn.execute(
        text("SELECT id FROM students WHERE id NOT IN (SELECT student_id FROM student_branches)"),
    )
    for (student_id,) in result.fetchall():
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO student_branches (student_id, branch_id) "
                "VALUES (:student_id, :branch_id)",
            ),
            {"student_id": student_id, "branch_id": orlova_id},
        )
