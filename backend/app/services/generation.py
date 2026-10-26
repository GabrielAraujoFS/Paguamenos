from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from app.schemas import Briefing, Channel, GeneratedText, GenerationMetadata, Product, VisualPlan
from app.schemas.configuration import parse_rules
from app.services.catalog import load_rules


class GenerationError(Exception):
    """Safe public failure, without upstream response bodies or credentials."""
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


@dataclass(frozen=True)
class GenerationPackage:
    pieces: list[GeneratedText]
    visual_plans: list[VisualPlan]
    metadata: GenerationMetadata


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

    def generate_package(self, briefing: Briefing, product: Product) -> GenerationPackage:
        from app.services.visual_planning import validate_visual_plans
        plans = []
        for channel in briefing.channels:
            if channel not in (Channel.FEED, Channel.STORY):
                continue
            layout = "produto_direita" if channel == Channel.FEED else "produto_centro"
            plans.append(VisualPlan(channel=channel, art_direction="Composição abstrata clara e equilibrada",
                background_prompt="Fundo abstrato suave com formas orgânicas e áreas livres",
                layout=layout, palette=["#DDEEFF", "#FFFFFF"], concept={"Verão": "Leveza e luminosidade", "Dia das Mães": "Acolhimento e proximidade", "Dia dos Pais": "Acolhimento e proximidade", "Beleza": "Equilíbrio e delicadeza", "Volta às aulas": "Organização e energia", "Autocuidado": "Calma e cuidado", "Saúde e prevenção": "Clareza e serenidade"}.get(briefing.theme, "Clareza e cuidado"),
                visual_style=briefing.visual_style or "Minimalista", scenario="Estúdio abstrato",
                lighting="Difusa e uniforme", decorative_elements=["formas suaves"]))
        return GenerationPackage(pieces=self.generate(briefing, product),
            visual_plans=validate_visual_plans(plans, briefing.channels, product),
            metadata=GenerationMetadata(provider="mock", model="deterministic",
                                        created_at=datetime.now(timezone.utc), attempts=1))
