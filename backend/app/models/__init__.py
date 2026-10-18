from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def uid():
    return str(uuid4())

def now():
    return datetime.now(timezone.utc).isoformat()

class CampaignModel(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(default=now)
    briefing: Mapped[dict] = mapped_column(JSON)
    pieces: Mapped[list["PieceModel"]] = relationship(cascade="all, delete-orphan", order_by="PieceModel.position")

class PieceModel(Base):
    __tablename__ = "pieces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    position: Mapped[int]
    # Monetary values are JSON strings, never SQLite floating-point values.
    content: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="draft")
    validations: Mapped[list["ValidationModel"]] = relationship(cascade="all, delete-orphan", order_by="ValidationModel.created_at")
    reviews: Mapped[list["ReviewModel"]] = relationship(cascade="all, delete-orphan", order_by="ReviewModel.created_at")

class ValidationModel(Base):
    __tablename__ = "validations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"), index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    fingerprint: Mapped[str]
    success: Mapped[bool]
    results: Mapped[list] = mapped_column(JSON)

class ReviewModel(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"), index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    decision: Mapped[str]
    reviewer_id: Mapped[str]
    comment: Mapped[str | None]
    fingerprint: Mapped[str]
