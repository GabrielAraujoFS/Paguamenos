"""Explicit edits and background selection; existing validation/review remain authoritative."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import session
from app.models import PieceModel, CampaignModel
from app.schemas import Briefing, Piece, PieceEdit, VisualMetadata, VisualProcessingState
from app.services.composition import default_template
from app.services.generation import MockGenerationService
from app.services.uploads import MAX_UPLOAD_BYTES, UploadError, normalize_background
from app.services.validation import validate_content
from app.services.workflow import fail, piece_output

router = APIRouter(tags=['editing'])


def editable_piece(db, piece_id, expected_version):
    piece = db.get(PieceModel, piece_id)
    if piece is None:
        fail(404, 'PIECE_NOT_FOUND', 'Peça não encontrada.')
    job = piece.content.get('_render_job') or {}
    if job.get('state') in ('processing', 'background_ready'):
        fail(409, 'PIECE_BUSY', 'Aguarde a composição terminar antes de editar.')
    if piece.content.get('edit_version', 0) != expected_version:
        fail(409, 'EDIT_CONFLICT', 'A peça mudou. Atualize a campanha antes de salvar novamente.')
    return piece


def ensure_plan(piece, db, app):
    visual = VisualMetadata.model_validate(piece.content.get('visual') or {})
    if visual.plan is None and piece.content['channel'] in ('feed', 'story'):
        campaign = db.get(CampaignModel, piece.campaign_id)
        briefing = Briefing.model_validate({'show_price': True, **campaign.briefing, 'channels': [piece.content['channel']]})
        product = app.state.catalog.get(piece.content['product_id'])
        if product is None:
            fail(409, 'PRODUCT_NOT_FOUND', 'O produto não existe mais no catálogo.')
        visual.plan = MockGenerationService(app.state.rules_loader).generate_package(briefing, product).visual_plans[0]
        visual.template = default_template(visual.plan.layout, visual.plan.channel)
    return visual


def audit(piece, editor, kind, before, after):
    content = piece.content
    piece.content = {**content, 'edit_version': content.get('edit_version', 0) + 1,
        'edit_history': [*content.get('edit_history', []), {
            'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
            'editor_id': editor, 'kind': kind, 'before': before, 'after': after}]}
    piece.state = 'draft'


@router.post('/pieces/{piece_id}/edit', response_model=Piece)
def edit_piece(piece_id: str, body: PieceEdit, request: Request, db: Session = Depends(session)):
    piece = editable_piece(db, piece_id, body.expected_version)
    old = deepcopy(piece.content)
    visual = ensure_plan(piece, db, request.app)
    if body.template is not None:
        if visual.plan is None:
            fail(422, 'TEMPLATE_UNSUPPORTED', 'Este canal não possui composição visual.')
        visual.plan = visual.plan.model_copy(update={'layout': body.template})
        visual.template = default_template(body.template, visual.plan.channel)
    if visual.plan is not None and body.visual_style is not None:
        visual.plan = visual.plan.model_copy(update={'visual_style': body.visual_style})
    updated = {**old, 'title': body.title, 'subtitle': body.subtitle, 'cta': body.cta,
        'show_price': body.show_price, 'visual_style': body.visual_style,
        'visual': visual.model_dump(mode='json')}
    rules = request.app.state.rules_loader()
    product = request.app.state.catalog.get(old['product_id'])
    checks = validate_content(updated, product, rules)
    blocked = {'CHARACTER_LIMIT', 'TEXT_PRICE_MATCH', 'TEXT_OFFER_MATCH', 'PUBLICATION_PRICE_HIDDEN', 'PRICE_MATCH', 'OFFER_MATCH', 'PRODUCT_NAME_MATCH', 'PRODUCT_EXISTS'}
    if any(not check.passed and check.rule_code in blocked for check in checks):
        fail(422, 'EDIT_CONTENT_INVALID', 'Confira os limites de texto, a preferência de preço e os dados comerciais autorizados. As demais regras serão verificadas pelo Brand Guardian.')
    fields = ('title', 'subtitle', 'cta', 'show_price', 'visual_style')
    before = {key: old.get(key, True if key == 'show_price' else None) for key in fields}
    after = {key: updated.get(key) for key in fields}
    before['template'] = (old.get('visual') or {}).get('plan', {}).get('layout') if (old.get('visual') or {}).get('plan') else None
    after['template'] = visual.plan.layout if visual.plan else None
    if before == after:
        return piece_output(piece)
    updated['visual_needs_recomposition'] = bool(visual.final_image) or old.get('visual_needs_recomposition', False)
    # A new composition of an edited legacy piece uses the current constrained layout.
    if visual.plan:
        updated['composition_version'] = 3
    history = list(old.get('visual_history') or [])
    previous = old.get('visual') or {}
    previous_id = (previous.get('final_image') or {}).get('file_id')
    if previous_id and all((item.get('final_image') or {}).get('file_id') != previous_id for item in history):
        history.append(previous)
    updated['visual_history'] = history
    piece.content = {key: val for key, val in updated.items() if key != '_render_job'}
    audit(piece, body.editor_id, 'content', before, after)
    db.flush()
    return piece_output(piece)


@router.post('/pieces/{piece_id}/background', response_model=Piece, openapi_extra={
    'requestBody': {'required': True, 'content': {
        media: {'schema': {'type': 'string', 'format': 'binary'}} for media in ('image/png', 'image/jpeg')}}})
async def upload_background(piece_id: str, request: Request,
    editor_id: str = Query(min_length=1, max_length=100),
    rights_confirmed: bool = Query(), expected_version: int = Query(ge=0)):
    if not rights_confirmed or not editor_id.strip():
        fail(422, 'IMAGE_RIGHTS_REQUIRED', 'Confirme a autorização de uso e informe sua identificação.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            fail(413, 'IMAGE_TOO_LARGE', 'A imagem deve ter no máximo 5 MiB.')
        data.extend(chunk)
    media_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    try:
        normalized, size, original_hash = normalize_background(bytes(data), media_type)
    except UploadError as exc:
        fail(422, 'IMAGE_UPLOAD_INVALID', str(exc))
    app = request.app
    with app.state.sessions.begin() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        piece = editable_piece(db, piece_id, expected_version)
        visual = ensure_plan(piece, db, app)
        if visual.plan is None:
            fail(422, 'TEMPLATE_UNSUPPORTED', 'Upload de fundo está disponível somente para feed e story.')
        reference = app.state.image_storage.save(normalized, 'image/png', kind='background', width=size[0], height=size[1],
            metadata={'source': 'uploaded', 'piece_id': piece.id, 'campaign_id': piece.campaign_id,
                'uploader_id': editor_id.strip(), 'rights_confirmed': True,
                'created_at': datetime.now(timezone.utc).isoformat(), 'original_sha256': original_hash})
        before = {'selected_background': piece.content.get('selected_background')}
        after = {'selected_background': reference.model_dump(mode='json')}
        piece.content = {key: val for key, val in piece.content.items() if key != '_render_job'} | {
            **after, 'visual': visual.model_dump(mode='json'), 'visual_needs_recomposition': True, 'composition_version': 3}
        audit(piece, editor_id.strip(), 'background', before, after)
        db.flush()
        return piece_output(piece)
