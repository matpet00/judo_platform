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

        result = await conn.execute(text("PRAGMA table_info(notifications)"))
        notification_columns = {row[1] for row in result.fetchall()}
        if notification_columns and "visible_until" not in notification_columns:
            await conn.execute(text("ALTER TABLE notifications ADD COLUMN visible_until DATETIME"))
            await conn.execute(
                text(
                    "UPDATE notifications "
                    "SET visible_until = datetime(COALESCE(created_at, CURRENT_TIMESTAMP), '+7 days') "
                    "WHERE visible_until IS NULL",
                ),
            )
        if notification_columns and "last_activity_at" not in notification_columns:
            await conn.execute(text("ALTER TABLE notifications ADD COLUMN last_activity_at DATETIME"))
            await conn.execute(
                text(
                    "UPDATE notifications "
                    "SET last_activity_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                    "WHERE last_activity_at IS NULL",
                ),
            )
        if notification_columns and "grace_seconds" not in notification_columns:
            # Existing notifications keep the previous 7-day grace period after expiry.
            await conn.execute(text("ALTER TABLE notifications ADD COLUMN grace_seconds INTEGER DEFAULT 604800"))
            await conn.execute(text("UPDATE notifications SET grace_seconds = 604800 WHERE grace_seconds IS NULL"))

        result = await conn.execute(text("PRAGMA table_info(notification_targets)"))
        target_columns = {row[1] for row in result.fetchall()}
        if target_columns and "branch_id" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN branch_id INTEGER"))
        if target_columns and "age_group" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN age_group VARCHAR(8)"))

        result = await conn.execute(text("PRAGMA table_info(parents)"))
        parent_columns = {row[1] for row in result.fetchall()}
        if parent_columns and "username" not in parent_columns:
            await conn.execute(text("ALTER TABLE parents ADD COLUMN username VARCHAR(64)"))
        if parent_columns and "password_hash" not in parent_columns:
            await conn.execute(text("ALTER TABLE parents ADD COLUMN password_hash VARCHAR(128)"))

        result = await conn.execute(text("PRAGMA table_info(notification_reads)"))
        read_columns = {row[1] for row in result.fetchall()}
        if read_columns and "parent_id" not in read_columns:
            # Rebuild to make trainer_id nullable and add parent_id (SQLite can't drop NOT NULL in place).
            await conn.execute(text("ALTER TABLE notification_reads RENAME TO notification_reads_old"))
            await conn.execute(
                text(
                    "CREATE TABLE notification_reads ("
                    "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                    "notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE, "
                    "trainer_id INTEGER REFERENCES trainers(id) ON DELETE CASCADE, "
                    "parent_id INTEGER REFERENCES parents(id) ON DELETE CASCADE, "
                    "last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "CONSTRAINT uq_notification_read_trainer UNIQUE (notification_id, trainer_id), "
                    "CONSTRAINT uq_notification_read_parent UNIQUE (notification_id, parent_id))",
                ),
            )
            await conn.execute(
                text(
                    "INSERT INTO notification_reads (id, notification_id, trainer_id, parent_id, last_read_at) "
                    "SELECT id, notification_id, trainer_id, NULL, last_read_at FROM notification_reads_old",
                ),
            )
            await conn.execute(text("DROP TABLE notification_reads_old"))

        result = await conn.execute(text("PRAGMA table_info(notification_comments)"))
        comment_columns = {row[1] for row in result.fetchall()}
        if comment_columns and "author_parent_id" not in comment_columns:
            await conn.execute(text("ALTER TABLE notification_comments ADD COLUMN author_parent_id INTEGER"))
        if comment_columns and "updated_at" not in comment_columns:
            await conn.execute(
                text("ALTER TABLE notification_comments ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"),
            )
            await conn.execute(
                text(
                    "UPDATE notification_comments "
                    "SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                    "WHERE updated_at IS NULL",
                ),
            )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema()
    await seed_branches()
    await seed_trainer_pins()
