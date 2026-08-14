from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ConsultationStatus(str, enum.Enum):
    requested = "requested"              # en attente de la réponse motivée de l'employeur
    response_received = "response_received"  # réponse motivée reçue
    closed = "closed"                    # clôturée (décision prise / archivée)


# Domaines de la « vie de l'entreprise » (art. L.414-3 du Code du travail)
class ConsultationCategory(str, enum.Enum):
    conditions_travail = "conditions_travail"
    reglement_interieur = "reglement_interieur"
    temps_travail = "temps_travail"
    pension = "pension"
    formation = "formation"
    reclassement = "reclassement"
    licenciements_collectifs = "licenciements_collectifs"
    transfert = "transfert"
    interimaire = "interimaire"
    oeuvres_sociales = "oeuvres_sociales"
    statistiques_sexe = "statistiques_sexe"
    teletravail = "teletravail"
    autre = "autre"


# Délai de réponse légal de l'employeur par catégorie (jours) — None = pas de
# délai fixé par le Code du travail (réponse motivée « dans un délai raisonnable »).
DEFAULT_RESPONSE_DAYS: dict[ConsultationCategory, int | None] = {
    ConsultationCategory.reglement_interieur: 60,  # décision de l'employeur sous 2 mois
    ConsultationCategory.conditions_travail: None,
    ConsultationCategory.temps_travail: None,
    ConsultationCategory.pension: None,
    ConsultationCategory.formation: None,
    ConsultationCategory.reclassement: None,
    ConsultationCategory.licenciements_collectifs: None,  # info/consultation PRÉALABLE
    ConsultationCategory.transfert: None,                # idem
    ConsultationCategory.interimaire: None,              # idem
    ConsultationCategory.oeuvres_sociales: None,         # compte rendu ≥ 1×/an
    ConsultationCategory.statistiques_sexe: None,        # semestrielles
    ConsultationCategory.teletravail: None,
    ConsultationCategory.autre: None,
}


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=False)
    category = Column(SAEnum(ConsultationCategory), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(ConsultationStatus), default=ConsultationStatus.requested, nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    response_due = Column(DateTime(timezone=True), nullable=True)
    direction_responded_at = Column(DateTime(timezone=True), nullable=True)
    direction_response = Column(Text, nullable=True)
    last_reminded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    created_by = relationship("User")
    organization = relationship("Organization")
