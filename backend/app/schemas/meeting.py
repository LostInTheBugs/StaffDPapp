from pydantic import BaseModel
from datetime import datetime


class MeetingPointSchema(BaseModel):
    description: str
    order: int = 0

    model_config = {"from_attributes": True}


class MeetingInviteeSchema(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    status: str

    model_config = {"from_attributes": True}


class CreateMeetingRequest(BaseModel):
    title: str
    date: datetime
    location: str | None = None
    points: list[MeetingPointSchema] = []
    invitee_ids: list[int] = []


class MeetingResponse(BaseModel):
    id: int
    title: str
    date: datetime
    location: str | None
    status: str
    created_by_name: str | None = None
    points: list[MeetingPointSchema] = []
    invitees: list[MeetingInviteeSchema] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RespondRequest(BaseModel):
    status: str  # accepted or declined
