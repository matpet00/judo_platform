from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    AgeGroup,
    Base,
    Branch,
    DEFAULT_BRANCHES,
    DEFAULT_DEMO_STUDENTS,
    DEFAULT_EVENT,
    DEFAULT_TRAINERS,
    DEFAULT_TRAINING_GROUPS,
    Event,
    EventTarget,
    NotificationAudience,
    Student,
    Trainer,
    TrainingGroup,
)
from app.security import hash_pin

engine = create_async_engine(
    settings.database_url,
    echo=False,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        """Tune SQLite for concurrent access.

        WAL lets readers run while a single writer commits (default rollback
        journal blocks readers during writes), and busy_timeout makes writers
        wait for a held lock instead of instantly failing with 'database is
        locked' under concurrency.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
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


async def seed_trainers() -> None:
    """Idempotentně doplní výchozí trenéry a jejich pobočky."""
    async with async_session_maker() as session:
        async with session.begin():
            branch_rows = (await session.execute(select(Branch))).scalars().all()
            by_name = {b.name: b for b in branch_rows}
            for first_name, last_name, branch_names in DEFAULT_TRAINERS:
                result = await session.execute(
                    select(Trainer)
                    .where(Trainer.first_name == first_name, Trainer.last_name == last_name)
                    .options(selectinload(Trainer.branches)),
                )
                trainer = result.scalar_one_or_none()
                branches = [by_name[name] for name in branch_names if name in by_name]
                if not branches:
                    continue
                if trainer is None:
                    trainer = Trainer(first_name=first_name, last_name=last_name)
                    trainer.branches.extend(branches)
                    session.add(trainer)
                else:
                    existing_ids = {b.id for b in trainer.branches}
                    target_ids = {b.id for b in branches}
                    if existing_ids != target_ids:
                        trainer.branches.clear()
                        trainer.branches.extend(branches)


async def _trainer_by_name(session: AsyncSession, first_name: str, last_name: str) -> Trainer | None:
    result = await session.execute(
        select(Trainer)
        .where(Trainer.first_name == first_name, Trainer.last_name == last_name)
        .options(selectinload(Trainer.branches)),
    )
    return result.scalar_one_or_none()


async def _training_group_with_relations(session: AsyncSession, group_id: int) -> TrainingGroup:
    result = await session.execute(
        select(TrainingGroup)
        .where(TrainingGroup.id == group_id)
        .options(
            selectinload(TrainingGroup.students),
            selectinload(TrainingGroup.trainers),
        ),
    )
    return result.scalar_one()


async def seed_demo_students() -> None:
    """Idempotentně doplní výchozí děti pro demo tréninkové série."""
    async with async_session_maker() as session:
        async with session.begin():
            branch_rows = (await session.execute(select(Branch))).scalars().all()
            by_name = {b.name: b for b in branch_rows}
            for first_name, last_name, age_group, branch_name in DEFAULT_DEMO_STUDENTS:
                branch = by_name.get(branch_name)
                if branch is None:
                    continue
                result = await session.execute(
                    select(Student)
                    .where(Student.first_name == first_name, Student.last_name == last_name)
                    .options(selectinload(Student.branches)),
                )
                student = result.scalar_one_or_none()
                if student is None:
                    student = Student(
                        first_name=first_name,
                        last_name=last_name,
                        age_group=AgeGroup(age_group),
                    )
                    student.branches.append(branch)
                    session.add(student)
                else:
                    branch_ids = {b.id for b in student.branches}
                    if branch.id not in branch_ids:
                        student.branches.append(branch)
                    if student.age_group != AgeGroup(age_group):
                        student.age_group = AgeGroup(age_group)


async def seed_training_groups() -> None:
    """Idempotentně doplní dvě výchozí tréninkové série s dětmi a trenéry."""
    today = date.today()
    active_until = today + timedelta(days=365)
    async with async_session_maker() as session:
        async with session.begin():
            branch_rows = (await session.execute(select(Branch))).scalars().all()
            branches = {b.name: b for b in branch_rows}
            students_by_branch: dict[str, list[Student]] = {}
            for first_name, last_name, _age_group, branch_name in DEFAULT_DEMO_STUDENTS:
                result = await session.execute(
                    select(Student)
                    .where(Student.first_name == first_name, Student.last_name == last_name)
                    .options(selectinload(Student.branches)),
                )
                student = result.scalar_one_or_none()
                if student is not None:
                    students_by_branch.setdefault(branch_name, []).append(student)

            for (
                name,
                branch_name,
                start_time,
                end_time,
                weekdays,
                lead_trainer,
                co_trainers,
            ) in DEFAULT_TRAINING_GROUPS:
                branch = branches.get(branch_name)
                lead = await _trainer_by_name(session, lead_trainer[0], lead_trainer[1])
                if branch is None or lead is None:
                    continue
                if branch.id not in {b.id for b in lead.branches}:
                    continue

                result = await session.execute(
                    select(TrainingGroup)
                    .where(
                        TrainingGroup.branch_id == branch.id,
                        TrainingGroup.name == name,
                        TrainingGroup.start_time == start_time,
                        TrainingGroup.end_time == end_time,
                    )
                    .options(
                        selectinload(TrainingGroup.students),
                        selectinload(TrainingGroup.trainers),
                    ),
                )
                group = result.scalar_one_or_none()
                if group is None:
                    new_group = TrainingGroup(
                        branch_id=branch.id,
                        name=name,
                        start_time=start_time,
                        end_time=end_time,
                        weekdays=list(weekdays),
                        active_from=today,
                        active_until=active_until,
                    )
                    session.add(new_group)
                    await session.flush()
                    group = await _training_group_with_relations(session, new_group.id)

                group.weekdays = list(weekdays)
                group.active_from = today
                group.active_until = active_until

                roster = students_by_branch.get(branch_name, [])[:6]
                if roster:
                    group.students.clear()
                    group.students.extend(roster)

                trainer_ids = {lead.id}
                group_trainers = [lead]
                for co_first, co_last in co_trainers:
                    co = await _trainer_by_name(session, co_first, co_last)
                    if co is None or branch.id not in {b.id for b in co.branches}:
                        continue
                    if co.id not in trainer_ids:
                        trainer_ids.add(co.id)
                        group_trainers.append(co)
                group.trainers.clear()
                group.trainers.extend(group_trainers)


async def seed_default_event() -> None:
    """Idempotentně doplní výchozí klubovou akci."""
    title, event_type, location, days_ahead, start_time, author = DEFAULT_EVENT
    event_day = date.today() + timedelta(days=days_ahead)
    starts_at = datetime.combine(event_day, start_time, tzinfo=UTC)
    async with async_session_maker() as session:
        async with session.begin():
            author_trainer = await _trainer_by_name(session, author[0], author[1])
            if author_trainer is None:
                return

            result = await session.execute(
                select(Event)
                .where(Event.title == title)
                .options(selectinload(Event.targets)),
            )
            event = result.scalar_one_or_none()
            if event is None:
                event = Event(
                    title=title,
                    description="Klubový turnaj pro všechny kategorie. Sraz u hlavní haly.",
                    event_type=event_type,
                    location=location,
                    starts_at=starts_at,
                    author_trainer_id=author_trainer.id,
                )
                event.targets.extend([
                    EventTarget(audience=NotificationAudience.parent),
                    EventTarget(audience=NotificationAudience.trainer),
                ])
                session.add(event)
            else:
                event.event_type = event_type
                event.location = location
                event.starts_at = starts_at
                event.author_trainer_id = author_trainer.id
                if not event.targets:
                    event.targets.extend([
                        EventTarget(audience=NotificationAudience.parent),
                        EventTarget(audience=NotificationAudience.trainer),
                    ])


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
        if notification_columns and "event_id" not in notification_columns:
            await conn.execute(text("ALTER TABLE notifications ADD COLUMN event_id INTEGER REFERENCES events(id)"))
        if notification_columns and "training_group_id" not in notification_columns:
            await conn.execute(
                text("ALTER TABLE notifications ADD COLUMN training_group_id INTEGER REFERENCES training_groups(id)"),
            )
        if notification_columns and "training_date" not in notification_columns:
            await conn.execute(text("ALTER TABLE notifications ADD COLUMN training_date DATE"))
        if notification_columns and "author_parent_id" not in notification_columns:
            await conn.execute(
                text("ALTER TABLE notifications ADD COLUMN author_parent_id INTEGER REFERENCES parents(id)"),
            )

        result = await conn.execute(text("PRAGMA table_info(events)"))
        event_columns = {row[1] for row in result.fetchall()}
        if event_columns and "reminder_sent" not in event_columns:
            await conn.execute(text("ALTER TABLE events ADD COLUMN reminder_sent BOOLEAN DEFAULT 0"))

        result = await conn.execute(text("PRAGMA table_info(training_groups)"))
        group_columns = {row[1] for row in result.fetchall()}
        if group_columns and "active_from" not in group_columns:
            await conn.execute(text("ALTER TABLE training_groups ADD COLUMN active_from DATE"))
        if group_columns and "active_until" not in group_columns:
            await conn.execute(text("ALTER TABLE training_groups ADD COLUMN active_until DATE"))

        result = await conn.execute(text("PRAGMA table_info(training_sessions)"))
        session_columns = {row[1] for row in result.fetchall()}
        if session_columns and "canceled" not in session_columns:
            await conn.execute(text("ALTER TABLE training_sessions ADD COLUMN canceled BOOLEAN DEFAULT 0"))
        if session_columns and "end_time" not in session_columns:
            await conn.execute(text("ALTER TABLE training_sessions ADD COLUMN end_time TIME"))

        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS training_occurrence_comments ("
                "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                "training_group_id INTEGER NOT NULL REFERENCES training_groups(id) ON DELETE CASCADE, "
                "training_date DATE NOT NULL, "
                "author_trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL, "
                "author_parent_id INTEGER REFERENCES parents(id) ON DELETE SET NULL, "
                "body VARCHAR(4000) NOT NULL, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            ),
        )

        result = await conn.execute(text("PRAGMA table_info(notification_targets)"))
        target_columns = {row[1] for row in result.fetchall()}
        if target_columns and "branch_id" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN branch_id INTEGER"))
        if target_columns and "age_group" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN age_group VARCHAR(8)"))
        if target_columns and "parent_id" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN parent_id INTEGER"))
        if target_columns and "trainer_id" not in target_columns:
            await conn.execute(text("ALTER TABLE notification_targets ADD COLUMN trainer_id INTEGER"))

        result = await conn.execute(text("PRAGMA table_info(event_rsvps)"))
        rsvp_columns = {row[1] for row in result.fetchall()}
        if rsvp_columns and "student_id" not in rsvp_columns:
            # Rebuild to add student_id and swap the parent-uniqueness for student-uniqueness.
            # Old parent rows carry no child, so only trainer (self) rows are preserved.
            await conn.execute(text("ALTER TABLE event_rsvps RENAME TO event_rsvps_old"))
            await conn.execute(
                text(
                    "CREATE TABLE event_rsvps ("
                    "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                    "event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, "
                    "trainer_id INTEGER REFERENCES trainers(id) ON DELETE CASCADE, "
                    "parent_id INTEGER REFERENCES parents(id) ON DELETE CASCADE, "
                    "student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, "
                    "status VARCHAR(8) NOT NULL, "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "CONSTRAINT uq_event_rsvp_trainer UNIQUE (event_id, trainer_id), "
                    "CONSTRAINT uq_event_rsvp_student UNIQUE (event_id, student_id))",
                ),
            )
            await conn.execute(
                text(
                    "INSERT INTO event_rsvps "
                    "(id, event_id, trainer_id, parent_id, student_id, status, created_at, updated_at) "
                    "SELECT id, event_id, trainer_id, NULL, NULL, status, created_at, updated_at "
                    "FROM event_rsvps_old WHERE trainer_id IS NOT NULL",
                ),
            )
            await conn.execute(text("DROP TABLE event_rsvps_old"))

        result = await conn.execute(text("PRAGMA table_info(students)"))
        student_columns = {row[1] for row in result.fetchall()}
        if student_columns and "birth_date" not in student_columns:
            await conn.execute(text("ALTER TABLE students ADD COLUMN birth_date DATE"))
        if student_columns and "birth_number" not in student_columns:
            await conn.execute(text("ALTER TABLE students ADD COLUMN birth_number VARCHAR(11)"))
        if student_columns and "health_insurance" not in student_columns:
            await conn.execute(text("ALTER TABLE students ADD COLUMN health_insurance VARCHAR(100)"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_students_birth_number "
                "ON students(birth_number) WHERE birth_number IS NOT NULL",
            ),
        )

        result = await conn.execute(text("PRAGMA table_info(parents)"))
        parent_columns = {row[1] for row in result.fetchall()}
        if parent_columns and "username" not in parent_columns:
            await conn.execute(text("ALTER TABLE parents ADD COLUMN username VARCHAR(64)"))
        if parent_columns and "password_hash" not in parent_columns:
            await conn.execute(text("ALTER TABLE parents ADD COLUMN password_hash VARCHAR(128)"))
        if parent_columns and "password_plain" in parent_columns:
            await conn.execute(text("ALTER TABLE parents DROP COLUMN password_plain"))

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

        result = await conn.execute(text("PRAGMA table_info(chat_participants)"))
        chat_participant_columns = {row[1] for row in result.fetchall()}
        if chat_participant_columns and "hidden_at" not in chat_participant_columns:
            await conn.execute(text("ALTER TABLE chat_participants ADD COLUMN hidden_at DATETIME"))

        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS trainer_training_groups ("
                "trainer_id INTEGER NOT NULL REFERENCES trainers(id) ON DELETE CASCADE, "
                "group_id INTEGER NOT NULL REFERENCES training_groups(id) ON DELETE CASCADE, "
                "PRIMARY KEY (trainer_id, group_id))"
            ),
        )

        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS trainer_session_attendance ("
                "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                "session_id INTEGER NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE, "
                "trainer_id INTEGER NOT NULL REFERENCES trainers(id) ON DELETE CASCADE, "
                "status VARCHAR(16) NOT NULL, "
                "recorded_by_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "CONSTRAINT uq_trainer_attendance_session_trainer UNIQUE (session_id, trainer_id))"
            ),
        )

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

        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS registration_requests ("
                "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                "status VARCHAR(16) NOT NULL DEFAULT 'pending', "
                "parent_email VARCHAR(320) NOT NULL, "
                "payload_json JSON NOT NULL, "
                "rejection_reason VARCHAR(1000), "
                "approved_parent_id INTEGER REFERENCES parents(id), "
                "reviewed_at DATETIME, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")",
            ),
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_registration_requests_parent_email "
                "ON registration_requests (parent_email)",
            ),
        )

        from app.student_delete import cleanup_students_without_branches

        await cleanup_students_without_branches(conn)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema()
    await seed_branches()
    await seed_trainers()
    await seed_trainer_pins()
    await seed_demo_students()
    await seed_training_groups()
    await seed_default_event()
