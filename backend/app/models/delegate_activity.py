"""Activity logged by designated delegates (délégués désignés).

Two legal domains:
- sécurité/santé (Art. L.414-14) — weekly control tours, inspections,
  enquiries, trainings, reports
- égalité (Art. L.414-15) — actions, awareness sessions, trainings, reports

The server only stores metadata + the free-text description; nothing here
is encrypted (no vault dependency).
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.core.database import Base


class DelegateActivity(Base):
    __tablename__ = "delegate_activities"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # le délégué
    domain = Column(String(20), nullable=False)   # "securite_sante" | "egalite"
    category = Column(String(30), nullable=False) # visite|enquete|formation|signalement|action|sensibilisation|autre
    description = Column(Text, nullable=False)
    activity_date = Column(DateTime(timezone=True), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<DelegateActivity {self.domain}/{self.category} user={self.user_id}>"
