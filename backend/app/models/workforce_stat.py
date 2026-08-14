from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class WorkforceStat(Base):
    """Rapport semestriel de l'effectif par sexe (art. L.414-3 Code du travail).

    L'employeur établit, chaque semestre, les statistiques de l'effectif
    ventilées par sexe et les communique à la délégation du personnel.
    """

    __tablename__ = "workforce_stats"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    semester = Column(String(7), nullable=False)  # ex. "2026-1" (S1) / "2026-2" (S2)
    male_count = Column(Integer, nullable=False, default=0)
    female_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    creator = relationship("User")
