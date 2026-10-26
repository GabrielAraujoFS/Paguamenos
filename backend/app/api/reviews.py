from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.api.dependencies import session
from app.models import PieceModel, ReviewModel
from app.schemas import Decision, Piece, PieceState, ReviewDecision
from app.services.validation import successful, validate_content
from app.services.visual_validation import validate_visual
from app.services.workflow import fail, invalidate_stale, piece_output
router = APIRouter(tags=["reviews"])

@router.post("/pieces/{piece_id}/review", response_model=Piece)
def review(piece_id: str, decision: ReviewDecision, request: Request, db: Session = Depends(session)):
    piece = db.get(PieceModel, piece_id)
    if piece is None:
        fail(404, "PIECE_NOT_FOUND", "Peça não encontrada.")
    catalog, rules = request.app.state.catalog, request.app.state.rules_loader()
    current = invalidate_stale(piece, catalog, rules, request.app.state.image_storage, request.app.state.composer)
    if decision.decision == Decision.APPROVED:
        last = piece.validations[-1] if piece.validations else None
        checks = validate_content(piece.content, catalog.get(piece.content.get("product_id")), rules)
        checks.extend(validate_visual(piece.content, request.app.state.image_storage,
                                      request.app.state.composer, rules))
        if (piece.state != PieceState.VALIDATED or last is None or not last.success
                or last.fingerprint != current or not successful(checks)):
            return JSONResponse(status_code=409, content={"error": {
                "code": "APPROVAL_BLOCKED", "message": "Aprovação exige validação atual bem-sucedida e estado validated.", "details": []}})
    piece.reviews.append(ReviewModel(**decision.model_dump(mode="json"), fingerprint=current))
    piece.state = decision.decision.value
    db.flush()
    return piece_output(piece)
