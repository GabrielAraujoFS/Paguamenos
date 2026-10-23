from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.api.dependencies import session, generation_session
import logging
from time import monotonic
from uuid import uuid4
from app.services.generation import GenerationError
from app.models import CampaignModel, PieceModel
from app.schemas import Briefing, Campaign, GeneratedText
from app.services.workflow import campaign_output, fail, invalidate_stale, validate_piece
router = APIRouter(tags=["campaigns"])
logger = logging.getLogger(__name__)

def find_campaign(db, campaign_id):
    campaign = db.get(CampaignModel, campaign_id)
    if campaign is None:
        fail(404, "CAMPAIGN_NOT_FOUND", "Campanha não encontrada.")
    return campaign

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
