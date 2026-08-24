"""Routes de notification : configuration, outbox, .eml, export standalone."""
import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, UserRole
from app.models.email import (
    EmailConfig, EmailOutbox, EmailStatus, TransportMode,
)
from app.models.organization import Organization
from app.schemas.email import (
    EmailConfigResponse, EmailConfigUpdate, EmailOutboxResponse, EmailTestRequest,
)
from app.services.email_service import (
    generate_eml, queue_email, render_email, send_ready_smtp, send_via_smtp,
)

router = APIRouter(prefix="/api/emails", tags=["emails"])


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'administrateur de la délégation")


def _get_or_create_config(db: Session, org_id: int) -> EmailConfig:
    cfg = db.query(EmailConfig).filter(EmailConfig.organization_id == org_id).first()
    if cfg is None:
        cfg = EmailConfig(organization_id=org_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _config_response(cfg: EmailConfig) -> EmailConfigResponse:
    return EmailConfigResponse(
        enabled=cfg.enabled,
        transport_mode=cfg.transport_mode.value,
        from_name=cfg.from_name,
        from_email=cfg.from_email,
        reply_to=cfg.reply_to,
        signature=cfg.signature,
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
        has_smtp_password=bool(cfg.smtp_password),
        smtp_use_tls=cfg.smtp_use_tls,
        smtp_use_ssl=cfg.smtp_use_ssl,
        direction_email=cfg.direction_email,
        remind_days_before=cfg.remind_days_before,
    )


def _outbox_response(m: EmailOutbox) -> EmailOutboxResponse:
    return EmailOutboxResponse(
        id=m.id,
        event_type=m.event_type.value,
        transport=m.transport.value,
        recipient_name=m.recipient_name,
        recipient_email=m.recipient_email,
        lang=m.lang,
        subject=m.subject,
        status=m.status.value,
        attempts=m.attempts,
        last_error=m.last_error,
        has_eml=bool(m.eml_path),
        exported_at=m.exported_at.isoformat() if m.exported_at else None,
        created_at=m.created_at.isoformat() if m.created_at else None,
        sent_at=m.sent_at.isoformat() if m.sent_at else None,
        payload=m.payload,
    )


@router.get("/config", response_model=EmailConfigResponse)
def get_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = _get_or_create_config(db, current_user.organization_id)
    return _config_response(cfg)


@router.put("/config", response_model=EmailConfigResponse)
def update_config(
    body: EmailConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    cfg = _get_or_create_config(db, current_user.organization_id)
    data = body.model_dump(exclude_unset=True)
    # Mot de passe : champ vide = inchangé
    if "smtp_password" in data and not data["smtp_password"]:
        del data["smtp_password"]
    for k, v in data.items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return _config_response(cfg)


@router.post("/config/test")
def send_test_email(
    body: EmailTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Envoie (ou met en file) un email de test avec la config courante."""
    _require_admin(current_user)
    cfg = _get_or_create_config(db, current_user.organization_id)
    if not cfg.enabled:
        raise HTTPException(status_code=400, detail="Les notifications sont désactivées — activez-les d'abord")
    org = db.query(Organization).get(current_user.organization_id)
    ctx = {"base_url": str(body.recipient).split("@")[0] or ""}  # placeholder; base_url réel ajouté par l'appelant
    # Le test s'envoie directement au destinataire demandé (pas de contexte réunion)
    msg = queue_email(
        db, current_user.organization_id, "test",
        body.recipient, body.recipient, "fr",
        {"base_url": "", "recipient_name": ""},
    )
    if msg is None:
        raise HTTPException(status_code=400, detail="Notifications désactivées ou config manquante")
    # En mode smtp : tentative immédiate
    if cfg.transport_mode == TransportMode.smtp:
        sent, _failed = send_ready_smtp(db, current_user.organization_id)
        if sent == 0:
            return {"status": "queued", "detail": "Mis en file (échec éventuel visible dans la liste)", "id": msg.id}
        return {"status": "sent", "detail": "Email de test envoyé", "id": msg.id}
    if cfg.transport_mode == TransportMode.eml:
        return {"status": "eml", "detail": "Fichier .eml généré — téléchargeable dans la liste", "id": msg.id}
    return {"status": "queued", "detail": "Message prêt pour export standalone", "id": msg.id}


@router.get("", response_model=list[EmailOutboxResponse])
def list_outbox(
    status_filter: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(EmailOutbox).filter(EmailOutbox.organization_id == current_user.organization_id)
    if status_filter:
        q = q.filter(EmailOutbox.status == status_filter)
    msgs = q.order_by(EmailOutbox.created_at.desc()).limit(min(limit, 500)).all()
    return [_outbox_response(m) for m in msgs]


@router.get("/{email_id}/download.eml")
def download_eml(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(EmailOutbox).filter(
        EmailOutbox.id == email_id,
        EmailOutbox.organization_id == current_user.organization_id,
    ).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message introuvable")
    if not msg.eml_path:
        # Génération à la demande (config changée après l'enqueue)
        cfg = _get_or_create_config(db, current_user.organization_id)
        org = db.query(Organization).get(current_user.organization_id)
        msg.eml_path = generate_eml(cfg, org, msg)
        db.commit()
    return FileResponse(msg.eml_path, filename=f"notification-{msg.id}.eml", media_type="message/rfc822")


@router.post("/{email_id}/retry")
def retry_email(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(EmailOutbox).filter(
        EmailOutbox.id == email_id,
        EmailOutbox.organization_id == current_user.organization_id,
    ).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message introuvable")
    msg.status = EmailStatus.ready
    msg.attempts = 0
    msg.last_error = None
    db.commit()
    if msg.transport == TransportMode.smtp:
        sent, _failed = send_ready_smtp(db, current_user.organization_id)
        if sent == 0:
            return {"status": "queued", "detail": "Nouvel essai en file"}
    return {"status": "ready", "detail": "Message relancé"}


@router.post("/{email_id}/cancel")
def cancel_email(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(EmailOutbox).filter(
        EmailOutbox.id == email_id,
        EmailOutbox.organization_id == current_user.organization_id,
    ).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message introuvable")
    msg.status = EmailStatus.cancelled
    db.commit()
    return {"status": "cancelled"}


@router.post("/{email_id}/mark-sent")
def mark_sent(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mode external : l'admin marque manuellement un message comme envoyé
    (après exécution de la CLI standalone sur une autre machine)."""
    _require_admin(current_user)
    msg = db.query(EmailOutbox).filter(
        EmailOutbox.id == email_id,
        EmailOutbox.organization_id == current_user.organization_id,
    ).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message introuvable")
    msg.status = EmailStatus.sent
    msg.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"status": "sent"}


@router.post("/export")
def export_external(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mode external : exporte les messages prêts en JSON (zip) pour la CLI
    email_sender.py — exécutable sur n'importe quelle machine avec SMTP."""
    _require_admin(current_user)
    cfg = _get_or_create_config(db, current_user.organization_id)
    msgs = db.query(EmailOutbox).filter(
        EmailOutbox.organization_id == current_user.organization_id,
        EmailOutbox.transport == TransportMode.external,
        EmailOutbox.status == EmailStatus.ready,
        EmailOutbox.exported_at.is_(None),
    ).all()
    if not msgs:
        raise HTTPException(status_code=404, detail="Aucun message en attente d'export")

    org = db.query(Organization).get(current_user.organization_id)
    items = []
    for m in msgs:
        items.append({
            "id": m.id,
            "to": m.recipient_email,
            "to_name": m.recipient_name or "",
            "subject": m.subject,
            "body_text": m.body_text,
            "body_html": m.body_html,
            "from_name": cfg.from_name or org.name,
            "from_email": cfg.from_email or f"noreply@{org.name.lower().replace(' ', '')}.invalid",
            "reply_to": cfg.reply_to,
        })

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("messages.json", json.dumps(items, ensure_ascii=False, indent=2))
        z.writestr("README.txt",
                   "Envoi : python3 email_sender.py --input messages.json "
                   "--host SMTP_HOST --port 587 [--user U --password P] [--tls] [--ssl]\n"
                   "Le script est fourni avec le projet (backend/email_sender.py).\n"
                   "Après envoi, marquez les messages comme envoyés dans l'application.\n")
    for m in msgs:
        m.exported_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=notifications-export.zip"},
    )
