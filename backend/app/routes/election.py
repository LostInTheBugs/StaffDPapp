"""Module Élections (L.413-1 à L.413-6, L.416-1).

Cycle complet : annonce (affiche PDF côté frontend) → candidatures avec
contrôle d'éligibilité (L.413-4) → scrutin secret anonyme → dépouillement
proportionnel (d'Hondt) ou majorité relative (<100 salariés, L.413-1) →
résultats → réunion constituante (L.416-1, suivi via compliance cockpit).

Anonymat du vote par construction : election_ballots (identité, sans choix)
et election_votes (choix, sans identité) — aucune jointure possible.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    User, Organization, Election, ElectionStatus, ElectionCandidate,
    ElectionBallot, ElectionVote,
)
from app.schemas.election import (
    ElectionCreate, ElectionCandidateCreate, ElectionCandidateResponse,
    ElectionResponse, ElectionVoteRequest, ElectionResultsResponse,
    ElectionResultList,
)

router = APIRouter(prefix="/api", tags=["elections"])

MIN_AGE_DAYS = 18 * 365.25
MIN_SENIORITY_DAYS = 12 * 30.44  # 12 mois


def _is_bureau(user: User) -> bool:
    return user.role == "admin" or user.delegue_role.value in ("president", "vice_president", "secretaire")


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date invalide")


def _candidate_eligibility(c: ElectionCandidate, election: Election):
    """Vérifie l'éligibilité (L.413-4) avec les données disponibles."""
    ref = election.election_date or datetime.now()
    if not c.birth_date:
        return False, "Date de naissance manquante"
    age_days = (ref - c.birth_date).days
    if age_days < MIN_AGE_DAYS:
        return False, "Moins de 18 ans au jour de l'élection"
    if not c.hire_date:
        return False, "Date d'embauche manquante"
    if (ref - c.hire_date).days < MIN_SENIORITY_DAYS:
        return False, "Moins de 12 mois d'ancienneté"
    if not c.declared_not_excluded:
        return False, "Déclaration sur l'honneur manquante (exclusions L.413-4)"
    return True, None


def _candidate_to_response(c: ElectionCandidate, election: Election):
    eligible, reason = _candidate_eligibility(c, election)
    return ElectionCandidateResponse(
        id=c.id, user_id=c.user_id, full_name=c.full_name,
        list_label=c.list_label, eligible=eligible, eligibility_reason=reason,
    )


def _election_to_response(e: Election, current_user: User, db: Session):
    candidates = [c for c in e.candidates]
    has_voted = db.query(ElectionBallot).filter(
        ElectionBallot.election_id == e.id,
        ElectionBallot.user_id == current_user.id,
    ).first() is not None
    votes_count = db.query(ElectionVote).filter(ElectionVote.election_id == e.id).count()
    name = f"{e.created_by.first_name} {e.created_by.last_name}".strip() if e.created_by else None
    return ElectionResponse(
        id=e.id, title=e.title,
        election_date=e.election_date.isoformat() if e.election_date else None,
        candidate_deadline=e.candidate_deadline.isoformat() if e.candidate_deadline else None,
        status=e.status.value, notes=e.notes,
        candidates=[_candidate_to_response(c, e) for c in candidates],
        votes_count=votes_count, has_voted=has_voted,
        can_manage=_is_bureau(current_user),
        created_by_name=name,
    )


def _dhondt_allocate(votes_by_list: dict[str, int], seats: int) -> dict[str, int]:
    """Répartition proportionnelle des sièges entre listes (d'Hondt)."""
    seats_by_list = {k: 0 for k in votes_by_list}
    for _ in range(seats):
        best = None
        best_q = -1.0
        for label, votes in votes_by_list.items():
            if votes <= 0:
                continue
            q = votes / (seats_by_list[label] + 1)
            if q > best_q or (q == best_q and votes > votes_by_list.get(best, 0)):
                best, best_q = label, q
        if best is None:
            break
        seats_by_list[best] += 1
    return seats_by_list


# ── CRUD ────────────────────────────────────────────────────────────

@router.get("/elections", response_model=list[ElectionResponse])
def list_elections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    elections = db.query(Election).filter(
        Election.organization_id == current_user.organization_id,
    ).order_by(Election.election_date.desc()).all()
    return [_election_to_response(e, current_user, db) for e in elections]


@router.post("/elections", response_model=ElectionResponse, status_code=201)
def create_election(
    body: ElectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    e = Election(
        organization_id=current_user.organization_id,
        title=body.title.strip(),
        election_date=_parse_date(body.election_date) or datetime.now(),
        candidate_deadline=_parse_date(body.candidate_deadline),
        notes=body.notes,
        created_by_id=current_user.id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _election_to_response(e, current_user, db)


@router.post("/elections/{election_id}/candidates", response_model=ElectionCandidateResponse, status_code=201)
def add_candidate(
    election_id: int,
    body: ElectionCandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Élection introuvable")
    if e.status != ElectionStatus.announced:
        raise HTTPException(status_code=400, detail="Candidatures fermées")
    c = ElectionCandidate(
        election_id=e.id,
        user_id=body.user_id,
        full_name=body.full_name.strip(),
        list_label=body.list_label.strip(),
        birth_date=_parse_date(body.birth_date),
        hire_date=_parse_date(body.hire_date),
        declared_not_excluded=body.declared_not_excluded,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _candidate_to_response(c, e)


@router.delete("/elections/{election_id}/candidates/{candidate_id}", status_code=204)
def remove_candidate(
    election_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None or e.status != ElectionStatus.announced:
        raise HTTPException(status_code=404 if e is None else 400,
                            detail="Élection introuvable" if e is None else "Candidatures fermées")
    c = db.query(ElectionCandidate).filter(
        ElectionCandidate.id == candidate_id,
        ElectionCandidate.election_id == e.id,
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    db.delete(c)
    db.commit()
    return None


# ── Scrutin ─────────────────────────────────────────────────────────

@router.post("/elections/{election_id}/vote", status_code=201)
def cast_vote(
    election_id: int,
    body: ElectionVoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Élection introuvable")
    if e.status != ElectionStatus.voting:
        raise HTTPException(status_code=400, detail="Le scrutin n'est pas ouvert")
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    existing = db.query(ElectionBallot).filter(
        ElectionBallot.election_id == e.id,
        ElectionBallot.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vote déjà enregistré")
    candidate = db.query(ElectionCandidate).filter(
        ElectionCandidate.id == body.candidate_id,
        ElectionCandidate.election_id == e.id,
    ).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    # Ballot (identité) et vote (choix) dans des tables séparées — non jointables.
    db.add(ElectionBallot(election_id=e.id, user_id=current_user.id))
    db.add(ElectionVote(election_id=e.id, candidate_id=candidate.id))
    db.commit()
    return {"ok": True, "message": "Vote enregistré"}


@router.post("/elections/{election_id}/open", response_model=ElectionResponse)
def open_election(
    election_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ouvre le scrutin (candidatures closes, vote possible)."""
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Élection introuvable")
    if e.status != ElectionStatus.announced:
        raise HTTPException(status_code=400, detail="Statut incompatible")
    if db.query(ElectionCandidate).filter(ElectionCandidate.election_id == e.id).count() == 0:
        raise HTTPException(status_code=400, detail="Aucun candidat — ajoutez au moins un candidat")
    e.status = ElectionStatus.voting
    db.commit()
    db.refresh(e)
    return _election_to_response(e, current_user, db)


@router.post("/elections/{election_id}/close", response_model=ElectionResultsResponse)
def close_election(
    election_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_bureau(current_user):
        raise HTTPException(status_code=403, detail="Réservé au bureau de la délégation")
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Élection introuvable")
    if e.status == ElectionStatus.announced:
        raise HTTPException(status_code=400, detail="Le scrutin n'a pas encore été ouvert")
    e.status = ElectionStatus.closed
    db.commit()
    return compute_results(e, current_user, db)


@router.get("/elections/{election_id}/results", response_model=ElectionResultsResponse)
def get_results(
    election_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.query(Election).filter(
        Election.id == election_id,
        Election.organization_id == current_user.organization_id,
    ).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Élection introuvable")
    return compute_results(e, current_user, db)


def compute_results(e: Election, current_user: User, db: Session):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    seats = org.required_titulaires if org else 1
    proportional = (org.employee_count or 0) >= 100  # L.413-1 : <100 → majorité relative

    votes = db.query(ElectionVote).filter(ElectionVote.election_id == e.id).all()
    voters = db.query(ElectionBallot).filter(ElectionBallot.election_id == e.id).count()
    candidates = db.query(ElectionCandidate).filter(ElectionCandidate.election_id == e.id).all()
    cand_by_id = {c.id: c for c in candidates}

    votes_by_candidate: dict[int, int] = {}
    for v in votes:
        votes_by_candidate[v.candidate_id] = votes_by_candidate.get(v.candidate_id, 0) + 1

    votes_by_list: dict[str, int] = {}
    for c in candidates:
        votes_by_list[c.list_label] = votes_by_list.get(c.list_label, 0) + votes_by_candidate.get(c.id, 0)

    if proportional:
        seats_by_list = _dhondt_allocate(votes_by_list, seats)
        supp_seats_by_list = _dhondt_allocate(votes_by_list, seats)
    else:
        # Majorité relative : la liste en tête emporte tous les sièges
        leader = ""
        best_v = -1
        for label, v in votes_by_list.items():
            if v > best_v:
                leader, best_v = label, v
        seats_by_list = {k: (seats if k == leader else 0) for k in votes_by_list}
        supp_seats_by_list = {k: (seats if k == leader else 0) for k in votes_by_list}

    lists_out = []
    for label in votes_by_list:
        list_cands = sorted(
            [c for c in candidates if c.list_label == label],
            key=lambda c: votes_by_candidate.get(c.id, 0), reverse=True,
        )
        elected = [c.full_name for c in list_cands[:seats_by_list[label]]]
        suppleants = [c.full_name for c in list_cands[seats_by_list[label]:seats_by_list[label] + supp_seats_by_list[label]]]
        lists_out.append(ElectionResultList(
            list_label=label, votes=votes_by_list[label],
            seats_titulaires=seats_by_list[label], seats_suppleants=supp_seats_by_list[label],
            elected=elected, suppleants=suppleants,
        ))

    return ElectionResultsResponse(
        election_id=e.id, status=e.status.value,
        total_votes=len(votes), voters_count=voters, seats=seats,
        proportional=proportional, lists=lists_out,
    )
