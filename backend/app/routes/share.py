"""Liens sécurisés de lecture d'un PV (partage avec la direction).

Le serveur ne détient que l'enveloppe (DEK chiffrée sous la clé dérivée du
code de lecture) : il ne peut PAS déchiffrer le contenu. Le destinataire
(direction, sans compte) ouvre /p/<token>, saisit le code transmis par un
canal séparé, et le navigateur déchiffre les sections partagées.
"""
import secrets
from datetime import datetime, timedelta
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, UserRole
from app.models.email import MinuteShareLink
from app.models.minute import Minute, SectionVisibility
from app.models.organization import Organization
from app.schemas.email import (
    ShareLinkCreate, ShareLinkCreateResponse, ShareLinkContent, ShareLinkInfo,
)

router = APIRouter(prefix="/api/share-links", tags=["share-links"])


def _get_valid_link(db: Session, token: str) -> MinuteShareLink:
    link = db.query(MinuteShareLink).filter(MinuteShareLink.token == token).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    if link.revoked:
        raise HTTPException(status_code=410, detail="Lien révoqué")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Lien expiré")
    return link


def _link_info(db: Session, link: MinuteShareLink) -> ShareLinkInfo:
    minute = db.query(Minute).get(link.minute_id)
    org = db.query(Organization).get(link.organization_id)
    meeting = minute.meeting if minute else None
    return ShareLinkInfo(
        token=link.token,
        org_name=org.name if org else "",
        minute_title=meeting.title if meeting else "",
        meeting_title=meeting.title if meeting else "",
        meeting_date=meeting.date.isoformat() if meeting and meeting.date else None,
        expires_at=link.expires_at.isoformat() if link.expires_at else None,
        revoked=link.revoked,
        valid=True,
    )


@router.get("/{token}", response_model=ShareLinkInfo)
def get_link_info(token: str, db: Session = Depends(get_db)):
    """Infos publiques du lien (titre, réunion, expiration) — sans contenu."""
    link = _get_valid_link(db, token)
    return _link_info(db, link)


@router.get("/{token}/content", response_model=ShareLinkContent)
def get_link_content(token: str, db: Session = Depends(get_db)):
    """Sections partagées du PV (ciphertext + nonce, jamais le clair).

    L'accès est ouvert par le token ; le contenu reste chiffré et n'est
    déchiffrable que dans le navigateur avec le code de lecture.
    """
    link = _get_valid_link(db, token)
    minute = db.query(Minute).get(link.minute_id)
    if minute is None:
        raise HTTPException(status_code=404, detail="PV introuvable")
    org = db.query(Organization).get(link.organization_id)
    meeting = minute.meeting

    import base64
    sections = []
    for s in sorted(minute.sections, key=lambda x: x.position):
        if s.visibility != SectionVisibility.partage:
            continue
        sections.append({
            "position": s.position,
            "title": s.title,
            "content": base64.b64encode(s.content).decode(),
            "nonce": base64.b64encode(s.nonce).decode() if s.nonce else None,
        })

    link.last_viewed_at = datetime.utcnow()
    db.commit()
    return ShareLinkContent(
        token=link.token,
        minute_title=meeting.title if meeting else "",
        meeting_title=meeting.title if meeting else "",
        meeting_date=meeting.date.isoformat() if meeting and meeting.date else None,
        org_name=org.name if org else "",
        envelope=link.envelope,
        sections=sections,
    )


@router.post("/{token}/revoke")
def revoke_link(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    link = db.query(MinuteShareLink).filter(MinuteShareLink.token == token).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    if link.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Non autorisé")
    link.revoked = True
    db.commit()
    return {"status": "revoked"}


# ── Création (utilisée par minute.py) ──────────────────────────────────

def create_share_link(
    db: Session,
    minute: Minute,
    current_user: User,
    envelope: str,
    expires_days: int,
) -> MinuteShareLink:
    token = secrets.token_urlsafe(32)
    link = MinuteShareLink(
        organization_id=minute.organization_id,
        minute_id=minute.id,
        token=token,
        envelope=envelope,
        created_by_id=current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def share_link_url(base_url: str, token: str) -> str:
    return urljoin(base_url, f"/p/{token}")
