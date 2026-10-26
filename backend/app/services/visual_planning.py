"""Validate visual direction before it reaches background generation or composition."""
import re
import unicodedata

from app.schemas import Channel, Product, VisualPlan
from app.services.composition import default_template
from app.services.generation import GenerationError


VISUAL_CHANNELS = {Channel.FEED, Channel.STORY}
BLOCKED_WORDS = (
    "preco", "desconto", "oferta", "promocao", "cupom", "logotipo", "logo",
    "embalagem", "produto", "marca d'agua", "marca d’agua", "watermark", "texto",
    "tipografia", "letras", "rotulo", "marca comercial", "brand", "packaging",
    "cura", "eficacia", "garantido", "beneficio", "alegacao",
)
NEGATIVE_PROMPT = (
    " Não gerar preços, números comerciais, textos, letras, logotipos, embalagens, "
    "produtos fictícios, marcas d'água ou marcas comerciais."
)


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def validate_visual_plan(plan: VisualPlan, product: Product) -> VisualPlan:
    if plan.channel not in VISUAL_CHANNELS or plan.layout not in {"produto_centro", "produto_direita"}:
        raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "Canal ou template visual não suportado.")
    for field in ("concept", "visual_style", "scenario", "lighting"):
        if not getattr(plan, field) or not getattr(plan, field).strip():
            raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "Plano visual incompleto.")
    if not plan.palette:
        raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "Paleta visual ausente.")
    source = " ".join([plan.art_direction, plan.background_prompt, plan.concept,
                       plan.visual_style, plan.scenario, plan.lighting, *plan.decorative_elements])
    normalized = _normalize(source)
    blocked = any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", normalized) for word in BLOCKED_WORDS)
    blocked |= bool(re.search(r"r\$|\$|\b\d+[.,]\d{2}\b|\b\d+\s*%", normalized))
    if product.name and _normalize(product.name) in normalized:
        blocked = True
    if blocked:
        raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "Plano visual contém conteúdo comercial ou elementos reservados.")
    area = ("Centro livre e faixas superior e inferior desobstruídas."
            if plan.layout == "produto_centro" else
            "Metade direita livre e faixas superior e inferior desobstruídas.")
    prompt = f"{plan.background_prompt.strip()} Cenário: {plan.scenario}. Estilo: {plan.visual_style}. Iluminação: {plan.lighting}. Cores: {', '.join(plan.palette)}. {area}{NEGATIVE_PROMPT}"
    try:
        finalized = plan.model_copy(update={"background_prompt": prompt})
        finalized = VisualPlan.model_validate(finalized.model_dump(mode="json"))
        default_template(finalized.layout, finalized.channel)
        return finalized
    except ValueError:
        raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "Prompt visual excede o contrato.") from None


def validate_visual_plans(plans: list[VisualPlan], channels: list[Channel], product: Product) -> list[VisualPlan]:
    expected = {channel for channel in channels if channel in VISUAL_CHANNELS}
    if len(plans) != len(expected) or {plan.channel for plan in plans} != expected:
        raise GenerationError("VISUAL_PLAN_CONTRACT_ERROR", "É necessário um plano por canal visual suportado.")
    return [validate_visual_plan(plan, product) for plan in plans]
