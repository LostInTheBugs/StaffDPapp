from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class MinuteStatus(str, enum.Enum):
    brouillon = "brouillon"
    valide = "valide"
    diffuse = "diffuse"


class SectionVisibility(str, enum.Enum):
    interne = "interne"
    partage = "partage"


class Minute(Base):
    __tablename__ = "minutes"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    status = Column(SAEnum(MinuteStatus), default=MinuteStatus.brouillon, nullable=False)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    dek_version = Column(Integer, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    validated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting = relationship("Meeting")
    organization = relationship("Organization")
    created_by = relationship("User", foreign_keys=[created_by_id])
    validated_by = relationship("User", foreign_keys=[validated_by_id])
    sections = relationship("MinuteSection", back_populates="minute", cascade="all, delete-orphan", order_by="MinuteSection.position")


class MinuteSection(Base):
    __tablename__ = "minute_sections"

    id = Column(Integer, primary_key=True, index=True)
    minute_id = Column(Integer, ForeignKey("minutes.id"), nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    visibility = Column(SAEnum(SectionVisibility), default=SectionVisibility.interne, nullable=False)
    content = Column(LargeBinary, nullable=False)
    nonce = Column(LargeBinary, nullable=True)

    minute = relationship("Minute", back_populates="sections")


class MinutePublication(Base):
    __tablename__ = "minute_publications"

    id = Column(Integer, primary_key=True, index=True)
    minute_id = Column(Integer, ForeignKey("minutes.id"), nullable=False)
    published_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    pdf_sha256 = Column(String(64), nullable=False)
    sections_count = Column(Integer, nullable=False)

    minute = relationship("Minute")
    published_by = relationship("User")
