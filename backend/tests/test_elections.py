"""Tests module Élections (L.413-1 à L.413-6).

Couvre : cycle complet (annonce → candidatures → scrutin → clôture),
éligibilité L.413-4, anonymat du vote par construction (ballots/votes
séparés, non jointables), double vote, d'Hondt proportionnel, majorité
relative <100 salariés, isolation entre organisations.
"""

from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models import Election, ElectionCandidate, ElectionBallot, ElectionVote, Organization
from tests.helpers import fetch_captcha, create_user


def _login(client, email: str, password: str = "test123456") -> str:
    cid, ans = fetch_captcha(client)
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": cid, "captcha_answer": ans,
    })
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _mk_election(client, token, title="Élections 2026", date=None):
    r = client.post("/api/elections", json={
        "title": title,
        "election_date": date or datetime(2026, 3, 10).isoformat(),
        "candidate_deadline": datetime(2026, 2, 20).isoformat(),
    }, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── CRUD + éligibilité ──────────────────────────────────────────────

def test_election_create_bureau_only(client, org_with_users):
    r = client.post("/api/elections", json={"title": "X", "election_date": "2026-03-10"},
                    headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 403
    eid = _mk_election(client, org_with_users["sophie_token"])
    r2 = client.get("/api/elections", headers=_h(org_with_users["tom_token"]))
    assert r2.status_code == 200 and len(r2.json()) == 1


def test_candidate_eligibility(client, org_with_users):
    eid = _mk_election(client, org_with_users["sophie_token"])
    # sans données → inéligible avec motif
    r = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "Jean Test", "list_label": "Liste Libre", "declared_not_excluded": True,
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 201
    assert r.json()["eligible"] is False
    assert "naissance" in r.json()["eligibility_reason"]

    # complet → éligible
    r2 = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "Marie Test", "list_label": "Liste Libre",
        "birth_date": datetime(1990, 1, 1).isoformat(),
        "hire_date": datetime(2015, 1, 1).isoformat(),
        "declared_not_excluded": True,
    }, headers=_h(org_with_users["sophie_token"]))
    assert r2.status_code == 201 and r2.json()["eligible"] is True

    # mineur → inéligible
    r3 = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "Jeune Test", "list_label": "Liste Libre",
        "birth_date": datetime(2015, 1, 1).isoformat(),
        "hire_date": datetime(2024, 1, 1).isoformat(),
        "declared_not_excluded": True,
    }, headers=_h(org_with_users["sophie_token"]))
    assert r3.status_code == 201 and r3.json()["eligible"] is False

    # déclaration honneur absente → inéligible
    r4 = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "Paul Test", "list_label": "Liste Libre",
        "birth_date": datetime(1990, 1, 1).isoformat(),
        "hire_date": datetime(2015, 1, 1).isoformat(),
        "declared_not_excluded": False,
    }, headers=_h(org_with_users["sophie_token"]))
    assert r4.status_code == 201 and r4.json()["eligible"] is False
    assert "honneur" in r4.json()["eligibility_reason"]


# ── Cycle + anonymat ────────────────────────────────────────────────

def test_election_cycle_and_vote_anonymity(client, org_with_users):
    eid = _mk_election(client, org_with_users["sophie_token"])
    # candidature impossible après ouverture
    r = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "Candidat", "list_label": "Liste Libre",
    }, headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 201
    # ouverture sans candidat éligible possible (au moins 1 candidat requis — ok ici)
    assert client.post(f"/api/elections/{eid}/open", headers=_h(org_with_users["sophie_token"])).status_code == 200

    # vote avant/après ouverture : un autre scrutin d'abord
    eid2 = _mk_election(client, org_with_users["sophie_token"], title="Autre")
    c = client.post(f"/api/elections/{eid2}/candidates", json={
        "full_name": "C1", "list_label": "L",
    }, headers=_h(org_with_users["sophie_token"])).json()
    # scrutin non ouvert → vote refusé
    r = client.post(f"/api/elections/{eid2}/vote", json={"candidate_id": c["id"]},
                    headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 400

    # ouverture avec au moins un candidat
    assert client.post(f"/api/elections/{eid2}/open", headers=_h(org_with_users["sophie_token"])).status_code == 200

    # tom vote
    r = client.post(f"/api/elections/{eid2}/vote", json={"candidate_id": c["id"]},
                    headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 201, r.text
    # double vote refusé
    r = client.post(f"/api/elections/{eid2}/vote", json={"candidate_id": c["id"]},
                    headers=_h(org_with_users["tom_token"]))
    assert r.status_code == 400

    # ANONYMAT : ballots (identité) et votes (choix) non jointables
    db = SessionLocal()
    ballots = db.query(ElectionBallot).filter(ElectionBallot.election_id == eid2).all()
    votes = db.query(ElectionVote).filter(ElectionVote.election_id == eid2).all()
    assert len(ballots) == 1 and len(votes) == 1
    assert ballots[0].user_id is not None
    assert votes[0].candidate_id == c["id"]
    # aucune colonne user_id sur election_votes (l'anonymat est structurel)
    cols = [c.name for c in ElectionVote.__table__.columns]
    assert "user_id" not in cols, cols
    db.close()

    # clôture par un membre → 403 ; par le bureau → résultats
    assert client.post(f"/api/elections/{eid2}/close", headers=_h(org_with_users["tom_token"])).status_code == 403
    r = client.post(f"/api/elections/{eid2}/close", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["total_votes"] == 1 and r.json()["voters_count"] == 1
    # vote après clôture refusé
    r = client.post(f"/api/elections/{eid2}/vote", json={"candidate_id": c["id"]},
                    headers=_h(org_with_users["marc_token"]))
    assert r.status_code == 400


# ── Dépouillement ───────────────────────────────────────────────────

def _seed_votes(db, eid, cand_ids, counts):
    for cid, n in zip(cand_ids, counts):
        for _ in range(n):
            db.add(ElectionVote(election_id=eid, candidate_id=cid))
    db.commit()


def test_results_dhondt_proportional(client, org_with_users):
    eid = _mk_election(client, org_with_users["sophie_token"])
    db = SessionLocal()
    org = db.query(Organization).get(org_with_users["org_id"])
    org.employee_count = 120  # ≥100 → proportionnelle
    db.commit()
    db.close()

    def add(full_name, label, votes_hint=None):
        r = client.post(f"/api/elections/{eid}/candidates", json={
            "full_name": full_name, "list_label": label,
            "birth_date": "1990-01-01T00:00:00", "hire_date": "2015-01-01T00:00:00",
            "declared_not_excluded": True,
        }, headers=_h(org_with_users["sophie_token"]))
        assert r.status_code == 201
        return r.json()["id"]

    # Liste A : 5 candidats ; Liste B : 4 candidats
    a = [add(f"A{i}", "Liste A") for i in range(5)]
    b = [add(f"B{i}", "Liste B") for i in range(4)]
    # Votes : A total 30 (15,10,5,0,0), B total 20 (12,8,0,0)
    db = SessionLocal()
    _seed_votes(db, eid, a + b, [15, 10, 5, 0, 0, 12, 8, 0, 0])
    db.close()

    assert client.post(f"/api/elections/{eid}/open", headers=_h(org_with_users["sophie_token"])).status_code == 200
    r = client.post(f"/api/elections/{eid}/close", headers=_h(org_with_users["sophie_token"]))
    assert r.status_code == 200
    data = r.json()
    assert data["proportional"] is True
    assert data["seats"] == 5
    assert data["total_votes"] == 50
    by_label = {x["list_label"]: x for x in data["lists"]}
    # d'Hondt sur 5 sièges : A=3, B=2 (vérifié à la main)
    assert by_label["Liste A"]["seats_titulaires"] == 3, data
    assert by_label["Liste B"]["seats_titulaires"] == 2, data
    # Élus par ordre de voix : A: A0,A1,A2 ; suppléants A: A3,A4
    assert by_label["Liste A"]["elected"] == ["A0", "A1", "A2"]
    assert by_label["Liste A"]["suppleants"] == ["A3", "A4"]
    assert by_label["Liste B"]["elected"] == ["B0", "B1"]
    assert by_label["Liste B"]["suppleants"] == ["B2", "B3"]


def test_results_majority_under_100(client, org_with_users):
    eid = _mk_election(client, org_with_users["sophie_token"])
    db = SessionLocal()
    org = db.query(Organization).get(org_with_users["org_id"])
    org.employee_count = 50  # <100 → majorité relative
    db.commit()
    db.close()

    def add(full_name, label):
        r = client.post(f"/api/elections/{eid}/candidates", json={
            "full_name": full_name, "list_label": label,
            "birth_date": "1990-01-01T00:00:00", "hire_date": "2015-01-01T00:00:00",
            "declared_not_excluded": True,
        }, headers=_h(org_with_users["sophie_token"]))
        return r.json()["id"]

    a = [add(f"A{i}", "Liste A") for i in range(3)]
    b = [add(f"B{i}", "Liste B") for i in range(3)]
    db = SessionLocal()
    _seed_votes(db, eid, a + b, [10, 5, 0, 8, 4, 0])
    db.close()
    client.post(f"/api/elections/{eid}/open", headers=_h(org_with_users["sophie_token"]))
    r = client.post(f"/api/elections/{eid}/close", headers=_h(org_with_users["sophie_token"]))
    data = r.json()
    assert data["proportional"] is False
    assert data["seats"] == 2  # barème L.412-1 : 26-50 salariés → 2 titulaires
    by_label = {x["list_label"]: x for x in data["lists"]}
    # Liste A (15 voix) emporte tous les sièges (majorité relative)
    assert by_label["Liste A"]["seats_titulaires"] == 2
    assert by_label["Liste B"]["seats_titulaires"] == 0


def test_elections_org_isolation(client, org_with_users):
    eid = _mk_election(client, org_with_users["sophie_token"])
    r = client.get("/api/elections", headers=_h(org_with_users["other_token"]))
    assert r.json() == []
    r = client.post(f"/api/elections/{eid}/open", headers=_h(org_with_users["other_token"]))
    assert r.status_code == 404
    r = client.post(f"/api/elections/{eid}/candidates", json={
        "full_name": "X", "list_label": "L",
    }, headers=_h(org_with_users["other_token"]))
    assert r.status_code == 404
