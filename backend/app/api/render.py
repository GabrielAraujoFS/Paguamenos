"""In-process visual jobs for the local MVP; no SQLite lock during image API calls."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Request, Response
from sqlalchemy import text

from app.models import PieceModel
from app.schemas import (BackgroundGenerationMetadata, ImageReference, RenderRequest,
                         RenderStatus, VisualMetadata, VisualPlan, VisualProcessingState)
from app.services.composition import CompositionError, default_template
from app.services.image_generation import ImageGenerationError, LocalAssetBackgroundGenerator, background_prompt, plan_identifier
from app.services.availability import IMAGE_FALLBACK_CODES
from app.services.workflow import fail, invalidate_stale

router = APIRouter(tags=['render'])


def _visual(piece) -> VisualMetadata:
    return VisualMetadata.model_validate(piece.content.get('_render_job') or piece.content.get('visual') or {})


def _status(piece) -> RenderStatus:
    return RenderStatus(piece_id=piece.id, visual=_visual(piece))


def _save_visual(piece, visual: VisualMetadata) -> None:
    piece.content = {**piece.content, '_render_job': visual.model_dump(mode='json')}


def _background_from_piece(app, piece, visual: VisualMetadata) -> ImageReference | None:
    if visual.background is None:
        return None
    try:
        stored = app.state.image_storage.get(visual.background)
    except (FileNotFoundError, ValueError):
        raise CompositionError('BACKGROUND_MISSING', 'Fundo armazenado ausente ou inválido.') from None
    if stored.metadata.get('kind') != 'background':
        raise CompositionError('BACKGROUND_NOT_AUTHORIZED', 'Referência não corresponde a um fundo gerado.')
    return visual.background


@router.post('/pieces/{piece_id}/render', response_model=RenderStatus, status_code=202)
def start_render(piece_id: str, body: RenderRequest, request: Request,
                 response: Response, tasks: BackgroundTasks):
    app = request.app
    with app.state.sessions() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        try:
            piece = db.get(PieceModel, piece_id)
            if piece is None:
                fail(404, 'PIECE_NOT_FOUND', 'Peça não encontrada.')
            visual = _visual(piece)
            if body.use_local_assets:
                if body.regenerate_background or body.source_piece_id:
                    fail(422, 'INVALID_RENDER_OPTIONS', 'A composição local não pode ser combinada com geração ou reutilização de fundo.')
                if visual.error_code not in IMAGE_FALLBACK_CODES and not (body.request_id and body.request_id == visual.render_request_id):
                    fail(409, 'LOCAL_FALLBACK_UNAVAILABLE', 'A composição alternativa exige uma falha temporária do provedor.')
            if visual.plan is None:
                fail(409, 'VISUAL_PLAN_MISSING', 'Esta peça não possui plano visual compatível.')
            if visual.state in (VisualProcessingState.PROCESSING, VisualProcessingState.BACKGROUND_READY):
                response.status_code = 202
                result = _status(piece)
                db.commit()
                return result
            if body.request_id and body.request_id == visual.render_request_id:
                response.status_code = 200
                result = _status(piece)
                db.commit()
                return result
            if visual.state == VisualProcessingState.COMPOSED and not (body.force or body.regenerate_background or body.source_piece_id or body.use_local_assets or piece.content.get('visual_needs_recomposition')):
                response.status_code = 200
                result = _status(piece)
                db.commit()
                return result
            try:
                if piece.content.get('product_photo_version', 'legacy') == 'legacy':
                    app.state.composer.check_assets(piece.content['product_id'])
                else:
                    app.state.composer.check_assets(piece.content['product_id'], version=piece.content['product_photo_version'])
                default_template(visual.plan.layout, visual.plan.channel)
                if body.source_piece_id:
                    source = db.get(PieceModel, body.source_piece_id)
                    if (source is None or source.campaign_id != piece.campaign_id
                            or source.content.get('channel') != piece.content.get('channel')):
                        fail(409, 'BACKGROUND_SOURCE_NOT_AUTHORIZED', 'A origem deve ser peça do mesmo canal e campanha.')
                    background = _background_from_piece(app, source, _visual(source))
                    if background is None:
                        fail(409, 'BACKGROUND_MISSING', 'A peça de origem não possui fundo.')
                elif body.use_local_assets:
                    background = None
                else:
                    if not body.regenerate_background and piece.content.get('selected_background'):
                        background = _background_from_piece(app, piece, VisualMetadata(background=piece.content['selected_background']))
                    else:
                        background = None if body.regenerate_background else _background_from_piece(app, piece, visual)
                if background is None and app.state.background_generator is None and not body.use_local_assets:
                    raise CompositionError('IMAGE_PROVIDER_UNCONFIGURED', 'Configure o provedor de fundos ou reutilize um fundo existente.')
            except CompositionError as exc:
                visual.state = VisualProcessingState.BLOCKED
                visual.error_code, visual.error_message = exc.code, str(exc)
                _save_visual(piece, visual)
                result = _status(piece)
                db.commit()
                response.status_code = 200
                return result
            request_id = body.request_id or str(uuid4())
            visual.state = VisualProcessingState.PROCESSING
            visual.render_request_id = request_id
            visual.composition_source = 'local_assets' if body.use_local_assets else None
            visual.fallback_reason = visual.error_code if body.use_local_assets else None
            visual.retry_after_seconds = None
            visual.plan_id = plan_identifier(visual.plan)
            visual.source_piece_id = body.source_piece_id
            visual.background = background
            visual.final_image = None
            visual.error_code = visual.error_message = None
            _save_visual(piece, visual)
            result = _status(piece)
            db.commit()
        except Exception:
            db.rollback()
            raise
    tasks.add_task(run_visual_render, app, piece_id, request_id)
    return result


@router.get('/pieces/{piece_id}/render', response_model=RenderStatus)
def get_render(piece_id: str, request: Request):
    with request.app.state.sessions() as db:
        piece = db.get(PieceModel, piece_id)
        if piece is None:
            fail(404, 'PIECE_NOT_FOUND', 'Peça não encontrada.')
        return _status(piece)


def run_visual_render(app, piece_id: str, request_id: str) -> None:
    """BackgroundTasks runs after the POST response; process crashes can interrupt it."""
    with app.state.sessions() as db:
        piece = db.get(PieceModel, piece_id)
        if piece is None:
            return
        visual = _visual(piece)
        if visual.render_request_id != request_id or visual.state != VisualProcessingState.PROCESSING:
            return
        plan = VisualPlan.model_validate(visual.plan.model_dump(mode='json'))
        background = visual.background
        snapshot = SimpleNamespace(id=piece.id, campaign_id=piece.campaign_id,
            content={key: value for key, value in piece.content.items() if key != '_render_job'}, state=piece.state)
        snapshot.content['visual'] = visual.model_dump(mode='json')
    try:
        if background is None:
            generator = (LocalAssetBackgroundGenerator(app.state.image_storage)
                if visual.composition_source == 'local_assets' else app.state.background_generator)
            if generator is None:
                raise ImageGenerationError('IMAGE_PROVIDER_UNCONFIGURED', 'Provedor de fundos indisponível.')
            if hasattr(generator, 'generate_with_metadata'):
                generated = generator.generate_with_metadata(plan)
                background, image_metadata = generated.reference, generated.metadata
            else:
                background = generator.generate(plan)
                image_metadata = BackgroundGenerationMetadata(generation_id=str(uuid4()),
                    plan_id=plan_identifier(plan), model='local_assets' if visual.composition_source == 'local_assets' else 'local_test', prompt=background_prompt(plan),
                    created_at=datetime.now(timezone.utc), attempts=1, duration_seconds=0)
            with app.state.sessions() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                current = db.get(PieceModel, piece_id)
                current_visual = _visual(current)
                if current_visual.render_request_id != request_id:
                    db.rollback()
                    return
                current_visual.background = background
                current_visual.image_generation = image_metadata
                current_visual.state = VisualProcessingState.BACKGROUND_READY
                _save_visual(current, current_visual)
                db.commit()
            snapshot.content['visual'] = current_visual.model_dump(mode='json')
        current_visual = VisualMetadata.model_validate(snapshot.content['visual'])
        stored_source = app.state.image_storage.get(background).metadata.get('metadata', {}).get('source')
        current_visual.composition_source = ('local_assets' if stored_source == 'local_assets' else
            'local_test' if stored_source == 'local_test' else
            'uploaded' if stored_source == 'uploaded' else 'ai')
        if stored_source == 'uploaded':
            current_visual.image_generation = None
        snapshot.content['visual'] = current_visual.model_dump(mode='json')
        template = default_template(plan.layout, plan.channel)
        app.state.composer.compose_model(snapshot, background, template)
        with app.state.sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            current = db.get(PieceModel, piece_id)
            current_visual = _visual(current)
            if current_visual.render_request_id != request_id:
                db.rollback()
                return
            previous = current.content.get('visual') or {}
            history = list(current.content.get('visual_history') or [])
            previous_id = (previous.get('final_image') or {}).get('file_id')
            if previous_id and all((item.get('final_image') or {}).get('file_id') != previous_id for item in history):
                history.append(previous)
            snapshot.content['visual_history'] = history
            snapshot.content['visual_needs_recomposition'] = False
            snapshot.content['selected_background'] = background.model_dump(mode='json') if stored_source == 'uploaded' else None
            current.content = snapshot.content
            invalidate_stale(current, app.state.catalog, app.state.rules_loader(),
                             app.state.image_storage, app.state.composer)
            db.commit()
    except (CompositionError, ImageGenerationError) as exc:
        _mark_failed(app, piece_id, request_id, exc.code, str(exc), exc)
    except Exception:
        _mark_failed(app, piece_id, request_id, 'IMAGE_PROCESSING_FAILED', 'Falha no processamento visual.')


def _mark_failed(app, piece_id: str, request_id: str, code: str, message: str, cause=None) -> None:
    with app.state.sessions() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        piece = db.get(PieceModel, piece_id)
        if piece is not None:
            visual = _visual(piece)
            if visual.render_request_id == request_id:
                visual.state = VisualProcessingState.FAILED
                visual.error_code, visual.error_message = code, message
                visual.retry_after_seconds = getattr(cause, 'retry_after_seconds', None)
                previous = VisualMetadata.model_validate(piece.content.get('visual') or {})
                visual.final_image = previous.final_image
                if visual.final_image:
                    visual.composition_source = previous.composition_source
                    visual.background = previous.background
                    visual.product_image = previous.product_image
                    visual.template = previous.template
                if isinstance(cause, ImageGenerationError) and cause.generation_id:
                    visual.image_generation = BackgroundGenerationMetadata(
                        generation_id=cause.generation_id, plan_id=cause.plan_id,
                        model=app.state.background_generator.settings.model,
                        prompt=cause.prompt, created_at=datetime.now(timezone.utc),
                        attempts=cause.attempts, duration_seconds=cause.duration_seconds)
                _save_visual(piece, visual)
        db.commit()
