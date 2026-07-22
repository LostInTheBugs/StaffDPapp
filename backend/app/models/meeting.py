from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class MeetingStatus(str, enum.Enum):
    planned = "planned"
    cancelled = "cancelled"
    held = "held"


class InviteeStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    location = Column(String(300), nullable=True)
    status = Column(SAEnum(MeetingStatus), default=MeetingStatus.planned, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    created_by = relationship("User")
    organization = relationship("Organization")
    points = relationship("MeetingPoint", back_populates="meeting", cascade="all, delete-orphan", order_by="MeetingPoint.order")
    invitees = relationship("MeetingInvitee", back_populates="meeting", cascade="all, delete-orphan")


class MeetingPoint(Base):
    __tablename__ = "meeting_points"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    description = Column(Text, nullable=False)
    order = Column(Integer, default=0)

    meeting = relationship("Meeting", back_populates="points")


class MeetingInvitee(Base):
    __tablename__ = "meeting_invitees"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(InviteeStatus), default=InviteeStatus.pending, nullable=False)

    meeting = relationship("Meeting", back_populates="invitees")
    user = relationship("User")
