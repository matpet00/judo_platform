import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AgeGroup(str, enum.Enum):
    U8 = "U8"
    U10 = "U10"
    U12 = "U12"
    U14 = "U14"
    U16 = "U16"
    U18 = "U18"


class BranchName(str, enum.Enum):
    """Názvy poboček v DB i v API (musí sedět s DEFAULT_BRANCHES)."""

    ORLOVA = "Orlova"
    DOLNI_LUTYNE = "Dolni Lutyne"
    PETRVALD = "Petrvald"


# (název v API/DB, fiktivní adresa pro vývoj)
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


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(String(512))

    trainers: Mapped[list["Trainer"]] = relationship(back_populates="branch")
    students: Mapped[list["Student"]] = relationship(back_populates="branch")


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))

    branch: Mapped[Branch] = relationship(back_populates="trainers")


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    phone: Mapped[str] = mapped_column(String(32))

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
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))

    branch: Mapped[Branch] = relationship(back_populates="students")
    parents: Mapped[list[Parent]] = relationship(
        secondary=student_parents,
        back_populates="children",
    )
