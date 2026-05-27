import enum
from datetime import datetime, time

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Table, Time, UniqueConstraint, func
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


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    phone: Mapped[str] = mapped_column(String(32))
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
