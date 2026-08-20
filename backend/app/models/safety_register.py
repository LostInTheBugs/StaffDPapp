from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SafetyRegisterEntry(Base):
    """Registre spécial sécurité/santé (Art. L.414-14).

    Constatations du délégué sécurité/santé, consignées dans le registre au
    bureau de l'entreprise, contresignées par le chef de service.
    """

    __tablename__ = "safety_register_entries"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    delegate_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_date = Column(Date, nullable=False)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending | countersigned
    chef_service_name = Column(String(200), nullable=True)
    countersigned_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization = relationship("Organization")
    delegate = relationship("User", foreign_keys=[delegate_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
