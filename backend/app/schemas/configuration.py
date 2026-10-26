"""Internal configuration contracts; public API schemas remain unchanged."""

from string import Formatter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import Channel, Severity


TextField = Literal['title', 'subtitle', 'cta', 'disclaimer']
ContentField = Literal[
    'title', 'subtitle', 'cta', 'disclaimer', 'product_id',
    'product_name', 'price', 'authorized_offer',
]
Nonblank = Annotated[str, Field(min_length=1, max_length=2000)]
HexColor = Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$')]


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BrandProfile(Configuration):
    name: Nonblank = 'Marca de demonstração'
    textual_identity: str = Field(default='', max_length=200)
    allowed_colors: list[HexColor] = Field(default_factory=list)
    allowed_fonts: list[Nonblank] = Field(default_factory=list)
    # Deterministic mock styles, not a semantic assessment of tone.
    tone_of_voice: Literal['neutro', 'acolhedor', 'direto'] = 'neutro'


class ExpressionRule(Configuration):
    expression: Nonblank
    fields: list[TextField] = Field(
        default_factory=lambda: ['title', 'subtitle', 'cta', 'disclaimer'], min_length=1,
    )
    channels: list[Channel] = Field(default_factory=lambda: list(Channel), min_length=1)
    severity: Severity = Severity.CRITICAL


PLACEHOLDERS = {'product_name', 'description', 'brand_name', 'brand_identity', 'cta'}


class ChannelTemplate(Configuration):
    title: Nonblank
    subtitle: Nonblank = '{description} {brand_identity}'
    cta: Nonblank = '{cta}'

    @field_validator('title', 'subtitle', 'cta')
    @classmethod
    def supported_placeholders(cls, value):
        for _, name, spec, conversion in Formatter().parse(value):
            if name is not None and (name not in PLACEHOLDERS or spec or conversion):
                raise ValueError('Use somente os placeholders textuais documentados, sem formatação adicional.')
        return value


class GenerationSettings(Configuration):
    disclaimer: Nonblank = 'Campanha fictícia. Dados sintéticos.'
    templates: dict[Channel, ChannelTemplate] = Field(default_factory=lambda: {
        Channel.FEED: ChannelTemplate(title='Conheça {product_name}'),
        Channel.STORY: ChannelTemplate(title='Seu próximo cuidado: {product_name}'),
        Channel.BANNER: ChannelTemplate(title='Descubra {product_name}'),
    })

    @field_validator('templates')
    @classmethod
    def all_channels(cls, value):
        if set(value) != set(Channel):
            raise ValueError('Configure os modelos de feed, story e banner.')
        return value


class CommercialRules(Configuration):
    # Catalog fields are ALWAYS checked; these options only restrict free text.
    text_price_policy: Literal['catalog_only', 'forbid'] = 'catalog_only'
    offer_markers: list[Nonblank] = Field(default_factory=lambda: [
        'desconto', 'promoção', 'frete grátis', 'cashback', 'cupom',
    ])


class BrandRules(Configuration):
    version: Nonblank = 'synthetic-1'
    synthetic: Literal[True] = True
    notice: Nonblank = 'Configuração provisória e sintética para demonstração.'
    brand: BrandProfile = Field(default_factory=BrandProfile)
    allowed_channels: list[Channel] = Field(default_factory=lambda: list(Channel), min_length=1)
    required_fields: list[ContentField] = Field(default_factory=lambda: [
        'title', 'subtitle', 'cta', 'disclaimer', 'product_id',
        'product_name', 'price', 'authorized_offer',
    ])
    character_limits: dict[Channel, dict[TextField, Annotated[int, Field(strict=True, gt=0, le=10000)]]]
    required_information: dict[TextField, list[Nonblank]] = Field(default_factory=dict)
    required_expressions: list[ExpressionRule] = Field(default_factory=list)
    forbidden_expressions: list[ExpressionRule] = Field(default_factory=list)
    # Only editorial rules can be downgraded. Catalog and required fields cannot.
    severities: dict[Literal['CHARACTER_LIMIT', 'REQUIRED_INFORMATION'], Severity] = Field(default_factory=dict)
    commercial: CommercialRules = Field(default_factory=CommercialRules)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)

    @field_validator('character_limits')
    @classmethod
    def complete_limits(cls, value):
        if set(value) != set(Channel):
            raise ValueError('Configure limites para feed, story e banner.')
        if any(not {'title', 'subtitle', 'cta'} <= set(limits) for limits in value.values()):
            raise ValueError('Cada canal precisa de limites para title, subtitle e cta.')
        return value


def parse_rules(value: dict | BrandRules) -> BrandRules:
    return value if isinstance(value, BrandRules) else BrandRules.model_validate(value)
