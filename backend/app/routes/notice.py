"""Tableau d'affichage virtuel — Art. L.414-16.

L'affichage des communications, rapports et prises de position de la
délégation du personnel, du délégué à l'égalité et du délégué à la sécurité
et à la santé s'effectue librement sur des supports divers accessibles au
personnel, y compris les moyens électroniques (L.414-16(1)).

Droits (miroir de la loi) :
- LECTURE : tout membre de l'organisation (y compris les salariés non-élus).
- ÉCRITURE : admin, bureau (président/vice-président/secrétaire), délégué
  sécurité/santé, délégué égalité — les acteurs nommés par l'article.
- ÉDITION/SUPPRESSION : l'auteur, ou admin/bureau (la délégation comme corps).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_module
from app.models import User, NoticePost
from app.schemas.notice import NoticePostCreate, NoticePostUpdate, NoticePostResponse

router = APIRouter(prefix="/api", tags=["notices"], dependencies=[Depends(require_module("notices"))])


def _can_post(user: User) -> bool:
    """Acteurs nommés par L.414-16(1) : délégation + délégués désignés."""
    return (
        user.role == "admin"
        or user.delegue_role.value in ("president", "vice_president", "secretaire")
        or user.is_delegue_securite_sante
        or user.is_delegue_egalite
    )


def _is_bureau(user: User) -> bool:
    return user.role == "admin" or user.delegue_role.value in ("president", "vice_president", "secretaire")


def _to_response(post: NoticePost) -> NoticePostResponse:
    created_by_name = None
    if post.created_by is not None:
        created_by_name = f"{post.created_by.first_name} {post.created_by.last_name}".strip() or None
    return NoticePostResponse(
        id=post.id,
        title=post.title,
        body=post.body,
        pinned=post.pinned,
        created_by_id=post.created_by_id,
        created_by_name=created_by_name,
        created_at=post.created_at.isoformat() if post.created_at else None,
        updated_at=post.updated_at.isoformat() if post.updated_at else None,
    )


@router.get("/notices", response_model=list[NoticePostResponse])
def list_notices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lecture : tout membre de l'organisation (employés compris)."""
    posts = (
        db.query(NoticePost)
        .filter(NoticePost.organization_id == current_user.organization_id)
        .order_by(NoticePost.pinned.desc(), NoticePost.created_at.desc())
        .all()
    )
    return [_to_response(p) for p in posts]


@router.post("/notices", response_model=NoticePostResponse, status_code=201)
def create_notice(
    body: NoticePostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_post(current_user):
        raise HTTPException(status_code=403, detail="Réservé à la délégation (Art. L.414-16)")
    post = NoticePost(
        organization_id=current_user.organization_id,
        title=body.title.strip(),
        body=body.body.strip(),
        pinned=body.pinned,
        created_by_id=current_user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _to_response(post)


@router.put("/notices/{post_id}", response_model=NoticePostResponse)
def update_notice(
    post_id: int,
    body: NoticePostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(NoticePost).filter(
        NoticePost.id == post_id,
        NoticePost.organization_id == current_user.organization_id,
    ).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Affiche introuvable")
    if post.created_by_id != current_user.id and not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Seul l'auteur ou le bureau peut modifier")
    if body.title is not None:
        post.title = body.title.strip()
    if body.body is not None:
        post.body = body.body.strip()
    if body.pinned is not None:
        post.pinned = body.pinned
    post.updated_at = datetime.now()
    db.commit()
    db.refresh(post)
    return _to_response(post)


@router.delete("/notices/{post_id}", status_code=204)
def delete_notice(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(NoticePost).filter(
        NoticePost.id == post_id,
        NoticePost.organization_id == current_user.organization_id,
    ).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Affiche introuvable")
    if post.created_by_id != current_user.id and not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Seul l'auteur ou le bureau peut supprimer")
    db.delete(post)
    db.commit()
    return None
