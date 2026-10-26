import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import campaigns, images, products, reviews, render, editing
from app.database import Base, make_engine, make_session_factory
from app.schemas import ErrorResponse
from app.schemas.configuration import parse_rules
from app.services.catalog import Catalog, load_rules
from app.services.generation import MockGenerationService, configured_generator
from app.services.gemini import GeminiGenerationService
from app.services.storage import image_storage_from_environment
from app.services.composition import PillowComposer
from app.services.image_generation import GoogleImageBackgroundGenerator, LocalImageBackgroundGenerator, OpenAIImageBackgroundGenerator
from app.settings import ImageGenerationConfig
from app.services.availability import DemoOffers
from app.models import PieceModel
from sqlalchemy import select

def local_origins(value: str) -> list[str]:
    origins = [o.strip() for o in value.split(",") if o.strip()]
    for origin in origins:
        parsed = urlparse(origin)
        if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("CORS_ORIGINS aceita apenas origens locais explícitas sem caminho.")
        parsed.port
    return origins

def create_app(database_url=None, generator=None, catalog=None, rules_loader=None, cors_origins=None,
               background_generator=None, composer=None, assets_root=None):
    engine = make_engine(database_url or os.getenv("DATABASE_URL", "sqlite:///./creative_factory.db"))

    @asynccontextmanager
    async def lifespan(application):
        Base.metadata.create_all(engine)
        # An in-process job cannot survive a service restart; make it retryable.
        with application.state.sessions.begin() as db:
            for piece in db.scalars(select(PieceModel)):
                key = '_render_job' if '_render_job' in piece.content else 'visual'
                visual = piece.content.get(key) or {}
                if visual.get('state') in ('processing', 'background_ready'):
                    piece.content = {**piece.content, key: {**visual, 'state': 'failed',
                        'error_code': 'IMAGE_JOB_INTERRUPTED',
                        'error_message': 'Processamento interrompido; solicite novamente.'}}
        yield
        engine.dispose()

    application = FastAPI(title="Creative Factory + Brand Guardian", version="0.1.0",
        description="MVP local com catálogo e regras sintéticos. Revisão humana obrigatória.",
        lifespan=lifespan,
        # Keep the exported contract stable across Python HTTPStatus wording changes.
        responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
                   422: {"model": ErrorResponse, "description": "Unprocessable Entity"}})
    application.state.engine = engine
    application.state.sessions = make_session_factory(engine)
    application.state.catalog = catalog if catalog is not None else Catalog()
    source_rules = rules_loader if rules_loader is not None else load_rules

    def configured_rules():
        return parse_rules(source_rules()).model_dump(mode='json')

    # Fail early on malformed local configuration; validate changes on every read.
    configured_rules()
    application.state.rules_loader = configured_rules
    application.state.generator = generator if generator is not None else configured_generator(configured_rules)
    application.state.demo_offers = DemoOffers()
    application.state.image_storage = image_storage_from_environment()
    image_config = ImageGenerationConfig.from_environment()
    application.state.background_generator = (background_generator if background_generator is not None else
        GoogleImageBackgroundGenerator(application.state.image_storage, image_config)
        if image_config.provider == 'google' else
        OpenAIImageBackgroundGenerator(application.state.image_storage, image_config)
        if image_config.provider == 'openai' else
        LocalImageBackgroundGenerator(application.state.image_storage, image_config.mock_image_path, 'image/png')
        if image_config.provider == 'mock' else None)
    application.state.composer = composer if composer is not None else PillowComposer(
        application.state.image_storage, assets_root=assets_root)
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
        provider = ('mock' if isinstance(application.state.generator, MockGenerationService) else
                    'gemini' if isinstance(application.state.generator, GeminiGenerationService) else 'custom')
        return {"status": "ok", "generation_provider": provider}

    for router in (products.router, campaigns.router, reviews.router, render.router, images.router, editing.router):
        application.include_router(router)
    return application

app = create_app()
