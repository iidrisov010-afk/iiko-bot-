from datetime import date
from pydantic import BaseModel, Field


class ManagerReportIn(BaseModel):
    telegram_user_id: int | None = None
    manager_name: str = Field(min_length=2)
    branch_name: str = Field(min_length=2)
    report_date: date
    shift_name: str = Field(min_length=2)
    guests_count: int = Field(ge=0)
    avg_check: float = Field(ge=0, default=0)
    complaints_count: int = Field(ge=0, default=0)
    compliments_count: int = Field(ge=0, default=0)
    stop_list: str = ''
    issues_text: str = ''
    comment_text: str = ''
    opening_score: int = Field(ge=0, le=100, default=0)
    cleanliness_score: int = Field(ge=0, le=100, default=0)
    discipline_violations: int = Field(ge=0, default=0)
    urgent_incidents: int = Field(ge=0, default=0)


class SyncPayload(BaseModel):
    branch_name: str
    business_date: date
