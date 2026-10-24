from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from pydantic import ValidationError
from app.api.dependencies import session, generation_session, read_session
import logging
from time import monotonic
from uuid import uuid4
from app.services.generation import GenerationError
from app.models import CampaignModel, PieceModel
from app.schemas import Briefing, Campaign, CampaignPage, Channel, ErrorResponse, GeneratedText, PieceState
from app.services.workflow import campaign_output, fail, invalidate_stale, validate_piece
router = APIRouter(tags=["campaigns"])
logger = logging.getLogger(__name__)

def find_campaign(db, campaign_id):
    campaign = db.get(CampaignModel, campaign_id)
    if campaign is None:
        fail(404, "CAMPAIGN_NOT_FOUND", "Campanha não encontrada.")
    return campaign

@router.get(
    "/campaigns",
    response_model=CampaignPage,
    summary="Listar campanhas",
    description=(
        "Retorna campanhas persistidas em ordem decrescente de criação, com briefing, "
        "peças e históricos. Aceita paginação e filtros opcionais. Esta consulta é "
        "somente leitura. Não exige autenticação no MVP."
    ),
    responses={422: {"model": ErrorResponse, "description": "Parâmetros de consulta inválidos."}},
)
def list_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: PieceState | None = None,
    channel: Channel | None = None,
    search: str | None = Query(default=None, min_length=1),
    db: Session = Depends(read_session),
):
    filters = []
    if status is not None:
        filters.append(select(PieceModel.id).where(
            PieceModel.campaign_id == CampaignModel.id,
            PieceModel.state == status.value,
        ).exists())
    if channel is not None:
        filters.append(select(PieceModel.id).where(
            PieceModel.campaign_id == CampaignModel.id,
            PieceModel.content["channel"].as_string() == channel.value,
        ).exists())
    if search is not None:
        term = search.strip()
        if term:
            literal = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{literal}%"
            filters.append(
                CampaignModel.briefing["campaign_name"].as_string().ilike(pattern, escape="\\")
                | CampaignModel.briefing["objective"].as_string().ilike(pattern, escape="\\")
                | CampaignModel.briefing["target_audience"].as_string().ilike(pattern, escape="\\")
            )
    total = db.scalar(select(func.count(CampaignModel.id)).where(*filters)) or 0
    campaigns = db.scalars(
        select(CampaignModel).where(*filters)
        .order_by(CampaignModel.created_at.desc(), CampaignModel.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
        .options(
            selectinload(CampaignModel.pieces).selectinload(PieceModel.validations),
            selectinload(CampaignModel.pieces).selectinload(PieceModel.reviews),
        )
    ).all()
    return {"items": [campaign_output(campaign) for campaign in campaigns],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size}

@router.post("/campaigns/generate", response_model=Campaign, status_code=201)
def generate(briefing: Briefing, request: Request, db: Session = Depends(generation_session)):
    product = request.app.state.catalog.get(briefing.product_id)
    if product is None:
        fail(404, "PRODUCT_NOT_FOUND", "Produto não encontrado.")
    rules = request.app.state.rules_loader()
    operation_id, started = str(uuid4()), monotonic()
    generator = request.app.state.generator
    provider = type(generator).__name__
    model = getattr(getattr(generator, 'settings', None), 'model', 'none')
    try:
        generated = [GeneratedText.model_validate(p) for p in request.app.state.generator.generate(briefing, product)]
    except GenerationError as exc:
        logger.warning('generation_failed operation=%s provider=%s model=%s code=%s duration=%.3f',
                       operation_id, provider, model, exc.code, monotonic() - started)
        fail(502, exc.code, exc.message)
    except (ValidationError, TypeError, ValueError):
        fail(502, 'GENERATION_CONTRACT_ERROR', 'O gerador deve retornar apenas canal e campos textuais válidos.')
    if sorted(p.channel for p in generated) != sorted(briefing.channels):
        fail(502, "GENERATION_CONTRACT_ERROR", "O gerador deve retornar uma peça por canal solicitado.")
    campaign = CampaignModel(briefing=briefing.model_dump(mode="json"))
    by_channel = {p.channel: p for p in generated}
    for index, channel in enumerate(briefing.channels):
        content = by_channel[channel].model_dump(mode="json")
        content.update(product_id=product.id, product_name=product.name, price=str(product.price),
            authorized_offer=product.authorized_offer, disclaimer=rules['generation']['disclaimer'])
        campaign.pieces.append(PieceModel(position=index, content=content, state="draft"))
    db.add(campaign)
    db.flush()
    logger.info('generation_completed operation=%s campaign=%s provider=%s model=%s duration=%.3f',
                operation_id, campaign.id, provider, model, monotonic() - started)
    return campaign_output(campaign)

@router.get("/campaigns/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str, request: Request, db: Session = Depends(session)):
    campaign = find_campaign(db, campaign_id)
    rules = request.app.state.rules_loader()
    for piece in campaign.pieces:
        invalidate_stale(piece, request.app.state.catalog, rules)
    db.flush()
    return campaign_output(campaign)

@router.post("/campaigns/{campaign_id}/validate", response_model=Campaign)
def validate(campaign_id: str, request: Request, db: Session = Depends(session)):
    campaign = find_campaign(db, campaign_id)
    rules = request.app.state.rules_loader()
    for piece in campaign.pieces:
        validate_piece(piece, request.app.state.catalog, rules)
    db.flush()
    return campaign_output(campaign)
