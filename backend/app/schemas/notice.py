from pydantic import BaseModel, Field


class NoticePostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    pinned: bool = False


class NoticePostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    pinned: bool | None = None


class NoticePostResponse(BaseModel):
    id: int
    title: str
    body: str
    pinned: bool = False
    created_by_id: int
    created_by_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}
