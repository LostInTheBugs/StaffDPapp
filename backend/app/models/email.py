"""Email & secure-share models.

Architecture (validée Fred, 2026-08-13) : une outbox unique alimentée par les
événements de l'app (convocation, PV → direction, PV → DP, invitation,
rappel), transportée selon le mode configuré par l'organisation :

  - 'eml'      : génération de fichiers .eml (RFC 5322) téléchargeables —
                 cas « serveur interne sans accès SMTP ».
  - 'smtp'     : envoi direct via un serveur SMTP (auth ou non, STARTTLS/SSL).
  - 'external' : export JSON consommé par une CLI standalone (email_sender.py)
                 qui peut tourner sur une machine tierce.
  - 'mailbox'  : réservé (mode 4 — webmail local intégré), non implémenté.
                 Le champ transport reste extensible.

Le clair des PV ne transite JAMAIS par le serveur : l'envoi du PV vers la
direction passe par un MinuteShareLink — le client (coffre déverrouillé)
chiffre la DEK sous une clé dérivée d'un code de lecture saisi par la
direction, stocke l'enveloppe côté serveur, et la direction déchiffre dans
SON navigateur à partir du code. Le serveur ne détient que l'enveloppe.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class TransportMode(str, enum.Enum):
    eml = "eml"
    smtp = "smtp"
    external = "external"
    mailbox = "mailbox"  # réservé (mode 4)


class EmailEventType(str, enum.Enum):
    meeting_invite = "meeting_invite"
    meeting_reminder = "meeting_reminder"
    minutes_direction = "minutes_direction"
    minutes_dp = "minutes_dp"
    member_invite = "member_invite"
    test = "test"


class EmailStatus(str, enum.Enum):
    ready = "ready"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"


class EmailConfig(Base):
    """Configuration des notifications par organisation (une seule ligne)."""

    __tablename__ = "email_configs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    transport_mode = Column(SAEnum(TransportMode), default=TransportMode.eml, nullable=False)

    # Expéditeur (identité affichée dans les emails)
    from_name = Column(String(200), nullable=True)
    from_email = Column(String(300), nullable=True)
    reply_to = Column(String(300), nullable=True)
    signature = Column(Text, nullable=True)

    # SMTP (mode smtp)
    smtp_host = Column(String(300), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(300), nullable=True)
    smtp_password = Column(String(500), nullable=True)  # stocké en clair côté serveur (config org) ; masqué à l'affichage
    smtp_use_tls = Column(Boolean, default=True, nullable=False)   # STARTTLS (port 587)
    smtp_use_ssl = Column(Boolean, default=False, nullable=False)  # SSL direct (port 465)

    # Adresse email de la direction (reçoit convocations et PV partagés)
    direction_email = Column(String(300), nullable=True)

    # Rappels
    remind_days_before = Column(Integer, default=3, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")


class EmailOutbox(Base):
    """File de sortie des messages. Un pipeline, plusieurs transports."""

    __tablename__ = "email_outbox"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event_type = Column(SAEnum(EmailEventType), nullable=False)
    transport = Column(SAEnum(TransportMode), nullable=False)  # copié du config à l'enqueue

    recipient_name = Column(String(300), nullable=True)
    recipient_email = Column(String(300), nullable=False)
    lang = Column(String(8), default="fr", nullable=False)

    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)

    # Métadonnées de contexte (meeting_id, minute_id, token, invite code, …)
    payload = Column(JSON, nullable=True)

    status = Column(SAEnum(EmailStatus), default=EmailStatus.ready, nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)

    # Mode eml : fichier généré sur disque (volume emails/)
    eml_path = Column(String(500), nullable=True)
    # Mode external : exporté une fois (évite les doublons d'export)
    exported_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")

    @property
    def event_key(self) -> str:
        """Clé d'idempotence (un seul rappel/convocation par cible)."""
        return f"{self.organization_id}:{self.event_type}:{self.recipient_email}:{self.payload or {}}"


class MinuteShareLink(Base):
    """Lien sécurisé de lecture d'un PV pour la direction (sans compte).

    Le serveur ne détient que l'enveloppe (DEK chiffrée sous la clé dérivée
    du code de lecture) — le contenu n'est déchiffrable que dans le
    navigateur du destinataire, avec le code transmis par un canal séparé.
    """

    __tablename__ = "minute_share_links"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    minute_id = Column(Integer, ForeignKey("minutes.id"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    # Enveloppe : {"algo":"argon2id","salt":b64,"nonce":b64,"wrapped":b64}
    # Clé dérivée du code de lecture côté client (mêmes params que le coffre).
    envelope = Column(Text, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)

    minute = relationship("Minute")
    created_by = relationship("User")
