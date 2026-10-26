from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
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

class VisualProcessingState(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    BACKGROUND_READY = "background_ready"
    COMPOSED = "composed"
    BLOCKED = "blocked"
    FAILED = "failed"

class VisualPlan(InputModel):
    channel: Channel
    art_direction: Annotated[str, Field(min_length=1, max_length=1000)]
    background_prompt: Annotated[str, Field(min_length=1, max_length=2000)]
    layout: Annotated[str, Field(min_length=1, max_length=100)]
    palette: list[Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]] = Field(default_factory=list, max_length=8)
    concept: str | None = Field(default=None, max_length=500)
    visual_style: str | None = Field(default=None, max_length=500)
    scenario: str | None = Field(default=None, max_length=500)
    lighting: str | None = Field(default=None, max_length=500)
    decorative_elements: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(default_factory=list, max_length=8)

class TemplateConfig(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    channel: Channel
    width: Annotated[int, Field(gt=0, le=10000)]
    height: Annotated[int, Field(gt=0, le=10000)]
    safe_area: dict[str, Annotated[int, Field(ge=0)]] = Field(default_factory=dict)
    min_font_size: Annotated[int, Field(gt=0, le=200)] = 20
    max_font_size: Annotated[int, Field(gt=0, le=300)] = 84

class ImageReference(InputModel):
    file_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

class GenerationMetadata(InputModel):
    provider: Annotated[str, Field(min_length=1, max_length=80)]
    model: Annotated[str, Field(min_length=1, max_length=120)]
    created_at: datetime
    prompt_tokens: int | None = Field(default=None, ge=0)
    response_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    attempts: int | None = Field(default=None, ge=1, le=3)

class BackgroundGenerationMetadata(InputModel):
    generation_id: str
    plan_id: str
    model: str
    prompt: str
    created_at: datetime
    attempts: int = Field(ge=1, le=2)
    duration_seconds: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    response_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    cost_basis: str | None = None

class VisualMetadata(InputModel):
    state: VisualProcessingState = VisualProcessingState.PENDING
    plan: VisualPlan | None = None
    template: TemplateConfig | None = None
    background: ImageReference | None = None
    product_image: ImageReference | None = None
    final_image: ImageReference | None = None
    generation: GenerationMetadata | None = None
    render_request_id: str | None = None
    plan_id: str | None = None
    image_generation: BackgroundGenerationMetadata | None = None
    composed_at: datetime | None = None
    source_piece_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    visual_review_required: bool = True

class RenderRequest(InputModel):
    request_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F-]{36}$")
    source_piece_id: str | None = None
    regenerate_background: bool = False
    force: bool = False

class RenderStatus(BaseModel):
    piece_id: str
    visual: VisualMetadata

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

class CampaignPage(BaseModel):
    items: list[Campaign]
    total: int
    page: int
    page_size: int
    total_pages: int

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)

class ErrorResponse(BaseModel):
    error: ErrorDetail
