import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("API_WRITE_KEY", "test-api-key")
os.environ.setdefault("PIN_PEPPER", "test-pin-pepper")

from app.database import async_session_maker, engine, migrate_schema, seed_branches
from app.main import app
from app.models import AgeGroup, Base, Branch, Parent, Student, Trainer, TrainingGroup
from app.security import hash_pin

API_KEY = "test-api-key"
DEFAULT_PIN = "1234"


async def seed_test_data() -> None:
    async with async_session_maker() as session:
        async with session.begin():
            branch = (await session.execute(select(Branch).where(Branch.name == "Orlova"))).scalar_one()

            trainer = Trainer(first_name="Petr", last_name="Matej", pin_hash=hash_pin(DEFAULT_PIN))
            trainer.branches.append(branch)
            other_trainer = Trainer(first_name="Jana", last_name="Coach", pin_hash=hash_pin(DEFAULT_PIN))
            other_trainer.branches.append(branch)

            students = [
                Student(first_name="A", last_name="Novak", age_group=AgeGroup.U8),
                Student(first_name="B", last_name="Svoboda", age_group=AgeGroup.U10),
                Student(first_name="C", last_name="Dvorak", age_group=AgeGroup.U12),
            ]
            for student in students:
                student.branches.append(branch)
                session.add(student)

            parent = Parent(
                first_name="Marie",
                last_name="Novakova",
                email="marie.novakova@example.com",
                phone="+420601234567",
                username="testparent",
                password_hash=hash_pin("testpass"),
            )
            students[0].birth_date = __import__("datetime").date(2018, 3, 15)
            students[0].birth_number = "180315/1234"
            students[0].health_insurance = "VZP ČR"
            students[0].parents.append(parent)

            session.add(trainer)
            session.add(other_trainer)
            await session.flush()

            group = TrainingGroup(
                branch_id=branch.id,
                name="Test 16:00-17:30",
                start_time=__import__("datetime").time(16, 0),
                end_time=__import__("datetime").time(17, 30),
            )
            group.students.extend(students)
            group.trainers.append(trainer)
            session.add(group)


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema()
    await seed_branches()
    await seed_test_data()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def write_headers(token: str | None = None) -> dict[str, str]:
    headers = {"X-API-Key": API_KEY}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def login_trainer(client: AsyncClient, trainer_id: int = 1, pin: str = DEFAULT_PIN) -> str:
    response = await client.post(
        f"/trainers/{trainer_id}/verify-pin",
        json={"pin": pin},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def login_parent(client: AsyncClient, username: str = "testparent", password: str = "testpass") -> str:
    response = await client.post(
        "/parents/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def parent_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login_admin(client: AsyncClient) -> str:
    response = await client.post("/admin/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    return response.json()["access_token"]


async def first_group_id(client: AsyncClient, trainer_id: int = 1) -> int:
    token = await login_trainer(client, trainer_id=trainer_id)
    response = await client.get("/training-groups", headers=write_headers(token))
    assert response.status_code == 200
    groups = response.json()
    assert groups
    return groups[0]["id"]
