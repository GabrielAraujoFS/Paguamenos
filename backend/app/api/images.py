"""Serve only the final image referenced by a persisted piece."""
from io import BytesIO

from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.models import PieceModel
from app.schemas import ImageReference, VisualProcessingState
from app.services.workflow import fail, invalidate_stale

router = APIRouter(tags=['render'])


@router.get('/pieces/{piece_id}/image', response_class=Response, responses={
    200: {'description': 'Prévia interna da peça final.', 'content': {
        'image/png': {'schema': {'type': 'string', 'format': 'binary'}}}},
})
def get_piece_image(piece_id: str, request: Request, version_id: str | None = Query(default=None, pattern=r'^[0-9a-f]{32}$')):
    with request.app.state.sessions.begin() as db:
        piece = db.get(PieceModel, piece_id)
        if piece is None:
            fail(404, 'PIECE_NOT_FOUND', 'Peça não encontrada.')
        invalidate_stale(piece, request.app.state.catalog, request.app.state.rules_loader(),
                         request.app.state.image_storage, request.app.state.composer)
        visual = piece.content.get('visual') or {}
        if version_id is not None:
            candidates = [visual, *piece.content.get('visual_history', [])]
            visual = next((item for item in candidates if (item.get('final_image') or {}).get('file_id') == version_id), None)
            if visual is None:
                fail(404, 'IMAGE_NOT_FOUND', 'Esta versão não pertence ao histórico da peça.')
        if visual.get('state') != VisualProcessingState.COMPOSED:
            fail(404, 'IMAGE_NOT_READY', 'A imagem final ainda não está disponível.')
        raw_reference = visual.get('final_image')
        if raw_reference is None:
            fail(404, 'IMAGE_NOT_FOUND', 'Referência da imagem final ausente.')
        try:
            reference = ImageReference.model_validate(raw_reference)
        except (ValidationError, TypeError, ValueError):
            fail(409, 'IMAGE_REFERENCE_INVALID', 'Referência da imagem final inválida.')
        if reference.media_type != 'image/png':
            fail(409, 'IMAGE_REFERENCE_INVALID', 'A imagem final deve ser PNG.')
        try:
            stored = request.app.state.image_storage.get(reference)
        except FileNotFoundError:
            fail(404, 'IMAGE_NOT_FOUND', 'Imagem final não encontrada.')
        except ValueError:
            fail(409, 'IMAGE_CORRUPT', 'Integridade da imagem final não confere.')
        if stored.metadata.get('kind') != 'final':
            fail(409, 'IMAGE_REFERENCE_INVALID', 'Referência não corresponde a uma peça final.')
        try:
            with Image.open(BytesIO(stored.data)) as image:
                if image.format != 'PNG':
                    raise ValueError('Invalid format')
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            fail(409, 'IMAGE_CORRUPT', 'Arquivo PNG inválido.')
        return Response(content=stored.data, media_type='image/png', headers={
            'Cache-Control': 'private, no-store',
            'Content-Disposition': f'inline; filename="preview-{piece.id}.png"',
            'X-Creative-Asset-Use': 'internal-preview',
            'X-Creative-Approval-State': 'historical' if version_id else piece.state,
            'X-Creative-Composition-Source': visual.get('composition_source') or 'unknown',
        })
