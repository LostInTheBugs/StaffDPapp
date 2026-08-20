from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.modules import enabled_modules_of
from app.core.security import decode_access_token
from app.models import User

security = HTTPBearer()


def require_module(module: str):
    """FastAPI dependency factory : 403 si le module est désactivé pour l'org.

    Usage : `router = APIRouter(..., dependencies=[Depends(require_module("elections"))])`
    ou `def route(user: User = Depends(require_module("time_tracking")))`.
    Le module désactivé rend TOUTES les routes du router inaccessibles (403).
    """

    def _check(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module désactivé")
        from app.models import Organization
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        if org is None or module not in enabled_modules_of(org.enabled_modules):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module désactivé")
        return user

    return _check


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT Bearer token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    # Reject MFA-pending tokens — they must complete the MFA step first
    if payload.get("typ") != "access" or payload.get("mfa") is True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur non trouvé")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    return user
