import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import campaigns, products, reviews
from app.database import Base, make_engine, make_session_factory
from app.schemas import ErrorResponse
from app.schemas.configuration import parse_rules
from app.services.catalog import Catalog, load_rules
from app.services.generation import MockGenerationService

def local_origins(value: str) -> list[str]:
    origins = [o.strip() for o in value.split(",") if o.strip()]
    for origin in origins:
        parsed = urlparse(origin)
        if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("CORS_ORIGINS aceita apenas origens locais explícitas sem caminho.")
        parsed.port
    return origins

def create_app(database_url=None, generator=None, catalog=None, rules_loader=None, cors_origins=None):
    engine = make_engine(database_url or os.getenv("DATABASE_URL", "sqlite:///./creative_factory.db"))

    @asynccontextmanager
    async def lifespan(application):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    application = FastAPI(title="Creative Factory + Brand Guardian", version="0.1.0",
        description="MVP local com catálogo e regras sintéticos. Revisão humana obrigatória.",
        lifespan=lifespan,
        responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
    application.state.engine = engine
    application.state.sessions = make_session_factory(engine)
    application.state.catalog = catalog if catalog is not None else Catalog()
    source_rules = rules_loader if rules_loader is not None else load_rules

    def configured_rules():
        return parse_rules(source_rules()).model_dump(mode='json')

    # Fail early on malformed local configuration; validate changes on every read.
    configured_rules()
    application.state.rules_loader = configured_rules
    application.state.generator = generator if generator is not None else MockGenerationService(configured_rules)
    application.add_middleware(CORSMiddleware,
        allow_origins=local_origins(cors_origins if cors_origins is not None else os.getenv("CORS_ORIGINS", "http://localhost:5173")),
        allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail), "details": []}
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @application.exception_handler(RequestValidationError)
    async def input_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "INVALID_REQUEST", "message": "Dados de entrada inválidos.", "details": details}})

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "generation_provider": "mock" if isinstance(application.state.generator, MockGenerationService) else "custom"}

    for router in (products.router, campaigns.router, reviews.router):
        application.include_router(router)
    return application

app = create_app()
