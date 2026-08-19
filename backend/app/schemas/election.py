from pydantic import BaseModel, Field


class ElectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    election_date: str = Field(min_length=8)  # ISO date
    candidate_deadline: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ElectionCandidateCreate(BaseModel):
    user_id: int | None = None
    full_name: str = Field(min_length=1, max_length=200)
    list_label: str = Field(min_length=1, max_length=200)
    birth_date: str | None = None
    hire_date: str | None = None
    declared_not_excluded: bool = False


class ElectionCandidateResponse(BaseModel):
    id: int
    user_id: int | None = None
    full_name: str
    list_label: str
    eligible: bool
    eligibility_reason: str | None = None


class ElectionResponse(BaseModel):
    id: int
    title: str
    election_date: str | None = None
    candidate_deadline: str | None = None
    status: str
    notes: str | None = None
    candidates: list[ElectionCandidateResponse] = []
    votes_count: int = 0
    has_voted: bool = False
    can_manage: bool = False
    created_by_name: str | None = None


class ElectionVoteRequest(BaseModel):
    candidate_id: int


class ElectionResultList(BaseModel):
    list_label: str
    votes: int
    seats_titulaires: int
    seats_suppleants: int
    elected: list[str]          # titulaires élus
    suppleants: list[str]       # suppléants


class ElectionResultsResponse(BaseModel):
    election_id: int
    status: str
    total_votes: int
    voters_count: int
    seats: int                  # nombre de titulaires à élire
    proportional: bool          # False = majorité relative (<100 salariés)
    lists: list[ElectionResultList]
