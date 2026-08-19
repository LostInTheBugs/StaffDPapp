from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ComplianceEvent(Base):
    """Événements de conformité légale suivis par le cockpit.

    event_type :
      - plenary_assembly      : assemblée plénière annuelle (L.415-7)
      - eco_financial_report  : rapport écrit éco-financier reçu (L.414-5, ≥150)
      - names_communication   : bureau communiqué au chef d'entreprise (L.416-1)
    """

    __tablename__ = "compliance_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)
    notes = Column(String(1000), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    created_by = relationship("User")
