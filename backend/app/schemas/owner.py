import re
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class UserRead(schemas.BaseUser[UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


def google_destination(value: str) -> str:
    value = value.strip()
    try:
        if len(value) > 2048 or re.search(r"[\s\\\x00-\x1f\x7f]", value):
            raise ValueError
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError
        HttpUrl(value)
        return value
    except ValueError:
        pass
    raise ValueError("Enter a complete HTTPS link without an embedded username or password.")


class BusinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    category_id: UUID
    google_review_url: str = Field(max_length=2048)
    description: str | None = Field(default=None, max_length=500)
    brand_tone: Literal["casual", "professional", "friendly", "luxury"] = "friendly"
    status: Literal["draft", "active", "paused"] = "active"
    destination_confirmed: bool = False

    _google_url = field_validator("google_review_url")(google_destination)


class AttributeRead(BaseModel):
    id: UUID
    label: str


class CategoryRead(BaseModel):
    id: UUID
    name: str
    attributes: list[AttributeRead]


class BusinessRead(BaseModel):
    id: UUID
    name: str
    category_id: UUID
    category_name: str
    description: str | None
    brand_tone: str
    status: str
    google_review_url: str
    destination_confirmed: bool
    public_identifier: str
    review_url: str
