from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Polarity = Literal["mentioned", "positive", "negative"]


class PublicBusinessAttribute(BaseModel):
    id: UUID
    label: str


class PublicBusinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_identifier: str
    name: str
    category_name: str
    brand_tone: str
    logo_url: str | None
    google_review_url: str
    attributes: list[PublicBusinessAttribute]
    available: bool


class ReviewSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    business_identifier: str = Field(min_length=22, max_length=64)
    entry_source: Literal["qr", "direct"] = "direct"


class SelectedAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute_id: UUID
    polarity: Polarity = "mentioned"


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_version: int = Field(ge=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    selected_attributes: list[SelectedAttribute] = Field(default_factory=list, max_length=5)
    customer_comment: str | None = Field(default=None, max_length=500)


class ReviewSessionRead(BaseModel):
    session_token: str
    expires_at: datetime
    business: PublicBusinessRead
    input_version: int
    rating: int | None
    selected_attributes: list[SelectedAttribute]
    customer_comment: str | None
