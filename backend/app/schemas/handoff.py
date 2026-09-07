from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ai", "manual"]
    generation_id: UUID | None = None
    option_id: Literal["1", "2", "3"] | None = None
    final_text: str = Field(min_length=1, max_length=2000)


class SelectionRead(BaseModel):
    selection_id: UUID
    final_text: str
    is_edited: bool


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    selection_id: UUID | None = None
    outcome: Literal["success", "failed"] | None = None
