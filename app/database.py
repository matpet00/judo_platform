from collections.abc import AsyncGenerator

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base, Branch, DEFAULT_BRANCHES, Trainer
from app.security import hash_pin

engine = create_async_engine(
    settings.database_url,
    echo=False,
)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

DEFAULT_TRAINER_PIN = "1234"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def seed_branches() -> None:
    """Idempotentně doplní / aktualizuje výchozí pobočky a adresy."""
    async with async_session_maker() as session:
        async with session.begin():
            for name, address in DEFAULT_BRANCHES:
                result = await session.execute(select(Branch).where(Branch.name == name))
                row = result.scalar_one_or_none()
                if row is None:
                    session.add(Branch(name=name, address=address))
                else:
                    row.address = address


async def seed_trainer_pins() -> None:
    """Nastaví výchozí PIN trenérům, kteří ho ještě nemají."""
    async with async_session_maker() as session:
        async with session.begin():
            result = await session.execute(select(Trainer).where(Trainer.pin_hash.is_(None)))
            trainers = result.scalars().all()
            pin_hash = hash_pin(DEFAULT_TRAINER_PIN)
            for trainer in trainers:
                trainer.pin_hash = pin_hash


async def migrate_schema() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(trainers)"))
        columns = {row[1] for row in result.fetchall()}
        if "pin_hash" not in columns:
            await conn.execute(text("ALTER TABLE trainers ADD COLUMN pin_hash VARCHAR(128)"))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema()
    await seed_branches()
    await seed_trainer_pins()
