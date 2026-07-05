import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AgeGroup(str, enum.Enum):
    U8 = "U8"
    U10 = "U10"
    U12 = "U12"
    U14 = "U14"
    U16 = "U16"
    U18 = "U18"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    excused = "excused"


class NotificationAudience(str, enum.Enum):
    trainer = "trainer"
    parent = "parent"


class EventType(str, enum.Enum):
    tournament = "tournament"
    training = "training"
    meeting = "meeting"
    seminar = "seminar"
    other = "other"


class RsvpStatus(str, enum.Enum):
    yes = "yes"
    no = "no"
    maybe = "maybe"


# (název v API/DB, fiktivní adresa pro vývoj — seed při startu)
DEFAULT_BRANCHES: tuple[tuple[str, str], ...] = (
    ("Orlova", "Hlavní třída 1285/45, 735 14 Orlová"),
    ("Dolni Lutyne", "Komenského 312, 735 71 Dolní Lutyně"),
    ("Petrvald", "Nádražní 201, 735 81 Petřvald"),
)


class Base(DeclarativeBase):
    pass


student_parents = Table(
    "student_parents",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("parent_id", Integer, ForeignKey("parents.id", ondelete="CASCADE"), primary_key=True),
)

student_branches = Table(
    "student_branches",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("branch_id", Integer, ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True),
)

trainer_branches = Table(
    "trainer_branches",
    Base.metadata,
    Column("trainer_id", Integer, ForeignKey("trainers.id", ondelete="CASCADE"), primary_key=True),
    Column("branch_id", Integer, ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True),
)

student_training_groups = Table(
    "student_training_groups",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("training_groups.id", ondelete="CASCADE"), primary_key=True),
)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    trainers: Mapped[list["Trainer"]] = relationship(
        secondary=trainer_branches,
        back_populates="branches",
    )
    students: Mapped[list["Student"]] = relationship(
        secondary=student_branches,
        back_populates="branches",
    )
    training_sessions: Mapped[list["TrainingSession"]] = relationship(back_populates="branch")
    training_groups: Mapped[list["TrainingGroup"]] = relationship(back_populates="branch")


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    pin_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    branches: Mapped[list[Branch]] = relationship(
        secondary=trainer_branches,
        back_populates="trainers",
    )
    training_sessions: Mapped[list["TrainingSession"]] = relationship(back_populates="trainer")
    recorded_attendance: Mapped[list["AttendanceRecord"]] = relationship(back_populates="recorded_by")
    authored_notifications: Mapped[list["Notification"]] = relationship(back_populates="author_trainer")


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    phone: Mapped[str] = mapped_column(String(32))
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    children: Mapped[list["Student"]] = relationship(
        secondary=student_parents,
        back_populates="parents",
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    age_group: Mapped[AgeGroup] = mapped_column(
        Enum(AgeGroup, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=8),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    branches: Mapped[list[Branch]] = relationship(
        secondary=student_branches,
        back_populates="students",
    )
    parents: Mapped[list[Parent]] = relationship(
        secondary=student_parents,
        back_populates="children",
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="student")
    training_groups: Mapped[list["TrainingGroup"]] = relationship(
        secondary=student_training_groups,
        back_populates="students",
    )


class TrainingGroup(Base):
    __tablename__ = "training_groups"
    __table_args__ = (
        UniqueConstraint("branch_id", "start_time", "end_time", "name", name="uq_training_group_branch_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    weekdays: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    # Optional window bounding recurring occurrences ("repeat from/until").
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    branch: Mapped[Branch] = relationship(back_populates="training_groups")
    students: Mapped[list[Student]] = relationship(
        secondary=student_training_groups,
        back_populates="training_groups",
    )
    training_sessions: Mapped[list["TrainingSession"]] = relationship(back_populates="training_group")


class TrainingSession(Base):
    __tablename__ = "training_sessions"
    __table_args__ = (
        UniqueConstraint("training_group_id", "starts_at", name="uq_training_session_group_starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    training_group_id: Mapped[int] = mapped_column(ForeignKey("training_groups.id", ondelete="CASCADE"))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    canceled: Mapped[bool] = mapped_column(Boolean, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    branch: Mapped[Branch] = relationship(back_populates="training_sessions")
    training_group: Mapped[TrainingGroup | None] = relationship(back_populates="training_sessions")
    trainer: Mapped[Trainer | None] = relationship(back_populates="training_sessions")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(4000))
    author_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    visible_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    grace_seconds: Mapped[int] = mapped_column(Integer, server_default="0")
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    author_trainer: Mapped[Trainer | None] = relationship(back_populates="authored_notifications")
    targets: Mapped[list["NotificationTarget"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["NotificationComment"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
    )
    reads: Mapped[list["NotificationReadReceipt"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationTarget(Base):
    __tablename__ = "notification_targets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"))
    audience: Mapped[NotificationAudience] = mapped_column(
        Enum(NotificationAudience, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=16),
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    age_group: Mapped[AgeGroup | None] = mapped_column(
        Enum(AgeGroup, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=8),
        nullable=True,
    )
    # Direct personal targets: when set, the notification is visible only to this parent/trainer.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=True)
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="CASCADE"), nullable=True)

    notification: Mapped[Notification] = relationship(back_populates="targets")
    branch: Mapped[Branch | None] = relationship()


class NotificationComment(Base):
    __tablename__ = "notification_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"))
    author_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    author_parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    notification: Mapped[Notification] = relationship(back_populates="comments")
    author_trainer: Mapped[Trainer | None] = relationship()
    author_parent: Mapped[Parent | None] = relationship()


class NotificationReadReceipt(Base):
    __tablename__ = "notification_reads"
    __table_args__ = (
        UniqueConstraint("notification_id", "trainer_id", name="uq_notification_read_trainer"),
        UniqueConstraint("notification_id", "parent_id", name="uq_notification_read_parent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="CASCADE"), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    notification: Mapped[Notification] = relationship(back_populates="reads")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=16),
    )
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped[TrainingSession] = relationship(back_populates="attendance_records")
    student: Mapped[Student] = relationship(back_populates="attendance_records")
    recorded_by: Mapped[Trainer | None] = relationship(back_populates="recorded_attendance")


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    is_group: Mapped[bool] = mapped_column(Boolean, server_default="0")
    # Canonical key for 1-1 conversations, e.g. "parent:31|trainer:1"; NULL for groups.
    dm_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    participants: Mapped[list["ChatParticipant"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    __table_args__ = (
        UniqueConstraint("conversation_id", "trainer_id", name="uq_chat_participant_trainer"),
        UniqueConstraint("conversation_id", "parent_id", name="uq_chat_participant_parent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("chat_conversations.id", ondelete="CASCADE"))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="CASCADE"), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-user soft delete: conversation hidden from this participant's list until new activity.
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[ChatConversation] = relationship(back_populates="participants")
    trainer: Mapped[Trainer | None] = relationship()
    parent: Mapped[Parent | None] = relationship()


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("chat_conversations.id", ondelete="CASCADE"))
    sender_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    sender_parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")
    sender_trainer: Mapped[Trainer | None] = relationship()
    sender_parent: Mapped[Parent | None] = relationship()


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(4000), server_default="")
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=16),
    )
    location: Mapped[str] = mapped_column(String(512), server_default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    # Guards the pre-event reminder sweep so each event only fires reminders once.
    reminder_sent: Mapped[bool] = mapped_column(Boolean, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    author_trainer: Mapped[Trainer | None] = relationship()
    targets: Mapped[list["EventTarget"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["EventComment"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["EventAttachment"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    rsvps: Mapped[list["EventRsvp"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )


class EventTarget(Base):
    __tablename__ = "event_targets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    audience: Mapped[NotificationAudience] = mapped_column(
        Enum(NotificationAudience, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=16),
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    age_group: Mapped[AgeGroup | None] = mapped_column(
        Enum(AgeGroup, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=8),
        nullable=True,
    )

    event: Mapped[Event] = relationship(back_populates="targets")
    branch: Mapped[Branch | None] = relationship()


class EventComment(Base):
    __tablename__ = "event_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    author_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    author_parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    event: Mapped[Event] = relationship(back_populates="comments")
    author_trainer: Mapped[Trainer | None] = relationship()
    author_parent: Mapped[Parent | None] = relationship()


class EventAttachment(Base):
    __tablename__ = "event_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), server_default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, server_default="0")
    stored_name: Mapped[str] = mapped_column(String(128))
    uploaded_trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True)
    uploaded_parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[Event] = relationship(back_populates="attachments")


class EventRsvp(Base):
    __tablename__ = "event_rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "trainer_id", name="uq_event_rsvp_trainer"),
        UniqueConstraint("event_id", "student_id", name="uq_event_rsvp_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id", ondelete="CASCADE"), nullable=True)
    # For parent RSVPs: parent_id is the submitter, student_id is the child the response is for.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[RsvpStatus] = mapped_column(
        Enum(RsvpStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False, length=8),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    event: Mapped[Event] = relationship(back_populates="rsvps")
    trainer: Mapped[Trainer | None] = relationship()
    parent: Mapped[Parent | None] = relationship()
    student: Mapped["Student | None"] = relationship()
