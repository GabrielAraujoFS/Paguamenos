from typing import Protocol
from app.schemas import Briefing, GeneratedText, Product
from app.schemas.configuration import parse_rules
from app.services.catalog import load_rules


class GenerationError(Exception):
    """Safe public failure, without upstream response bodies or credentials."""
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def configured_generator(rules_loader):
    from app.settings import GenerationConfig
    settings = GenerationConfig.from_environment()
    if settings.provider == 'mock':
        return MockGenerationService(rules_loader)
    from app.services.gemini import GeminiGenerationService
    return GeminiGenerationService(settings, rules_loader)


class GenerationService(Protocol):
    """Providers return copy only, never commercial fields or review decisions."""
    def generate(self, briefing: Briefing, product: Product) -> list[GeneratedText]: ...


class MockGenerationService:
    """Deterministic templates. No model, network call or API key is involved."""

    def __init__(self, rules_loader=load_rules):
        self.rules_loader = rules_loader

    def generate(self, briefing: Briefing, product: Product) -> list[GeneratedText]:
        rules = parse_rules(self.rules_loader())
        calls = {'neutro': 'Conheça o produto', 'acolhedor': 'Conheça com calma', 'direto': 'Confira agora'}
        values = dict(
            product_name=product.name, description=product.description,
            brand_name=rules.brand.name, brand_identity=rules.brand.textual_identity,
            cta=calls[rules.brand.tone_of_voice],
        )
        pieces = []
        for channel in briefing.channels:
            template = rules.generation.templates[channel]
            pieces.append(GeneratedText(channel=channel, **{
                field: getattr(template, field).format_map(values).strip()
                for field in ('title', 'subtitle', 'cta')
            }))
        return pieces
