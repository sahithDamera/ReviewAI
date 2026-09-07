from datetime import date

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    sessions: int
    rated_sessions: int
    generated_sessions: int
    selected_sessions: int
    manual_sessions: int
    copied_sessions: int
    google_handoff_sessions: int
    rating_average: float | None


class AnalyticsDay(BaseModel):
    day: date
    sessions: int
    rated_sessions: int
    generated_sessions: int
    selected_sessions: int
    manual_sessions: int
    copied_sessions: int
    google_handoff_sessions: int
    rating_sum: int
    rating_count: int


class AnalyticsReport(BaseModel):
    start: date
    end: date
    summary: AnalyticsSummary
    daily: list[AnalyticsDay]
