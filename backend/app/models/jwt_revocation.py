from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class JwtRevocation(Base):
    """Jeton JWT révoqué individuellement (logout) — identifié par son `jti`.

    La révocation de TOUS les jetons d'un compte passe par
    `users.token_version` (le JWT porte `ver`, toute différence = rejet) :
    pas besoin d'énumérer les jetons actifs. Cette table ne sert qu'au
    logout ciblé du jeton courant.
    """

    __tablename__ = "jwt_revocations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
