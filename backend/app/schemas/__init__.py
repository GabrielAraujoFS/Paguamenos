from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Channel(StrEnum):
    FEED = "feed"
    STORY = "story"
    BANNER = "banner"

class PieceState(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"

class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class Decision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"

class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

Text = Annotated[str, Field(min_length=1, max_length=2000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]

class Briefing(InputModel):
    campaign_name: Text
    product_id: Text
    objective: Text
    target_audience: Text
    channels: list[Channel] = Field(min_length=1, max_length=3)
    additional_instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("channels")
    @classmethod
    def unique_channels(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Os canais não podem se repetir.")
        return value

class Product(InputModel):
    id: Text
    name: Text
    description: Text
    category: Text
    price: Money
    authorized_offer: Text

class GeneratedText(InputModel):
    channel: Channel
    title: Text
    subtitle: Text
    cta: Text

class ValidationResult(BaseModel):
    rule_code: str
    severity: Severity
    message: str
    field: str
    passed: bool

class ValidationRun(BaseModel):
    id: str
    created_at: datetime
    fingerprint: str
    success: bool
    results: list[ValidationResult]

class ReviewDecision(InputModel):
    decision: Decision
    reviewer_id: Annotated[str, Field(min_length=1, max_length=100)]
    comment: str | None = Field(default=None, max_length=2000)

class ReviewRecord(ReviewDecision):
    id: str
    created_at: datetime
    fingerprint: str

class Piece(BaseModel):
    id: str
    campaign_id: str
    channel: Channel
    title: str
    subtitle: str
    cta: str
    disclaimer: str
    product_id: str
    product_name: str
    price: Money
    authorized_offer: str
    state: PieceState
    validations: list[ValidationRun]
    reviews: list[ReviewRecord]

class Campaign(BaseModel):
    id: str
    created_at: datetime
    briefing: Briefing
    pieces: list[Piece]

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)

class ErrorResponse(BaseModel):
    error: ErrorDetail
