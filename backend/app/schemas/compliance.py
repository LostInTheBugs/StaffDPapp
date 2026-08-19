from pydantic import BaseModel, Field

COMPLIANCE_EVENT_TYPES = ("plenary_assembly", "eco_financial_report", "names_communication")


class ComplianceEventCreate(BaseModel):
    event_type: str = Field(pattern="^(plenary_assembly|eco_financial_report|names_communication)$")
    event_date: str | None = None  # ISO date, defaults to now
    notes: str | None = Field(default=None, max_length=1000)


class ComplianceEventResponse(BaseModel):
    id: int
    event_type: str
    event_date: str | None = None
    notes: str | None = None
    created_by_name: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class ComplianceItem(BaseModel):
    key: str
    title: str
    legal_ref: str
    status: str  # ok | warn | due | na | info
    detail: str


class ComplianceOverview(BaseModel):
    items: list[ComplianceItem]
    events: list[ComplianceEventResponse]
    generated_at: str
