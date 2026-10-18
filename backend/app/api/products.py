from fastapi import APIRouter, Request
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
