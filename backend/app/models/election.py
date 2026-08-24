import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ElectionStatus(str, enum.Enum):
    announced = "announced"   # candidatures ouvertes
    voting = "voting"         # scrutin ouvert
    closed = "closed"         # dépouillement publié


class Election(Base):
    """Élection de la délégation du personnel (L.413-1 à L.413-6).

    - Renouvellement intégral entre le 1er février et le 31 mars de chaque
      5e année (L.413-2) ; l'annonce se fait par voie d'affichage.
    - Scrutin secret, représentation proportionnelle (majorité relative
      pour les entreprises de moins de 100 salariés) — L.413-1.
    """

    __tablename__ = "elections"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    election_date = Column(DateTime(timezone=True), nullable=False)
    candidate_deadline = Column(DateTime(timezone=True), nullable=True)
    status = Column(SAEnum(ElectionStatus), default=ElectionStatus.announced, nullable=False)
    notes = Column(String(1000), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    created_by = relationship("User")
    candidates = relationship("ElectionCandidate", backref="election", order_by="ElectionCandidate.id")


class ElectionCandidate(Base):
    """Candidat à une élection (L.413-4 éligibilité).

    L'éligibilité exige : 18 ans accomplis, ≥12 mois d'ancienneté précédant
    le 1er jour du mois de l'affichage, nationalité ou autorisation de
    travail ; exclus : parents/allies ≤4e degré du chef d'entreprise,
    gérants, directeurs, responsable du personnel (déclaration sur l'honneur).
    """

    __tablename__ = "election_candidates"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # membre avec compte, ou None
    full_name = Column(String(200), nullable=False)
    list_label = Column(String(200), nullable=False)  # syndicat représentatif ou liste libre
    birth_date = Column(DateTime(timezone=True), nullable=True)
    hire_date = Column(DateTime(timezone=True), nullable=True)
    declared_not_excluded = Column(Boolean, default=False, nullable=False)  # déclaration honneur L.413-4
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class ElectionBallot(Base):
    """Preuve de vote (électeur) — SANS le choix exprimé.

    Invariant d'anonymat : cette table contient l'identité, l'autre
    (election_votes) contient le choix ; aucune jointure possible par design.
    """

    __tablename__ = "election_ballots"

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    cast_at = Column(DateTime(timezone=True), server_default=func.now())


class ElectionVoteTally(Base):
    """Vote agrégé par candidat — SANS identité et SANS ligne par électeur.

    L'anonymat est STRUCTUREL : il n'existe aucune ligne par électeur, donc
    rien à corréler avec election_ballots (identité, sans choix). Seuls les
    totaux par candidat sont conservés ; le dépouillement n'a jamais eu
    besoin que de ça. (La table election_votes, ligne par électeur écrite
    dans la même transaction que le ballot, permettait une jointure par
    ordre d'insertion — supprimée par la migration 20260801_0016.)
    """

    __tablename__ = "election_vote_tallies"

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("election_candidates.id"), nullable=False, unique=True)
    count = Column(Integer, default=0, nullable=False)
