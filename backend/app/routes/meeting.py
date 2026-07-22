from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, UserRole
from app.models.meeting import Meeting, MeetingPoint, MeetingInvitee, MeetingStatus, InviteeStatus
from app.schemas.meeting import (
    CreateMeetingRequest, MeetingResponse, RespondRequest,
    MeetingPointSchema, MeetingInviteeSchema,
)

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _meeting_to_response(m: Meeting) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "date": m.date,
        "location": m.location,
        "status": m.status.value if m.status else "planned",
        "created_by_name": m.created_by.full_name if m.created_by else None,
        "points": [
            {"description": p.description, "order": p.order}
            for p in (m.points or [])
        ],
        "invitees": [
            {
                "id": inv.id,
                "user_id": inv.user_id,
                "user_name": inv.user.full_name if inv.user else None,
                "status": inv.status.value if inv.status else "pending",
            }
            for inv in (m.invitees or [])
        ],
        "created_at": m.created_at,
    }


@router.get("", response_model=list[MeetingResponse])
def list_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meetings = (
        db.query(Meeting)
        .filter(Meeting.organization_id == current_user.organization_id)
        .order_by(Meeting.date.desc())
        .all()
    )
    return [_meeting_to_response(m) for m in meetings]


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(
    body: CreateMeetingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = Meeting(
        title=body.title,
        date=body.date,
        location=body.location,
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    db.add(meeting)
    db.flush()

    # Points
    for i, pt in enumerate(body.points):
        db.add(MeetingPoint(meeting_id=meeting.id, description=pt.description, order=pt.order or i))

    # Invitees
    for uid in body.invitee_ids:
        user = db.query(User).filter(User.id == uid, User.organization_id == current_user.organization_id).first()
        if user:
            db.add(MeetingInvitee(meeting_id=meeting.id, user_id=uid))

    db.commit()
    db.refresh(meeting)
    return _meeting_to_response(meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")
    return _meeting_to_response(meeting)


@router.post("/{meeting_id}/respond")
def respond_meeting(
    meeting_id: int,
    body: RespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.status not in ("accepted", "declined"):
        raise HTTPException(status_code=400, detail="Statut invalide (accepted ou declined)")

    invitee = (
        db.query(MeetingInvitee)
        .filter(MeetingInvitee.meeting_id == meeting_id, MeetingInvitee.user_id == current_user.id)
        .first()
    )
    if not invitee:
        raise HTTPException(status_code=404, detail="Vous n'êtes pas invité à cette réunion")

    invitee.status = InviteeStatus(body.status)
    db.commit()
    return {"status": "ok"}


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404)
    if current_user.role != UserRole.admin and meeting.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Seul l'admin ou le créateur peut supprimer")
    db.delete(meeting)
    db.commit()
    return None
