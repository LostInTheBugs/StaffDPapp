from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, LargeBinary, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class VaultKey(Base):
    __tablename__ = "vault_keys"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    invitation_id = Column(Integer, ForeignKey("invitations.id"), nullable=True)
    wrapped_dek = Column(LargeBinary, nullable=False)   # AES-GCM(KEK, DEK) — 48 octets
    nonce = Column(LargeBinary, nullable=False)          # 12 octets
    kdf_salt = Column(LargeBinary, nullable=False)       # 16 octets
    kdf_params = Column(String(500), nullable=False)     # JSON: {"algo":"argon2id","m":65536,"t":3,"p":1}
    # Enveloppe de récupération (optionnelle) : AES-GCM(KEK_recovery, DEK) —
    # KEK_recovery dérivée de la clé de récupération via PBKDF2 côté client.
    # Le serveur ne stocke JAMAIS la clé de récupération elle-même.
    recovery_wrapped_dek = Column(LargeBinary, nullable=True)
    recovery_nonce = Column(LargeBinary, nullable=True)
    recovery_kdf_salt = Column(LargeBinary, nullable=True)
    recovery_kdf_params = Column(String(500), nullable=True)
    dek_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Exactement un de user_id / invitation_id non nul
        CheckConstraint(
            "(user_id IS NOT NULL AND invitation_id IS NULL) OR "
            "(user_id IS NULL AND invitation_id IS NOT NULL)",
            name="ck_vault_keys_exactly_one_owner",
        ),
    )

    organization = relationship("Organization")
    user = relationship("User")
