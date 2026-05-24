from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base, Branch, DEFAULT_BRANCHES

engine = create_async_engine(
    settings.database_url,
    echo=False,
)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_branches()
