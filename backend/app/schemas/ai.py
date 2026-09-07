from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_version: int = Field(ge=0)


class ReviewOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern="^[123]$")
    text: str = Field(min_length=1, max_length=500)


class GenerateResponse(BaseModel):
    generation_id: str
    input_version: int
    reviews: list[ReviewOption] = Field(min_length=3, max_length=3)
