from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class DelegueRole(str, enum.Enum):
    titulaire = "titulaire"
    suppleant = "suppleant"
    president = "president"
    vice_president = "vice_president"
    secretaire = "secretaire"
    tresorier = "tresorier"
    employe = "employe"  # salarié non-élu (ex: délégué sécurité/santé hors délégation)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    delegue_role = Column(SAEnum(DelegueRole), default=DelegueRole.titulaire, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.member, nullable=False)
    is_active = Column(Boolean, default=True)

    # Désignations spéciales (Art. L.414-2 et L.414-3)
    is_delegue_securite_sante = Column(Boolean, default=False)
    is_delegue_egalite = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="members")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
