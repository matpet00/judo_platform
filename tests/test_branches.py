import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.database import async_session_maker
from app.models import Branch, Student, Trainer, TrainingGroup, student_branches, trainer_branches
from tests.conftest import login_trainer, write_headers


@pytest.mark.asyncio
async def test_delete_branch_cascades_assignments(client: AsyncClient) -> None:
    create = await client.post(
        "/branches",
        headers=write_headers(),
        json={"name": "QA Delete Branch", "address": "Test"},
    )
    assert create.status_code == 201
    branch_id = create.json()["id"]

    patch_trainer = await client.patch(
        "/trainers/1",
        headers=write_headers(),
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
        student_row = await session.get(Student, student_id)
        assert student_row is not None
        n_trainer_links = await session.scalar(
            select(func.count()).select_from(trainer_branches).where(trainer_branches.c.branch_id == branch_id),
        )
        assert n_trainer_links == 0
        n_student_links = await session.scalar(
            select(func.count()).select_from(student_branches).where(student_branches.c.branch_id == branch_id),
        )
        assert n_student_links == 0
