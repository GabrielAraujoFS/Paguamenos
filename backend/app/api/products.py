from fastapi import APIRouter, Request
from fastapi.responses import Response
from app.services.composition import CompositionError
from app.schemas import Product
from app.services.workflow import fail
router = APIRouter(tags=["products"])

@router.get("/products", response_model=list[Product])
def products(request: Request):
    return request.app.state.catalog.all()

@router.get("/products/{product_id}", response_model=Product)
def product(product_id: str, request: Request):
    found = request.app.state.catalog.get(product_id)
    if found is None:
        fail(404, "PRODUCT_NOT_FOUND", "Produto não encontrado.")
    return found


@router.get('/products/{product_id}/image', response_class=Response, responses={
    200: {'description': 'Fotografia autorizada atual do produto.', 'content': {
        'image/png': {'schema': {'type': 'string', 'format': 'binary'}}}},
})
def product_image(product_id: str, request: Request):
    if request.app.state.catalog.get(product_id) is None:
        fail(404, 'PRODUCT_NOT_FOUND', 'Produto não encontrado.')
    composer = request.app.state.composer
    if not hasattr(composer, 'load_product_photo'):
        fail(404, 'PRODUCT_PHOTO_NOT_FOUND', 'Fotografia do produto indisponível.')
    try:
        version = composer.product_photo_version(product_id)
        data, _ = composer.load_product_photo(product_id, version)
        digest = composer.product_asset_hash(product_id, version)
    except CompositionError as exc:
        fail(404 if exc.code == 'PRODUCT_ASSET_MISSING' else 409, exc.code, str(exc))
    except OSError:
        fail(404, 'PRODUCT_PHOTO_NOT_FOUND', 'Fotografia do produto indisponível.')
    return Response(content=data, media_type='image/png', headers={
        'Cache-Control': 'no-cache', 'ETag': f'"{digest}"',
        'X-Content-Type-Options': 'nosniff',
    })
