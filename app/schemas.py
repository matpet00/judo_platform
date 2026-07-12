from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import (
    DEFAULT_BRANCHES,
    AgeGroup,
    AttendanceStatus,
    EventType,
    NotificationAudience,
    RsvpStatus,
)
from app.phone import validate_e164_phone
from app.birth_number import validate_birth_number

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
    pin: str | None = Field(default=None, min_length=4, max_length=8)

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


class TrainerPinVerify(BaseModel):
    pin: str = Field(min_length=4, max_length=8)


class TrainerPinChange(BaseModel):
    current_pin: str = Field(min_length=4, max_length=8)
    new_pin: str = Field(min_length=6, max_length=8)


class TrainerAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    trainer_id: int
    pin_change_required: bool = False


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
    def normalize_parent_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return validate_e164_phone(v)
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


class TrainerStudentRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    age_group: AgeGroup
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = None
    branches: list[BranchRead]
    parents: list[ParentRead]
    training_groups: list[str]
    is_guest: bool = False
    home_branch: str | None = None


class ParentLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class ParentPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class ParentAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    parent_id: int


class ParentChildRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    age_group: AgeGroup
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = None
    branches: list[BranchRead]

    model_config = {"from_attributes": True}


class ParentChildPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = Field(default=None, max_length=100)

    @field_validator("birth_number", mode="before")
    @classmethod
    def normalize_birth_number_patch(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return validate_birth_number(v)
        return v

    @field_validator("health_insurance", mode="before")
    @classmethod
    def normalize_health_insurance_patch(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return v.strip()
        return v


class ParentSelf(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    username: str | None = None
    children: list[ParentChildRead]

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
    def normalize_optional_parent_phone(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            return validate_e164_phone(v)
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
    def normalize_student_parent_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return validate_e164_phone(v)
        return v


class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    age_group: AgeGroup
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = Field(default=None, max_length=100)
    branch_ids: list[int] = Field(min_length=1, description="Jedna nebo více poboček (M:N).")
    parents: list[StudentParentInput] = Field(default_factory=list, max_length=2)

    @field_validator("birth_number", mode="before")
    @classmethod
    def normalize_birth_number_create(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return validate_birth_number(v)
        return v

    @field_validator("health_insurance", mode="before")
    @classmethod
    def normalize_health_insurance_create(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_branch_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class ChildRegistrationInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: date
    birth_number: str = Field(min_length=10, max_length=11)
    health_insurance: str = Field(min_length=1, max_length=100)
    branch_ids: list[int] = Field(min_length=1)

    @field_validator("birth_number", mode="before")
    @classmethod
    def normalize_child_birth_number(cls, v: object) -> object:
        if isinstance(v, str):
            return validate_birth_number(v)
        return v

    @field_validator("health_insurance", mode="before")
    @classmethod
    def normalize_child_health_insurance(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("branch_ids", mode="after")
    @classmethod
    def unique_branch_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate branch_ids are not allowed.")
        if any(bid < 1 for bid in v):
            raise ValueError("branch_ids must be >= 1.")
        return v


class ClubRegistrationCreate(BaseModel):
    """Registrace rodiče a jednoho či více dětí do klubu."""

    parent_first_name: str = Field(min_length=1, max_length=100)
    parent_last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=1, max_length=32)
    second_guardian: StudentParentInput | None = None
    children: list[ChildRegistrationInput] = Field(min_length=1, max_length=5)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_registration_phone(cls, v: object) -> object:
        if isinstance(v, str):
            return validate_e164_phone(v)
        return v

    @model_validator(mode="after")
    def validate_guardians(self) -> "ClubRegistrationCreate":
        if self.second_guardian is not None:
            primary = str(self.email).strip().lower()
            secondary = str(self.second_guardian.email).strip().lower()
            if primary == secondary:
                raise ValueError("E-mail druhého zástupce musí být jiný než u prvního.")
        return self


class AgeGroupPreview(BaseModel):
    birth_date: date
    reference_year: int
    age_at_year_end: int
    age_group: AgeGroup


class StudentRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Pepa"])
    last_name: str = Field(examples=["Zelený"])
    age_group: AgeGroup = Field(examples=[AgeGroup.U10])
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = None
    created_at: datetime
    updated_at: datetime
    branches: list[BranchRead]
    parents: list[ParentRead]

    model_config = {"from_attributes": True}


class GuardianCredentialsRead(BaseModel):
    parent_id: int
    first_name: str
    last_name: str
    email: str
    username: str
    credentials_created: bool = False
    credentials_email_sent: bool = False
    credentials_email_error: str | None = None


class ClubRegistrationRead(BaseModel):
    parent_id: int
    students: list[StudentRead]
    existing_parent: bool
    username: str | None = None
    credentials_created: bool = False
    credentials_email_sent: bool = False
    credentials_email_error: str | None = None
    second_guardian: GuardianCredentialsRead | None = None
    access_token: str | None = None
    token_type: str | None = None
    expires_at: datetime | None = None
    parent_id_token: int | None = None
    message: str | None = None


class ParentEmailStatus(BaseModel):
    exists: bool
    has_login: bool = False


class BirthNumberStatus(BaseModel):
    available: bool


class RegistrationStatusQuery(BaseModel):
    email: EmailStr


class RegistrationSubmittedRead(BaseModel):
    request_id: int
    message: str
    confirmation_email_sent: bool = False
    confirmation_email_error: str | None = None


class RegistrationStatusRead(BaseModel):
    status: str = Field(description="pending | rejected | unavailable")
    message: str
    rejection_reason: str | None = None
    request_id: int | None = None
    reviewed_at: datetime | None = None


class RegistrationRejectBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class RegistrationRequestChildRead(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    birth_number: str
    health_insurance: str
    branch_names: list[str]
    age_group: AgeGroup


class RegistrationRequestListItem(BaseModel):
    id: int
    status: str
    parent_first_name: str
    parent_last_name: str
    parent_email: str
    parent_phone: str
    children_count: int
    has_second_guardian: bool
    created_at: datetime
    reviewed_at: datetime | None = None


class RegistrationRequestDetail(RegistrationRequestListItem):
    children: list[RegistrationRequestChildRead]
    second_guardian: StudentParentInput | None = None
    rejection_reason: str | None = None
    approved_parent_id: int | None = None


class StudentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    age_group: AgeGroup | None = None
    birth_date: date | None = None
    birth_number: str | None = None
    health_insurance: str | None = Field(default=None, max_length=100)
    branch_ids: list[int] | None = Field(default=None, min_length=1)
    parents: list[StudentParentInput] | None = Field(default=None, max_length=2)

    @field_validator("birth_number", mode="before")
    @classmethod
    def normalize_birth_number_patch(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return validate_birth_number(v)
        return v

    @field_validator("health_insurance", mode="before")
    @classmethod
    def normalize_health_insurance_patch(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return v.strip()
        return v

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


class TrainingGroupCreate(BaseModel):
    branch_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=128)
    start_time: time
    end_time: time
    weekdays: list[int] | None = Field(default=None, description="ISO weekday 1=Mon … 7=Sun")
    active_from: date | None = Field(default=None, description="Opakovat od (včetně); None = bez omezení.")
    active_until: date | None = Field(default=None, description="Opakovat do (včetně); None = bez omezení.")
    student_ids: list[int] = Field(default_factory=list, description="Zapsané děti (roster).")
    trainer_ids: list[int] = Field(default_factory=list, description="Stálí trenéři skupiny (kromě tvůrce).")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("weekdays", mode="after")
    @classmethod
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(set(v)) != len(v):
            raise ValueError("Duplicate weekdays are not allowed.")
        for day in v:
            if day < 1 or day > 7:
                raise ValueError("weekdays must be integers 1–7 (ISO, Monday=1).")
        return sorted(v)

    @field_validator("student_ids", mode="after")
    @classmethod
    def unique_group_student_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate student_ids are not allowed.")
        if any(sid < 1 for sid in v):
            raise ValueError("student_ids must be >= 1.")
        return v

    @field_validator("trainer_ids", mode="after")
    @classmethod
    def unique_group_trainer_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate trainer_ids are not allowed.")
        if any(tid < 1 for tid in v):
            raise ValueError("trainer_ids must be >= 1.")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time must be after start_time.")
        return v

    @model_validator(mode="after")
    def validate_active_window(self) -> "TrainingGroupCreate":
        if self.active_from is not None and self.active_until is not None and self.active_until < self.active_from:
            raise ValueError("active_until must be on or after active_from.")
        if self.weekdays and not self.student_ids:
            raise ValueError("Recurring training groups require at least one student.")
        return self


class TrainingGroupPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    start_time: time | None = None
    end_time: time | None = None
    weekdays: list[int] | None = None
    active_from: date | None = None
    active_until: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_optional_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("weekdays", mode="after")
    @classmethod
    def validate_weekdays_patch(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(set(v)) != len(v):
            raise ValueError("Duplicate weekdays are not allowed.")
        for day in v:
            if day < 1 or day > 7:
                raise ValueError("weekdays must be integers 1–7 (ISO, Monday=1).")
        return sorted(v)


class TrainingGroupRead(BaseModel):
    id: int = Field(examples=[1])
    branch_id: int = Field(examples=[1])
    name: str = Field(examples=["Orlova 16:00–17:30"])
    start_time: time
    end_time: time
    weekdays: list[int] | None = Field(examples=[[1, 3]])
    active_from: date | None = None
    active_until: date | None = None
    created_at: datetime
    updated_at: datetime
    branch: BranchRead

    model_config = {"from_attributes": True}


class TrainingGroupDetailRead(TrainingGroupRead):
    students: list[StudentBrief] = Field(default_factory=list)
    trainers: list[TrainerBrief] = Field(default_factory=list)


class TrainingGroupBrief(BaseModel):
    id: int = Field(examples=[1])
    branch_id: int = Field(examples=[1])
    name: str = Field(examples=["Orlova 16:00–17:30"])
    start_time: time
    end_time: time
    weekdays: list[int] | None = None

    model_config = {"from_attributes": True}


class TrainingGroupStudentsReplace(BaseModel):
    student_ids: list[int] = Field(default_factory=list)

    @field_validator("student_ids", mode="after")
    @classmethod
    def unique_student_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate student_ids are not allowed.")
        if any(sid < 1 for sid in v):
            raise ValueError("student_ids must be >= 1.")
        return v


class TrainingGroupTrainersReplace(BaseModel):
    trainer_ids: list[int] = Field(default_factory=list)

    @field_validator("trainer_ids", mode="after")
    @classmethod
    def unique_trainer_ids(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate trainer_ids are not allowed.")
        if any(tid < 1 for tid in v):
            raise ValueError("trainer_ids must be >= 1.")
        return v


class TrainingSessionCreate(BaseModel):
    training_group_id: int = Field(ge=1)
    session_date: date
    trainer_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class TrainingGroupSessionCreate(BaseModel):
    session_date: date
    trainer_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_group_session_notes(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class TrainingOccurrenceSchedulePatch(BaseModel):
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_slot(self) -> "TrainingOccurrenceSchedulePatch":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class TrainingSessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_group_id: int | None = Field(default=None, ge=1)
    session_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    trainer_id: int | None = Field(default=None, ge=1)
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
    training_group_id: int = Field(examples=[1])
    trainer_id: int | None = Field(examples=[1])
    starts_at: datetime
    end_time: time | None = None
    notes: str | None = None
    canceled: bool = False
    created_at: datetime
    updated_at: datetime
    branch: BranchRead
    training_group: TrainingGroupBrief
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


class AttendanceSummary(BaseModel):
    id: int
    status: AttendanceStatus
    recorded_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SessionStudentWithAttendance(BaseModel):
    id: int
    first_name: str
    last_name: str
    age_group: AgeGroup
    attendance: AttendanceSummary | None = None
    # True for children marked on this session who are not on the group's standing roster
    # (e.g. a child from another branch dropping in as a guest).
    is_guest: bool = False
    home_branch: str | None = None


class SessionTrainerWithAttendance(BaseModel):
    id: int
    first_name: str
    last_name: str
    attendance: AttendanceSummary | None = None
    branches: str | None = None
    is_guest: bool = False


class TrainerAttendanceRecordCreate(BaseModel):
    trainer_id: int = Field(ge=1)
    status: AttendanceStatus
    recorded_by_id: int | None = Field(default=None, ge=1)


class TrainerAttendanceRecordPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AttendanceStatus | None = None
    recorded_by_id: int | None = Field(default=None, ge=1)


class TrainerAttendanceRecordRead(BaseModel):
    id: int
    session_id: int
    trainer_id: int
    status: AttendanceStatus
    recorded_by_id: int | None = None
    created_at: datetime
    updated_at: datetime
    trainer: TrainerBrief
    recorded_by: TrainerBrief | None = None

    model_config = {"from_attributes": True}


class AttendanceBulkItem(BaseModel):
    student_id: int = Field(ge=1)
    status: AttendanceStatus
    recorded_by_id: int | None = Field(default=None, ge=1)


class AttendanceBulkReplace(BaseModel):
    records: list[AttendanceBulkItem] = Field(min_length=1)

    @field_validator("records", mode="after")
    @classmethod
    def unique_student_ids(cls, v: list[AttendanceBulkItem]) -> list[AttendanceBulkItem]:
        ids = [item.student_id for item in v]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate student_id in records.")
        return v


class TrainingSessionDetailRead(TrainingSessionRead):
    students: list[SessionStudentWithAttendance] = Field(default_factory=list)
    trainers: list[SessionTrainerWithAttendance] = Field(default_factory=list)
    attendance_records: list[AttendanceRecordRead] = Field(default_factory=list)


class AttendanceRecordWithSessionRead(AttendanceRecordRead):
    session: TrainingSessionRead


class TrainingOccurrence(BaseModel):
    group_id: int
    name: str
    branch_id: int
    date: date
    start_time: time
    end_time: time
    session_id: int | None = None
    canceled: bool = False
    roster_count: int = 0
    marked_count: int = 0
    guest_count: int = 0


class AttendanceMonthlyReportRow(BaseModel):
    student_id: int
    name: str
    present: int = 0
    absent: int = 0
    excused: int = 0
    sessions: int = 0
    is_guest: bool = False


class AttendanceMonthlyReport(BaseModel):
    group_id: int | None = None
    branch_id: int | None = None
    month: str = Field(examples=["2026-07"])
    sessions: int = 0
    group_count: int = 0
    rows: list[AttendanceMonthlyReportRow] = Field(default_factory=list)


class NotificationTargetCreate(BaseModel):
    audience: NotificationAudience
    branch_id: int | None = Field(default=None, ge=1, description="Konkrétní pobočka; None = všechny pobočky.")
    age_group: AgeGroup | None = Field(
        default=None,
        description="Jen pro rodiče: konkrétní kategorie; None = všechny kategorie.",
    )
    parent_id: int | None = Field(default=None, ge=1, description="Přímý osobní příjemce (rodič).")
    trainer_id: int | None = Field(default=None, ge=1, description="Přímý osobní příjemce (trenér).")

    @model_validator(mode="after")
    def validate_age_group(self) -> "NotificationTargetCreate":
        if self.age_group is not None and self.audience != NotificationAudience.parent:
            raise ValueError("age_group can only be set for parent targets.")
        return self


class NotificationDurationUnit(str):
    seconds = "seconds"
    minutes = "minutes"
    hours = "hours"
    days = "days"
    weeks = "weeks"
    months = "months"


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=4000)
    targets: list[NotificationTargetCreate] = Field(default_factory=list)
    visible_until: datetime | None = None
    duration_amount: int | None = Field(default=None, ge=1)
    duration_unit: str | None = Field(default=None, pattern="^(seconds|minutes|hours|days|weeks|months)$")
    keep_after_expiry: bool = False
    grace_amount: int | None = Field(default=None, ge=1)
    grace_unit: str | None = Field(default=None, pattern="^(seconds|minutes|hours|days|weeks|months)$")

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_notification_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def require_any_target(self) -> "NotificationCreate":
        if not self.targets:
            raise ValueError("Notification needs at least one target.")
        has_duration = self.duration_amount is not None or self.duration_unit is not None
        if self.visible_until is not None and has_duration:
            raise ValueError("Use either visible_until or duration_amount/duration_unit, not both.")
        if (self.duration_amount is None) != (self.duration_unit is None):
            raise ValueError("duration_amount and duration_unit must be provided together.")
        if (self.grace_amount is None) != (self.grace_unit is None):
            raise ValueError("grace_amount and grace_unit must be provided together.")
        if self.keep_after_expiry and self.grace_amount is None:
            raise ValueError("grace_amount and grace_unit are required when keep_after_expiry is true.")
        return self


class ParentNotificationCreate(BaseModel):
    """Rodič píše trenérům – buď všem, nebo trenérům konkrétní pobočky."""

    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=4000)
    branch_id: int | None = Field(default=None, ge=1, description="Konkrétní pobočka; None = všichni trenéři.")

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_parent_notification_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class NotificationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    body: str | None = Field(default=None, min_length=1, max_length=4000)

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_notification_patch_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def require_any_field(self) -> "NotificationPatch":
        if self.title is None and self.body is None:
            raise ValueError("Provide title or body to update.")
        return self


class NotificationTargetRead(BaseModel):
    id: int
    audience: NotificationAudience
    branch_id: int | None = None
    age_group: AgeGroup | None = None
    parent_id: int | None = None
    trainer_id: int | None = None

    model_config = {"from_attributes": True}


class NotificationCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_comment_body(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class ParentBrief(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Marie"])
    last_name: str = Field(examples=["Nováková"])

    model_config = {"from_attributes": True}


class TrainingOccurrenceCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_training_comment_body(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class TrainingOccurrenceCommentRead(BaseModel):
    id: int
    training_group_id: int
    training_date: date
    author_trainer_id: int | None = None
    author_parent_id: int | None = None
    body: str
    created_at: datetime
    updated_at: datetime
    author_trainer: TrainerBrief | None = None
    author_parent: ParentBrief | None = None
    can_delete: bool = False
    can_edit: bool = False


class NotificationCommentRead(BaseModel):
    id: int
    notification_id: int
    author_trainer_id: int | None = None
    author_parent_id: int | None = None
    body: str
    created_at: datetime
    updated_at: datetime
    author_trainer: TrainerBrief | None = None
    author_parent: ParentBrief | None = None
    can_delete: bool = False
    can_edit: bool = False

    model_config = {"from_attributes": True}


ChatParticipantKind = Literal["trainer", "parent"]


class ChatContact(BaseModel):
    kind: ChatParticipantKind
    id: int
    name: str
    subtitle: str | None = None


class ChatParticipantBrief(BaseModel):
    kind: ChatParticipantKind
    id: int
    name: str


class ChatMessageRead(BaseModel):
    id: int
    conversation_id: int
    sender_kind: ChatParticipantKind | None = None
    sender_id: int | None = None
    sender_name: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class ChatConversationRead(BaseModel):
    id: int
    is_group: bool = False
    counterpart: ChatParticipantBrief | None = None
    last_message: ChatMessageRead | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    created_at: datetime


class ChatMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_message_body(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class StartConversation(BaseModel):
    counterpart_kind: ChatParticipantKind
    counterpart_id: int = Field(ge=1)


class NotificationRead(BaseModel):
    id: int
    title: str
    body: str
    author_trainer_id: int | None = None
    author_parent_id: int | None = None
    event_id: int | None = None
    training_group_id: int | None = None
    training_date: date | None = None
    visible_until: datetime
    hide_after: datetime
    visibility_state: str
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime
    author_trainer: TrainerBrief | None = None
    author_parent: ParentBrief | None = None
    targets: list[NotificationTargetRead] = Field(default_factory=list)
    can_delete: bool = False
    can_edit: bool = False
    unread: bool = True
    has_read: bool = False
    comment_count: int = 0
    last_comment_author: str | None = None
    last_comment_preview: str | None = None


class EventTargetCreate(NotificationTargetCreate):
    pass


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    event_type: EventType = Field(examples=[EventType.tournament])
    location: str = Field(default="", max_length=512)
    starts_at: datetime
    ends_at: datetime | None = None
    targets: list[EventTargetCreate] = Field(default_factory=list)

    @field_validator("title", "description", "location", mode="before")
    @classmethod
    def strip_event_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_event(self) -> "EventCreate":
        if not self.targets:
            raise ValueError("Event needs at least one target.")
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be at or after starts_at.")
        return self


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    event_type: EventType | None = None
    location: str | None = Field(default=None, max_length=512)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    targets: list[EventTargetCreate] | None = None

    @field_validator("title", "description", "location", mode="before")
    @classmethod
    def strip_event_patch_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class EventTargetRead(BaseModel):
    id: int
    audience: NotificationAudience
    branch_id: int | None = None
    age_group: AgeGroup | None = None

    model_config = {"from_attributes": True}


class EventCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_event_comment_body(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class EventCommentRead(BaseModel):
    id: int
    event_id: int
    author_trainer_id: int | None = None
    author_parent_id: int | None = None
    body: str
    created_at: datetime
    updated_at: datetime
    author_trainer: TrainerBrief | None = None
    author_parent: ParentBrief | None = None
    can_delete: bool = False
    can_edit: bool = False

    model_config = {"from_attributes": True}


class EventAttachmentRead(BaseModel):
    id: int
    event_id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    can_delete: bool = False

    model_config = {"from_attributes": True}


class EventRsvpItem(BaseModel):
    student_id: int | None = Field(default=None, ge=1, description="Dítě, za které rodič hlasuje; None = trenér sám za sebe.")
    status: RsvpStatus = Field(examples=[RsvpStatus.yes])


class EventRsvpSet(BaseModel):
    responses: list[EventRsvpItem] = Field(min_length=1)

    @field_validator("responses", mode="after")
    @classmethod
    def unique_student_ids(cls, v: list[EventRsvpItem]) -> list[EventRsvpItem]:
        ids = [item.student_id for item in v]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate student_id in responses.")
        return v


class EventRsvpParticipant(BaseModel):
    kind: ChatParticipantKind
    id: int
    name: str
    status: RsvpStatus
    student_id: int | None = None
    child_name: str | None = None


class EventRsvpSummary(BaseModel):
    yes: int = 0
    no: int = 0
    maybe: int = 0
    participants: list[EventRsvpParticipant] = Field(default_factory=list)


class EventChildRsvp(BaseModel):
    student_id: int
    name: str
    status: RsvpStatus | None = None


class EventRead(BaseModel):
    id: int
    title: str
    description: str
    event_type: EventType
    location: str
    starts_at: datetime
    ends_at: datetime | None = None
    author_trainer_id: int | None = None
    created_at: datetime
    updated_at: datetime
    author_trainer: TrainerBrief | None = None
    targets: list[EventTargetRead] = Field(default_factory=list)
    can_edit: bool = False
    my_rsvp: RsvpStatus | None = None
    my_child_rsvps: list[EventChildRsvp] = Field(default_factory=list)
    comment_count: int = 0
    attachment_count: int = 0

    model_config = {"from_attributes": True}


class EventDetailRead(EventRead):
    comments: list[EventCommentRead] = Field(default_factory=list)
    attachments: list[EventAttachmentRead] = Field(default_factory=list)
    rsvp_summary: EventRsvpSummary | None = None
