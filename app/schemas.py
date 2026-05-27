from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import DEFAULT_BRANCHES, AgeGroup, AttendanceStatus

_EX_BRANCH_NAME, _EX_BRANCH_ADDR = DEFAULT_BRANCHES[0]


class BranchRead(BaseModel):
    id: int = Field(examples=[1])
    name: str = Field(examples=[_EX_BRANCH_NAME])
    address: str = Field(examples=[_EX_BRANCH_ADDR])
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudentBrief(BaseModel):
    """Žák bez pobočky a rodičů — pro výpis pod pobočkou (bez cyklů v JSON)."""

    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Pepa"])
    last_name: str = Field(examples=["Zelený"])
    age_group: AgeGroup = Field(examples=[AgeGroup.U10])

    model_config = {"from_attributes": True}


class TrainerBrief(BaseModel):
    """Trenér bez pobočky — pro výpis pod pobočkou."""

    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Jirka"])
    last_name: str = Field(examples=["Trenér"])

    model_config = {"from_attributes": True}


class BranchDetailRead(BaseModel):
    id: int = Field(examples=[1])
    name: str = Field(examples=[_EX_BRANCH_NAME])
    address: str = Field(examples=[_EX_BRANCH_ADDR])
    created_at: datetime
    updated_at: datetime
    students: list[StudentBrief]
    trainers: list[TrainerBrief]

    model_config = {"from_attributes": True}


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=1, max_length=512)

    @field_validator("name", "address", mode="before")
    @classmethod
    def strip_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class BranchPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=64)
    address: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("name", "address", mode="before")
    @classmethod
    def strip_optional(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class TrainerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    branch_ids: list[int] = Field(min_length=1, description="Jedna nebo více poboček (M:N).")

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_trainer_branch_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class TrainerRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Jirka"])
    last_name: str = Field(examples=["Trenér"])
    created_at: datetime
    updated_at: datetime
    branches: list[BranchRead]

    model_config = {"from_attributes": True}


class TrainerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    branch_ids: list[int] | None = Field(default=None, min_length=1)

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_trainer_branch_ids_patch(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class ParentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=1, max_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_parent_create_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def strip_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class ParentRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Marie"])
    last_name: str = Field(examples=["Nováková"])
    email: EmailStr = Field(examples=["marie.novakova@example.com"])
    phone: str = Field(examples=["+420601234567"])
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_optional_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def strip_optional_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class StudentParentInput(BaseModel):
    """Rodič u žáka — podle e-mailu (existující nebo nový záznam). Bez ID."""

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def strip_student_parent_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    age_group: AgeGroup
    branch_ids: list[int] = Field(min_length=1, description="Jedna nebo více poboček (M:N).")
    parents: list[StudentParentInput] = Field(default_factory=list, max_length=2)

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_branch_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class StudentRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Pepa"])
    last_name: str = Field(examples=["Zelený"])
    age_group: AgeGroup = Field(examples=[AgeGroup.U10])
    created_at: datetime
    updated_at: datetime
    branches: list[BranchRead]
    parents: list[ParentRead]

    model_config = {"from_attributes": True}


class StudentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    age_group: AgeGroup | None = None
    branch_ids: list[int] | None = Field(default=None, min_length=1)
    parents: list[StudentParentInput] | None = Field(default=None, max_length=2)

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_branch_ids_patch(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class MailToParentsRequest(BaseModel):
    parent_ids: list[int] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1)


class MailToParentsResponse(BaseModel):
    sent_to: list[EmailStr] = Field(examples=[["marie.novakova@example.com"]])
    message: str = Field(default="ok", examples=["ok"])


class TrainingSessionCreate(BaseModel):
    branch_id: int = Field(ge=1)
    trainer_id: int | None = Field(default=None, ge=1)
    starts_at: datetime
    age_group: AgeGroup | None = None
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class TrainingSessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int | None = Field(default=None, ge=1)
    trainer_id: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    age_group: AgeGroup | None = None
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_optional_notes(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class TrainingSessionRead(BaseModel):
    id: int = Field(examples=[1])
    branch_id: int = Field(examples=[1])
    trainer_id: int | None = Field(examples=[1])
    starts_at: datetime
    age_group: AgeGroup | None = Field(examples=[AgeGroup.U10])
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    branch: BranchRead
    trainer: TrainerBrief | None = None

    model_config = {"from_attributes": True}


class AttendanceRecordCreate(BaseModel):
    student_id: int = Field(ge=1)
    status: AttendanceStatus = Field(examples=[AttendanceStatus.present])
    recorded_by_id: int | None = Field(default=None, ge=1)


class AttendanceRecordPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AttendanceStatus | None = None
    recorded_by_id: int | None = Field(default=None, ge=1)


class AttendanceRecordRead(BaseModel):
    id: int = Field(examples=[1])
    session_id: int = Field(examples=[1])
    student_id: int = Field(examples=[1])
    status: AttendanceStatus = Field(examples=[AttendanceStatus.present])
    recorded_by_id: int | None = None
    created_at: datetime
    updated_at: datetime
    student: StudentBrief
    recorded_by: TrainerBrief | None = None

    model_config = {"from_attributes": True}


class TrainingSessionDetailRead(TrainingSessionRead):
    attendance_records: list[AttendanceRecordRead] = Field(default_factory=list)


class AttendanceRecordWithSessionRead(AttendanceRecordRead):
    session: TrainingSessionRead
