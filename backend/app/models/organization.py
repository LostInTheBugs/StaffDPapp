from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    company_name = Column(String(300), nullable=True)
    country = Column(String(2), default="LU")
    employee_count = Column(Integer, nullable=False, default=15)
    mandate_end_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="organization", cascade="all, delete-orphan")

    @property
    def required_titulaires(self) -> int:
        """Calcule le nombre de titulaires requis selon l'Art. L.412-1."""
        n = self.employee_count
        if n <= 25:
            return 1
        if n <= 50:
            return 2
        if n <= 75:
            return 3
        if n <= 100:
            return 4
        if n <= 200:
            return 5
        if n <= 300:
            return 6
        if n <= 400:
            return 7
        if n <= 500:
            return 8
        if n <= 600:
            return 9
        if n <= 700:
            return 10
        if n <= 800:
            return 11
        if n <= 900:
            return 12
        if n <= 1000:
            return 13
        if n <= 1100:
            return 14
        if n <= 1500:
            return 15
        if n <= 1900:
            return 16
        if n <= 2300:
            return 17
        if n <= 2700:
            return 18
        if n <= 3100:
            return 19
        if n <= 3500:
            return 20
        if n <= 3900:
            return 21
        if n <= 4300:
            return 22
        if n <= 4700:
            return 23
        if n <= 5100:
            return 24
        if n <= 5500:
            return 25
        # >5500: +1 par tranche de 500
        return 25 + ((n - 5500) // 500) + (1 if (n - 5500) % 500 > 0 else 0)
