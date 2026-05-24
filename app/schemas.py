from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import DEFAULT_BRANCHES, AgeGroup, BranchName

_EX_BRANCH_NAME, _EX_BRANCH_ADDR = DEFAULT_BRANCHES[0]


class BranchRead(BaseModel):
    id: int = Field(examples=[1])
    name: str = Field(examples=[_EX_BRANCH_NAME])
    address: str = Field(examples=[_EX_BRANCH_ADDR])

    model_config = {"from_attributes": True}


class TrainerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    branch: BranchName


class TrainerRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Jirka"])
    last_name: str = Field(examples=["Trenér"])
    branch: BranchRead

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


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
    branch: BranchName
    parents: list[StudentParentInput] = Field(default_factory=list, max_length=2)


class StudentRead(BaseModel):
    id: int = Field(examples=[1])
    first_name: str = Field(examples=["Pepa"])
    last_name: str = Field(examples=["Zelený"])
    age_group: AgeGroup = Field(examples=[AgeGroup.U10])
    branch: BranchRead
    parents: list[ParentRead]

    model_config = {"from_attributes": True}


class MailToParentsRequest(BaseModel):
    parent_ids: list[int] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1)


class MailToParentsResponse(BaseModel):
    sent_to: list[EmailStr] = Field(examples=[["marie.novakova@example.com"]])
    message: str = Field(default="ok", examples=["ok"])
