import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, Organization
from app.models.minute import Minute, MinuteSection, MinutePublication, MinuteStatus, SectionVisibility
from app.models.meeting import Meeting
from app.models.vault_key import VaultKey
from app.schemas.minute import (
    MinuteResponse, MinuteDetailResponse, CreateMinuteRequest, UpdateSectionsRequest,
    SectionSchema, PreviewSectionSchema, DirectionPreviewResponse,
    PublishRequest, PublicationHistorySchema,
)

router = APIRouter(tags=["minutes"])

BUREAU_ROLES = {"president", "vice_president", "secretaire"}


def _section_to_dict(s: MinuteSection) -> dict:
    return {
        "id": s.id,
        "position": s.position,
        "title": s.title,
        "visibility": s.visibility.value if s.visibility else "interne",
        "content": base64.b64encode(s.content).decode("ascii") if s.content else "",
        "nonce": base64.b64encode(s.nonce).decode("ascii") if s.nonce else None,
    }


def _minute_to_response(m: Minute) -> dict:
    return {
        "id": m.id,
        "meeting_id": m.meeting_id,
        "status": m.status.value if m.status else "brouillon",
        "is_encrypted": m.is_encrypted,
        "created_by_id": m.created_by_id,
        "created_by_name": m.created_by.full_name if m.created_by else None,
        "validated_by_id": m.validated_by_id,
        "validated_by_name": m.validated_by.full_name if m.validated_by else None,
        "validated_at": m.validated_at,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
        "sections": [_section_to_dict(s) for s in (m.sections or [])],
    }


def _projection_fingerprint(sections: list) -> list[tuple[int, str, bytes]]:
    """Représentation canonique de la version direction : liste ordonnée de
    (position renumérotée, title, content_bytes) pour les sections partagées.

    Compare les OCTETS du champ content, qu'ils soient en clair ou chiffrés.
    Avec du contenu chiffré (AES-256-GCM), changer le clair produit un
    ciphertext différent, donc le fingerprint détecte le changement
    correctement. MAIS : avec un nonce aléatoire, rechiffrer le même texte
    produirait un ciphertext différent → faux positif. La solution est côté
    client : ne rechiffrer une section que si le clair a changé. Sinon,
    renvoyer le ciphertext existant tel quel. Le serveur compare les octets
    et ne verra pas de différence.
    """
    partage = [s for s in sections if s.visibility == SectionVisibility.partage]
    return [(i, s.title, s.content) for i, s in enumerate(partage)]


def _get_vault_dek_version(org_id: int, db: Session) -> int | None:
    """Return the current DEK version for the org's vault, or None if no vault."""
    vk = db.query(VaultKey).filter(
        VaultKey.organization_id == org_id, VaultKey.user_id.isnot(None)
    ).first()
    return vk.dek_version if vk else None


def _check_encryption_guard(org_id: int, sections: list, db: Session) -> None:
    """If the org's vault is enabled, refuse sections without a nonce.

    This is a server-side guard: the server must NEVER accept plaintext
    section content when the vault is enabled. An attacker who compromised
    the client JS could try to send plaintext; this blocks it.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or not org.pv_vault_enabled:
        return
    for sec in sections:
        if not sec.nonce:
            raise HTTPException(
                status_code=422,
                detail="Le coffre est activé : toutes les sections doivent être chiffrées (nonce requis)",
            )


# ── POST /api/meetings/{meeting_id}/minutes ────────────────────────


@router.post("/api/meetings/{meeting_id}/minutes", response_model=MinuteResponse, status_code=status.HTTP_201_CREATED)
def create_minute(
    meeting_id: int,
    body: CreateMinuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Cloisonnement : vérifier que la réunion appartient à l'organisation de l'utilisateur
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    # Une réunion a au plus un PV
    existing = db.query(Minute).filter(Minute.meeting_id == meeting_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un PV existe déjà pour cette réunion")

    # Encryption guard: if vault is enabled, refuse plaintext content
    _check_encryption_guard(current_user.organization_id, body.sections, db)

    minute = Minute(
        meeting_id=meeting_id,
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
    )
    db.add(minute)
    db.flush()

    # Determine DEK version if any section has a nonce
    has_encrypted = any(sec.nonce for sec in body.sections)
    if has_encrypted:
        dek_version = _get_vault_dek_version(current_user.organization_id, db)
        if dek_version is None:
            raise HTTPException(status_code=400, detail="Aucune clé de coffre trouvée — créez le coffre d'abord")
        minute.is_encrypted = True
        minute.dek_version = dek_version

    for i, sec in enumerate(body.sections):
        content_bytes = base64.b64decode(sec.content) if sec.content else b""
        nonce_bytes = base64.b64decode(sec.nonce) if sec.nonce else None
        db.add(MinuteSection(
            minute_id=minute.id,
            position=sec.position if sec.position is not None else i,
            title=sec.title,
            visibility=SectionVisibility(sec.visibility) if sec.visibility else SectionVisibility.interne,
            content=content_bytes,
            nonce=nonce_bytes,
        ))

    db.commit()
    db.refresh(minute)
    return _minute_to_response(minute)


# ── GET /api/meetings/{meeting_id}/minute ──────────────────────────


@router.get("/api/meetings/{meeting_id}/minute", response_model=MinuteResponse)
def get_meeting_minute(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère le PV associé à une réunion, ou 404 s'il n'existe pas."""
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.organization_id == current_user.organization_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    minute = db.query(Minute).filter(Minute.meeting_id == meeting_id).first()
    if not minute:
        raise HTTPException(status_code=404, detail="Aucun PV pour cette réunion")
    return _minute_to_response(minute)


# ── GET /api/minutes/{id} ──────────────────────────────────────────


@router.get("/api/minutes/{minute_id}", response_model=MinuteDetailResponse)
def get_minute(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Build publication history
    publications = (
        db.query(MinutePublication)
        .filter(MinutePublication.minute_id == minute_id)
        .order_by(MinutePublication.published_at.desc())
        .all()
    )

    result = dict(_minute_to_response(minute))
    result["publications"] = [
        {
            "id": p.id,
            "published_by_name": p.published_by.full_name if p.published_by else None,
            "published_at": p.published_at,
            "pdf_sha256": p.pdf_sha256,
            "sections_count": p.sections_count,
        }
        for p in publications
    ]
    return result


# ── PUT /api/minutes/{id}/sections ─────────────────────────────────


@router.put("/api/minutes/{minute_id}/sections", response_model=MinuteResponse)
def update_sections(
    minute_id: int,
    body: UpdateSectionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Encryption guard
    _check_encryption_guard(current_user.organization_id, body.sections, db)

    # Empreinte de la projection direction AVANT modification
    old_fingerprint = _projection_fingerprint(list(minute.sections or []))

    # Supprimer les anciennes sections
    for s in list(minute.sections or []):
        db.delete(s)
    db.flush()

    # Determine encryption status
    has_encrypted = any(sec.nonce for sec in body.sections)
    dek_version = None
    if has_encrypted:
        dek_version = _get_vault_dek_version(current_user.organization_id, db)
        if dek_version is None:
            raise HTTPException(status_code=400, detail="Aucune clé de coffre trouvée")
        minute.is_encrypted = True
        minute.dek_version = dek_version
    else:
        minute.is_encrypted = False
        minute.dek_version = None

    # Insérer les nouvelles sections (elles n'ont pas encore d'id)
    for i, sec in enumerate(body.sections):
        vis = SectionVisibility(sec.visibility) if sec.visibility else SectionVisibility.interne
        content_bytes = base64.b64decode(sec.content) if sec.content else b""
        nonce_bytes = base64.b64decode(sec.nonce) if sec.nonce else None
        db.add(MinuteSection(
            minute_id=minute.id,
            position=sec.position if sec.position is not None else i,
            title=sec.title,
            visibility=vis,
            content=content_bytes,
            nonce=nonce_bytes,
        ))
    db.flush()

    # Empreinte de la projection direction APRÈS modification
    new_sections = (
        db.query(MinuteSection)
        .filter(MinuteSection.minute_id == minute.id)
        .order_by(MinuteSection.position)
        .all()
    )
    new_fingerprint = _projection_fingerprint(new_sections)

    # Si le PV était validé ou diffusé et que la version direction a changé,
    # repasser en brouillon (et donc invalider la diffusion précédente).
    if minute.status in (MinuteStatus.valide, MinuteStatus.diffuse) and old_fingerprint != new_fingerprint:
        minute.status = MinuteStatus.brouillon
        minute.validated_by_id = None
        minute.validated_at = None

    db.commit()
    db.refresh(minute)
    return _minute_to_response(minute)


# ── POST /api/minutes/{id}/validate ────────────────────────────────


@router.post("/api/minutes/{minute_id}/validate")
def validate_minute(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Le validateur doit être membre du bureau
    if current_user.delegue_role.value not in BUREAU_ROLES:
        raise HTTPException(status_code=403, detail="Seuls les membres du bureau (président, vice-président, secrétaire) peuvent valider un PV")

    # Le validateur doit être différent du rédacteur
    if current_user.id == minute.created_by_id:
        raise HTTPException(status_code=403, detail="Le rédacteur du PV ne peut pas valider son propre PV. La validation doit être effectuée par un autre membre du bureau.")

    minute.status = MinuteStatus.valide
    minute.validated_by_id = current_user.id
    minute.validated_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "ok", "message": "PV validé"}


# ── GET /api/minutes/{id}/direction-preview ────────────────────────


@router.get("/api/minutes/{minute_id}/direction-preview", response_model=DirectionPreviewResponse)
def direction_preview(
    minute_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Projection via la même fonction que celle utilisée pour la comparaison
    # avant/après dans update_sections — garantit l'absence de divergence.
    fingerprint = _projection_fingerprint(list(minute.sections or []))

    preview_sections = []
    for pos, title, content_bytes in fingerprint:
        # Get nonce from the original section for encrypted content
        # (the fingerprint only has position, title, content — we need the nonce)
        section = next(
            (s for s in (minute.sections or [])
             if s.visibility == SectionVisibility.partage and s.title == title),
            None
        )
        preview_sections.append({
            "position": pos,
            "title": title,
            "content": base64.b64encode(content_bytes).decode("ascii") if content_bytes else "",
            "visibility": "partage",
            "nonce": base64.b64encode(section.nonce).decode("ascii") if (section and section.nonce) else None,
        })

    return {
        "minute_id": minute.id,
        "meeting_title": minute.meeting.title if minute.meeting else None,
        "validated_by_name": minute.validated_by.full_name if minute.validated_by else None,
        "validated_at": minute.validated_at,
        "sections": preview_sections,
        "generated_at": datetime.now(timezone.utc),
    }


# ── POST /api/minutes/{id}/publish ─────────────────────────────────


@router.post("/api/minutes/{minute_id}/publish")
def publish_minute(
    minute_id: int,
    body: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a minute as published and record the PDF hash.
    Reserved to the bureau only. Requires status 'valide'."""
    minute = (
        db.query(Minute)
        .filter(Minute.id == minute_id, Minute.organization_id == current_user.organization_id)
        .first()
    )
    if not minute:
        raise HTTPException(status_code=404, detail="PV non trouvé")

    # Only bureau can publish
    if current_user.delegue_role.value not in BUREAU_ROLES:
        raise HTTPException(status_code=403,
            detail="Seuls les membres du bureau peuvent diffuser un PV")

    # Must be validated
    if minute.status != MinuteStatus.valide:
        raise HTTPException(status_code=409,
            detail="Le PV doit être validé avant diffusion")

    # Count shared sections
    partage_count = sum(1 for s in (minute.sections or [])
                        if s.visibility == SectionVisibility.partage)

    # Create publication record
    pub = MinutePublication(
        minute_id=minute.id,
        published_by_id=current_user.id,
        published_at=datetime.now(timezone.utc),
        pdf_sha256=body.pdf_sha256,
        sections_count=partage_count,
    )
    db.add(pub)

    # Set minute status to diffuse
    minute.status = MinuteStatus.diffuse
    minute.published_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "status": "ok",
        "message": "PV diffusé",
        "publication_id": pub.id,
        "sections_count": partage_count,
    }
