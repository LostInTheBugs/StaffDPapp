from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.user import DelegueStatus, DelegueRole


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    # Argon2id hash of the invitation code (Crockford base32, 26 chars).
    # The code itself is NEVER stored in clear — only shown once at creation.
    # Index removed because lookups now iterate over unused invitations and
    # verify the hash one by one (acceptable for low-volume invite tables).
    code_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    delegue_status = Column(SAEnum(DelegueStatus), default=DelegueStatus.titulaire, nullable=False)
    delegue_role = Column(SAEnum(DelegueRole), default=DelegueRole.membre, nullable=False)

    # Désignations spéciales
    is_delegue_securite_sante = Column(Boolean, default=False)
    is_delegue_egalite = Column(Boolean, default=False)

    is_used = Column(Boolean, default=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="invitations")
    created_by = relationship("User")
