from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    display_name: str
    event_id: str | None = None
    team_id: str | None = None
    team_name: str | None = None

class EventSettingsUpdate(BaseModel):
    submission_opens_at: datetime | None = None
    submission_closes_at: datetime | None = None


class ProjectCreate(BaseModel):
    title: str
    tagline: str | None = None
    description: str | None = None
    repo_url: str | None = None
    demo_url: str | None = None
    track_id: str | None = None


class ProjectOut(BaseModel):
    id: str
    title: str
    tagline: str | None
    description: str | None
    repo_url: str | None
    demo_url: str | None
    status: str
    track_id: str | None

    class Config:
        from_attributes = True


class ScoreDraftIn(BaseModel):
    criterion_id: str
    value: float | None = None
    feedback: str | None = None


class ScoreSubmitIn(BaseModel):
    scores: list[ScoreDraftIn]


class TeamCreate(BaseModel):
    name: str
    event_id: str
