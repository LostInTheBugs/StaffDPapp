from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class NoticePost(Base):
    """Affiche du tableau d'affichage virtuel (Art. L.414-16).

    La délégation du personnel (et les délégués désignés sécurité/santé et
    égalité) peuvent afficher librement leurs communications, rapports et
    prises de position sur des supports accessibles au personnel, y compris
    les moyens électroniques.
    """

    __tablename__ = "notice_posts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    pinned = Column(Boolean, default=False, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")
    created_by = relationship("User")
