import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.database import async_session_maker
from app.models import Branch, Student, Trainer, TrainingGroup, student_branches, trainer_branches
from tests.conftest import login_admin, login_trainer, write_headers


@pytest.mark.asyncio
async def test_delete_branch_cascades_assignments(client: AsyncClient) -> None:
    create = await client.post(
        "/branches",
        headers=write_headers(),
        json={"name": "QA Delete Branch", "address": "Test"},
    )
    assert create.status_code == 201
    branch_id = create.json()["id"]

    admin = await login_admin(client)
    patch_trainer = await client.patch(
        "/trainers/1",
        headers=write_headers(admin),
        json={"branch_ids": [1, branch_id]},
    )
    assert patch_trainer.status_code == 200

    student = await client.post(
        "/students",
        headers=write_headers(),
        json={
            "first_name": "Del",
            "last_name": "Student",
            "age_group": "U10",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "Del",
                "last_name": "Parent",
                "email": "del.parent@example.com",
                "phone": "+420601111111",
            }],
        },
    )
    assert student.status_code == 200
    student_id = student.json()["id"]

    trainer_token = await login_trainer(client)

    group = await client.post(
        "/training-groups",
        headers=write_headers(trainer_token),
        json={
            "branch_id": branch_id,
            "name": "QA Delete Group",
            "start_time": "16:00:00",
            "end_time": "17:30:00",
            "weekdays": [1, 3],
            "student_ids": [student_id],
        },
    )
    assert group.status_code == 201

    delete = await client.delete(f"/branches/{branch_id}", headers=write_headers())
    assert delete.status_code == 204

    async with async_session_maker() as session:
        assert await session.get(Branch, branch_id) is None
        n_groups = await session.scalar(
            select(func.count()).select_from(TrainingGroup).where(TrainingGroup.branch_id == branch_id),
        )
        assert n_groups == 0
        trainer_row = await session.get(Trainer, 1)
        assert trainer_row is not None
        assert await session.get(Student, student_id) is not None
        branch_ids = (
            await session.scalars(
                select(student_branches.c.branch_id).where(student_branches.c.student_id == student_id),
            )
        ).all()
        assert branch_ids == [1]
        n_trainer_links = await session.scalar(
            select(func.count()).select_from(trainer_branches).where(trainer_branches.c.branch_id == branch_id),
        )
        assert n_trainer_links == 0
        n_student_links = await session.scalar(
            select(func.count()).select_from(student_branches).where(student_branches.c.branch_id == branch_id),
        )
        assert n_student_links == 0


@pytest.mark.asyncio
async def test_delete_branch_moves_orphans_to_orlova(client: AsyncClient) -> None:
    create = await client.post(
        "/branches",
        headers=write_headers(),
        json={"name": "QA Orphan Branch", "address": "Test"},
    )
    assert create.status_code == 201
    branch_id = create.json()["id"]

    student = await client.post(
        "/students",
        headers=write_headers(),
        json={
            "first_name": "Orphan",
            "last_name": "Move",
            "age_group": "U8",
            "branch_ids": [branch_id],
            "parents": [{
                "first_name": "Orphan",
                "last_name": "Parent",
                "email": "orphan.move@example.com",
                "phone": "+420603333333",
            }],
        },
    )
    assert student.status_code == 200
    student_id = student.json()["id"]

    delete = await client.delete(f"/branches/{branch_id}", headers=write_headers())
    assert delete.status_code == 204

    students = await client.get("/students", headers=write_headers())
    row = next(s for s in students.json() if s["id"] == student_id)
    assert [b["name"] for b in row["branches"]] == ["Orlova"]


@pytest.mark.asyncio
async def test_delete_branch_keeps_student_on_other_branch(client: AsyncClient) -> None:
    create = await client.post(
        "/branches",
        headers=write_headers(),
        json={"name": "QA Second Branch", "address": "Test 2"},
    )
    assert create.status_code == 201
    second_branch_id = create.json()["id"]

    student = await client.post(
        "/students",
        headers=write_headers(),
        json={
            "first_name": "Multi",
            "last_name": "Branch",
            "age_group": "U10",
            "branch_ids": [1, second_branch_id],
            "parents": [{
                "first_name": "Multi",
                "last_name": "Parent",
                "email": "multi.branch@example.com",
                "phone": "+420602222222",
            }],
        },
    )
    assert student.status_code == 200
    student_id = student.json()["id"]

    delete = await client.delete(f"/branches/{second_branch_id}", headers=write_headers())
    assert delete.status_code == 204

    detail = await client.get(f"/students", headers=write_headers())
    assert detail.status_code == 200
    row = next(s for s in detail.json() if s["id"] == student_id)
    assert [b["id"] for b in row["branches"]] == [1]


@pytest.mark.asyncio
async def test_patch_student_requires_branch(client: AsyncClient) -> None:
    resp = await client.patch(
        "/students/1",
        headers=write_headers(),
        json={"branch_ids": []},
    )
    assert resp.status_code == 422
