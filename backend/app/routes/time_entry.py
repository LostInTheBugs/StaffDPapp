from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models.time_entry import TimeEntry
from sqlalchemy.sql import func

router = APIRouter(prefix="/api/time", tags=["time"])


class CreateTimeEntryRequest(BaseModel):
    date: str  # ISO date
    hours: float
    description: str | None = None
    category: str = "administratif"


class TimeEntryResponse(BaseModel):
    id: int
    date: str
    hours: float
    description: str | None
    category: str
    created_at: str | None = None

    model_config = {"from_attributes": True}


class MonthlySummaryResponse(BaseModel):
    month: str
    total_hours: float
    credit_hours: float
    remaining: float


def _entry_to_response(e: TimeEntry) -> dict:
    return {
        "id": e.id,
        "date": e.date.isoformat() if e.date else "",
        "hours": e.hours,
        "description": e.description,
        "category": e.category,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("", response_model=list[TimeEntryResponse])
def list_entries(
    month: str | None = Query(None, description="YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(TimeEntry).filter(TimeEntry.user_id == current_user.id).order_by(TimeEntry.date.desc())
    if month:
        try:
            y, m = month.split("-")
            start = datetime(int(y), int(m), 1)
            if int(m) == 12:
                end = datetime(int(y) + 1, 1, 1)
            else:
                end = datetime(int(y), int(m) + 1, 1)
            q = q.filter(TimeEntry.date >= start, TimeEntry.date < end)
        except (ValueError, IndexError):
            pass
    entries = q.all()
    return [_entry_to_response(e) for e in entries]


@router.post("", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: CreateTimeEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.hours <= 0 or body.hours > 24:
        raise HTTPException(status_code=400, detail="Heures invalides (0-24)")
    try:
        dt = datetime.fromisoformat(body.date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Date invalide")

    entry = TimeEntry(
        user_id=current_user.id,
        date=dt,
        hours=body.hours,
        description=body.description,
        category=body.category,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(TimeEntry).filter(TimeEntry.id == entry_id, TimeEntry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404)
    db.delete(entry)
    db.commit()
    return None


@router.get("/summary", response_model=MonthlySummaryResponse)
def monthly_summary(
    month: str | None = Query(None, description="YYYY-MM (default: current month)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not month:
        now = datetime.now()
        month = now.strftime("%Y-%m")
    y, m = month.split("-")
    start = datetime(int(y), int(m), 1)
    if int(m) == 12:
        end = datetime(int(y) + 1, 1, 1)
    else:
        end = datetime(int(y), int(m) + 1, 1)

    total = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.date >= start,
        TimeEntry.date < end,
    ).with_entities(func.sum(TimeEntry.hours)).scalar() or 0.0

    credit = current_user.monthly_credit_hours or 20.0
    return {
        "month": month,
        "total_hours": round(total, 1),
        "credit_hours": credit,
        "remaining": round(credit - total, 1),
    }
