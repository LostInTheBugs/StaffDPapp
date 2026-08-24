"""Seed des données d'exemple pour la démo (org "demo").

Demande Fred 2026-08-20 : la démo doit montrer des exemples concrets —
réunions, consultations, activités délégués, stats, affichage, élection.

Idempotent : ne crée RIEN si l'org a déjà des réunions (un seed précédent
existe). À lancer APRÈS seed.sh (qui crée les comptes), dans le conteneur :
    docker compose exec -T backend python3 /app/scripts/seed_demo_data.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Lancer depuis le conteneur : python3 /app/scripts/seed_demo_data.py
# → /app/scripts est sys.path[0], il faut ajouter /app pour trouver app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models import Organization, User, DelegateActivity, NoticePost, ComplianceEvent, WorkforceStat, VaultKey
from app.models.meeting import Meeting, MeetingPoint, MeetingInvitee, MeetingStatus, InviteeStatus
from app.models.consultation import Consultation, ConsultationStatus, ConsultationCategory
from app.models.election import Election, ElectionStatus, ElectionCandidate
from app.models.time_entry import TimeEntry

ORG_SLUG = "demo"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def main() -> int:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        if org is None:
            print("[seed-demo] org 'demo' introuvable — lancez seed.sh d'abord")
            return 1

        # Idempotence : des réunions existent déjà → on ne duplique rien
        if db.query(Meeting).filter(Meeting.organization_id == org.id).count() > 0:
            print("[seed-demo] données déjà présentes — rien à faire (idempotent)")
            return 0

        sophie = db.query(User).filter(User.organization_id == org.id, User.email == "sophie@demo.lu").first()
        marc = db.query(User).filter(User.organization_id == org.id, User.email == "marc@demo.lu").first()
        laura = db.query(User).filter(User.organization_id == org.id, User.email == "laura@demo.lu").first()
        tom = db.query(User).filter(User.organization_id == org.id, User.email == "tom@demo.lu").first()
        emma = db.query(User).filter(User.organization_id == org.id, User.email == "emma@demo.lu").first()
        if not all([sophie, marc, laura, tom, emma]):
            print("[seed-demo] comptes démo incomplets — lancez seed.sh d'abord")
            return 1
        titulaires = [sophie, marc, laura, tom, emma]
        now = _now()

        # ── Réunions : 6 en 2026 (3 avec direction → conformité L.415-6) + 1 future
        meetings_spec = [
            ("Réunion ordinaire — bilan 1er trimestre", datetime(2026, 1, 15, 10, 0), False,
             ["Bilan des consultations en cours", "Conditions de travail", "Questions diverses"]),
            ("Réunion avec la direction — plan de formation", datetime(2026, 2, 20, 14, 0), True,
             ["Plan de formation continue 2026", "Télétravail", "Horaires de travail"]),
            ("Réunion ordinaire — sécurité", datetime(2026, 3, 12, 10, 0), False,
             ["Registre sécurité/santé", "Visites de contrôle", "Égalité professionnelle"]),
            ("Réunion avec la direction — restructuration", datetime(2026, 4, 24, 14, 0), True,
             ["Réorganisation des services", "Transfert d'activité", "Œuvres sociales"]),
            ("Réunion ordinaire — congés et formation", datetime(2026, 5, 7, 10, 0), False,
             ["Congés de formation", "Calendrier des réunions", "Point sur les PV"]),
            ("Réunion avec la direction — œuvres sociales", datetime(2026, 6, 18, 14, 0), True,
             ["Budget œuvres sociales", "Statistiques effectif S1", "Consultations en cours"]),
            ("Prochaine réunion ordinaire", now + timedelta(days=14), False,
             ["Ordre du jour à définir", "Points des membres"]),
        ]
        for title, date, with_direction, points in meetings_spec:
            m = Meeting(
                organization_id=org.id, created_by_id=sophie.id,
                title=title, date=date, location="Salle de réunion principale",
                status=MeetingStatus.held if date < now else MeetingStatus.planned,
                direction_invited=with_direction,
            )
            db.add(m)
            db.flush()
            for i, desc in enumerate(points):
                db.add(MeetingPoint(meeting_id=m.id, description=desc, order=i))
            for u in titulaires:
                db.add(MeetingInvitee(meeting_id=m.id, user_id=u.id, status=InviteeStatus.accepted))
        print("[seed-demo] 7 réunions créées (6 en 2026 dont 3 avec direction + 1 prochaine)")

        # ── Consultations : 1 en attente + 1 clôturée
        db.add(Consultation(
            organization_id=org.id, created_by_id=sophie.id,
            title="Consultation sur l'aménagement du temps de travail",
            category=ConsultationCategory.temps_travail,
            description="Réorganisation des horaires en équipes — demande d'avis de la délégation.",
            status=ConsultationStatus.requested,
            response_due=now + timedelta(days=10),
        ))
        db.add(Consultation(
            organization_id=org.id, created_by_id=sophie.id,
            title="Consultation sur le règlement intérieur",
            category=ConsultationCategory.reglement_interieur,
            description="Mise à jour du règlement intérieur (télétravail, droit à la déconnexion).",
            status=ConsultationStatus.closed,
            requested_at=datetime(2026, 4, 1),
            response_due=datetime(2026, 5, 31),
            direction_responded_at=datetime(2026, 5, 15),
            direction_response="Règlement mis à jour et communiqué aux salariés le 15 mai 2026.",
        ))
        print("[seed-demo] 2 consultations créées (1 en attente, 1 clôturée)")

        # ── Désignations + activités délégués
        marc.is_delegue_securite_sante = True
        laura.is_delegue_egalite = True
        db.add(DelegateActivity(
            organization_id=org.id, user_id=marc.id, domain="securite_sante",
            category="visite", description="Visite de l'atelier de production — contrôle des issues de secours.",
            activity_date=datetime(2026, 7, 2), created_by_id=marc.id,
        ))
        db.add(DelegateActivity(
            organization_id=org.id, user_id=marc.id, domain="securite_sante",
            category="signalement", description="Signalement : éclairage défectueux dans la zone de stockage.",
            activity_date=datetime(2026, 7, 18), created_by_id=marc.id,
        ))
        db.add(DelegateActivity(
            organization_id=org.id, user_id=laura.id, domain="egalite",
            category="sensibilisation", description="Campagne de sensibilisation égalité salariale femmes/hommes.",
            activity_date=datetime(2026, 6, 24), created_by_id=laura.id,
        ))
        print("[seed-demo] Marc 🛡️ + Laura ⚖️ désignés, 3 activités créées")

        # ── Stats semestrielles S1 2026 (L.414-3)
        db.add(WorkforceStat(organization_id=org.id, semester="2026-1", male_count=68, female_count=52, created_by=sophie.id))
        print("[seed-demo] stats S1 2026 créées (68/52)")

        # ── Tableau d'affichage
        db.add(NoticePost(
            organization_id=org.id, created_by_id=sophie.id, pinned=True,
            title="Assemblée plénière du personnel — septembre",
            body="L'assemblée plénière annuelle du personnel se tiendra en septembre (Art. L.415-7). "
                 "L'ordre du jour portera sur le bilan de l'année, les conditions de travail et les questions diverses.",
        ))
        print("[seed-demo] affiche épinglée créée")

        # ── Événements conformité (plénière + noms communiqués)
        db.add(ComplianceEvent(
            organization_id=org.id, event_type="plenary_assembly",
            event_date=datetime(2026, 1, 20), created_by_id=sophie.id,
            notes="Assemblée plénière annuelle tenue.",
        ))
        db.add(ComplianceEvent(
            organization_id=org.id, event_type="names_communication",
            event_date=datetime(2026, 1, 10), created_by_id=sophie.id,
            notes="Composition du bureau communiquée à la direction.",
        ))
        print("[seed-demo] événements conformité créés (plénière, noms du bureau)")

        # ── Heures du mois (widget dashboard)
        for u, hours, cat, desc in [
            (sophie, 4.0, "reunion", "Réunion avec la direction — plan de formation"),
            (sophie, 2.0, "administratif", "Préparation de l'ordre du jour"),
            (marc, 3.0, "tournee", "Tournée de contrôle sécurité/santé"),
        ]:
            db.add(TimeEntry(user_id=u.id, date=now - timedelta(days=3), hours=hours, category=cat, description=desc))
        print("[seed-demo] heures du mois créées (Sophie 6h, Marc 3h)")

        # ── Élection en cours (candidatures ouvertes)
        election = Election(
            organization_id=org.id, created_by_id=sophie.id,
            title="Renouvellement de la délégation — mandat 2026-2031",
            election_date=datetime(2027, 2, 15, 8, 0),
            candidate_deadline=datetime(2026, 12, 15),
            status=ElectionStatus.announced,
            notes="Renouvellement intégral (Art. L.413-1/2). Candidatures ouvertes jusqu'au 15 décembre 2026.",
        )
        db.add(election)
        db.flush()
        db.add(ElectionCandidate(
            election_id=election.id, user_id=sophie.id, full_name="Sophie Muller",
            list_label="Liste Unia", birth_date=datetime(1988, 3, 12), hire_date=datetime(2014, 1, 5),
            declared_not_excluded=True,
        ))
        db.add(ElectionCandidate(
            election_id=election.id, user_id=marc.id, full_name="Marc Weber",
            list_label="Liste Unia", birth_date=datetime(1985, 7, 21), hire_date=datetime(2012, 2, 1),
            declared_not_excluded=True,
        ))
        print("[seed-demo] élection annoncée avec 2 candidats (Sophie, Marc)")

        db.commit()
        print("[seed-demo] ✅ données d'exemple en place")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
