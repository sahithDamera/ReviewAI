from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    review_link_opens: int
    sessions: int
    generations_completed: int
    reviews_selected: int
    successful_copies: int
    google_handoff_clicks: int
    average_rating: float | None


class ActivityItem(BaseModel):
    id: UUID
    event_type: str
    occurred_at: datetime
    rating: int | None


class DashboardOverview(BaseModel):
    summary: DashboardSummary
    activity: list[ActivityItem]
