from fastapi import HTTPException
from app.models import ValidationModel
from app.schemas import PieceState
from app.services.validation import fingerprint, successful, validate_content
from app.services.visual_validation import validate_visual, visual_fingerprint_evidence

def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message, "details": []})

def context(piece, catalog, rules, storage=None, composer=None):
    product = catalog.get(piece.content.get("product_id"))
    evidence = visual_fingerprint_evidence(piece.content, storage, composer)
    # A failed/in-progress render job is operational data, not a changed creative.
    content = {key: value for key, value in piece.content.items() if key != '_render_job'}
    return product, fingerprint(content, product, rules, evidence)

def invalidate_stale(piece, catalog, rules, storage=None, composer=None):
    _, current = context(piece, catalog, rules, storage, composer)
    last = piece.validations[-1] if piece.validations else None
    if piece.state in (PieceState.VALIDATED, PieceState.APPROVED):
        if last is None or last.fingerprint != current or not last.success:
            piece.state = PieceState.DRAFT
    return current

def validate_piece(piece, catalog, rules, storage=None, composer=None):
    product, current = context(piece, catalog, rules, storage, composer)
    results = validate_content(piece.content, product, rules)
    if storage is not None and composer is not None:
        results.extend(validate_visual(piece.content, storage, composer, rules))
    success = successful(results)
    preserve_approval = piece.state == PieceState.APPROVED and bool(piece.validations) and piece.validations[-1].fingerprint == current
    piece.validations.append(ValidationModel(fingerprint=current, success=success,
        results=[r.model_dump(mode="json") for r in results]))
    piece.state = PieceState.APPROVED if success and preserve_approval else (PieceState.VALIDATED if success else PieceState.DRAFT)

def piece_output(piece):
    return {"id": piece.id, "campaign_id": piece.campaign_id, **piece.content,
        "state": piece.state,
        "validations": [{"id": v.id, "created_at": v.created_at, "fingerprint": v.fingerprint,
            "success": v.success, "results": v.results} for v in piece.validations],
        "reviews": [{"id": r.id, "created_at": r.created_at, "decision": r.decision,
            "reviewer_id": r.reviewer_id, "comment": r.comment, "fingerprint": r.fingerprint} for r in piece.reviews]}

def campaign_output(campaign):
    return {"id": campaign.id, "created_at": campaign.created_at, "briefing": {"show_price": True, **campaign.briefing},
        "generation": campaign.pieces[0].content.get('text_generation') if campaign.pieces else None,
        "pieces": [piece_output(p) for p in campaign.pieces]}
