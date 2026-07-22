from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    hours = Column(Float, nullable=False)
    description = Column(String(500), nullable=True)
    category = Column(String(50), default="administratif")  # reunion, formation, tournee, administratif, autre
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
