"""Background-only generation; generated pixels never contain commercial assets."""
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Protocol
from uuid import uuid4

import httpx
import requests
from PIL import Image, UnidentifiedImageError
from google import genai
from google.genai import errors, types

from app.schemas import BackgroundGenerationMetadata, Channel, ImageReference, VisualPlan
from app.services.storage import LocalImageStorage
from app.services.visual_planning import NEGATIVE_PROMPT


class ImageGenerationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.generation_id = None
        self.plan_id = None
        self.prompt = None
        self.attempts = None
        self.duration_seconds = None
        super().__init__(message)


@dataclass(frozen=True)
class GeneratedBackground:
    reference: ImageReference
    metadata: BackgroundGenerationMetadata


_ASPECT_RATIOS = {Channel.FEED: '4:5', Channel.STORY: '9:16'}
# GPT Image 1 Mini supports portrait 1024x1536; Pillow crops to the exact template ratio.
_OPENAI_SIZES = {Channel.FEED: '1024x1536', Channel.STORY: '1024x1536'}
_COST_ESTIMATES = {
    ('gemini-3.1-flash-image', '1K'): Decimal('0.067'),
    ('gemini-3.1-flash-image', '2K'): Decimal('0.101'),
    ('gemini-3.1-flash-lite-image', '1K'): Decimal('0.0336'),
}


def plan_identifier(plan: VisualPlan) -> str:
    return sha256(plan.model_dump_json(exclude_none=True).encode('utf-8')).hexdigest()


def background_prompt(plan: VisualPlan) -> str:
    prompt = plan.background_prompt.strip()
    if NEGATIVE_PROMPT.strip() not in prompt:
        prompt += NEGATIVE_PROMPT
    return prompt


class BackgroundGenerator(Protocol):
    def generate(self, plan: VisualPlan) -> ImageReference: ...


class GoogleImageBackgroundGenerator:
    def __init__(self, storage: LocalImageStorage, settings, client=None):
        self.storage, self.settings, self.client = storage, settings, client

    def generate(self, plan: VisualPlan) -> ImageReference:
        return self.generate_with_metadata(plan).reference

    def generate_with_metadata(self, plan: VisualPlan) -> GeneratedBackground:
        if plan.channel not in _ASPECT_RATIOS:
            raise ImageGenerationError('IMAGE_CHANNEL_UNSUPPORTED', 'Canal sem formato de fundo configurado.')
        prompt = background_prompt(plan)
        generation_id = str(uuid4())
        started = monotonic()
        client = self.client or genai.Client(api_key=self.settings.api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(self.settings.timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            for attempt in range(1, self.settings.max_attempts + 1):
                try:
                    response = client.models.generate_content(model=self.settings.model, contents=prompt,
                        config=types.GenerateContentConfig(response_modalities=['IMAGE'],
                            image_config=types.ImageConfig(aspect_ratio=_ASPECT_RATIOS[plan.channel],
                                image_size=self.settings.image_size), automatic_continuation=False))
                    candidates = response.candidates or []
                    parts = candidates[0].content.parts if len(candidates) == 1 and candidates[0].content else []
                    images = [part.inline_data for part in parts if getattr(part, 'inline_data', None)]
                    if len(images) != 1 or not images[0].data:
                        raise ImageGenerationError('IMAGE_EMPTY', 'O provedor não retornou exatamente um fundo.')
                    blob = images[0]
                    media_type = blob.mime_type
                    if media_type not in ('image/png', 'image/jpeg', 'image/webp'):
                        raise ImageGenerationError('IMAGE_FORMAT_INVALID', 'Formato de imagem não suportado.')
                    try:
                        data = bytes(blob.data)
                    except (TypeError, ValueError):
                        raise ImageGenerationError('IMAGE_FORMAT_INVALID', 'Bytes de imagem inválidos.') from None
                    try:
                        with Image.open(BytesIO(data)) as image:
                            image.load()
                            width, height = image.size
                            expected_format = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP'}[media_type]
                            if image.format != expected_format or width > 8192 or height > 8192:
                                raise ValueError('Invalid image')
                    except (UnidentifiedImageError, OSError, ValueError):
                        raise ImageGenerationError('IMAGE_FORMAT_INVALID', 'Bytes de imagem inválidos.') from None
                    usage = getattr(response, 'usage_metadata', None)
                    estimate = _COST_ESTIMATES.get((self.settings.model, self.settings.image_size))
                    metadata = BackgroundGenerationMetadata(generation_id=generation_id,
                        plan_id=plan_identifier(plan), model=self.settings.model, prompt=prompt,
                        created_at=datetime.now(timezone.utc), attempts=attempt,
                        duration_seconds=monotonic() - started,
                        prompt_tokens=getattr(usage, 'prompt_token_count', None),
                        response_tokens=getattr(usage, 'candidates_token_count', None),
                        total_tokens=getattr(usage, 'total_token_count', None),
                        estimated_cost_usd=estimate,
                        cost_basis='estimativa publicada por imagem; não é cobrança confirmada' if estimate is not None else None)
                    reference = self.storage.save(data, media_type, kind='background',
                        metadata=metadata.model_dump(mode='json'), width=width, height=height)
                    return GeneratedBackground(reference, metadata)
                except errors.APIError as exc:
                    status = getattr(exc, 'code', None)
                    if status in (401, 403):
                        raise ImageGenerationError('IMAGE_AUTH_ERROR', 'Acesso ao provedor de imagens não autorizado.') from None
                    if status == 429:
                        raise ImageGenerationError('IMAGE_RATE_LIMIT', 'Quota de imagens atingida.') from None
                    if status not in (408, 500, 502, 503, 504) or attempt == self.settings.max_attempts:
                        raise ImageGenerationError('IMAGE_UNAVAILABLE', 'O provedor de imagens não concluiu a geração.') from None
                except (httpx.TimeoutException, requests.Timeout, TimeoutError):
                    if attempt == self.settings.max_attempts:
                        raise ImageGenerationError('IMAGE_TIMEOUT', 'Tempo de geração de fundo excedido.') from None
                except (httpx.RequestError, requests.RequestException):
                    if attempt == self.settings.max_attempts:
                        raise ImageGenerationError('IMAGE_UNAVAILABLE', 'Não foi possível acessar o provedor de imagens.') from None
        except ImageGenerationError as exc:
            exc.generation_id = generation_id
            exc.plan_id = plan_identifier(plan)
            exc.prompt = prompt
            exc.attempts = attempt
            exc.duration_seconds = monotonic() - started
            raise
        finally:
            if self.client is None:
                client.close()
        raise AssertionError('unreachable')


class OpenAIImageBackgroundGenerator:
    """Generate only a PNG background through OpenAI's Images API."""

    def __init__(self, storage: LocalImageStorage, settings, client: httpx.Client | None = None):
        self.storage, self.settings, self.client = storage, settings, client

    def generate(self, plan: VisualPlan) -> ImageReference:
        return self.generate_with_metadata(plan).reference

    def generate_with_metadata(self, plan: VisualPlan) -> GeneratedBackground:
        if plan.channel not in _OPENAI_SIZES:
            raise ImageGenerationError('IMAGE_CHANNEL_UNSUPPORTED', 'Canal sem formato de fundo configurado.')
        prompt = background_prompt(plan)
        generation_id = str(uuid4())
        started = monotonic()
        attempt = 0
        client = self.client or httpx.Client(timeout=self.settings.timeout_seconds)
        try:
            for attempt in range(1, self.settings.max_attempts + 1):
                try:
                    response = client.post('https://api.openai.com/v1/images/generations',
                        headers={'Authorization': f'Bearer {self.settings.api_key.get_secret_value()}'},
                        json={'model': 'gpt-image-1-mini', 'prompt': prompt, 'n': 1,
                              'size': _OPENAI_SIZES[plan.channel], 'quality': 'medium',
                              'output_format': 'png'}, timeout=self.settings.timeout_seconds)
                    if response.status_code in (401, 403):
                        raise ImageGenerationError('IMAGE_AUTH_ERROR', 'Acesso ao provedor de imagens não autorizado.')
                    if response.status_code == 429:
                        raise ImageGenerationError('IMAGE_RATE_LIMIT', 'Quota de imagens atingida.')
                    if response.status_code != 200:
                        if response.status_code in (408, 500, 502, 503, 504) and attempt < self.settings.max_attempts:
                            continue
                        raise ImageGenerationError('IMAGE_UNAVAILABLE', 'O provedor de imagens não concluiu a geração.')
                    try:
                        payload = response.json()
                    except (ValueError, TypeError):
                        raise ImageGenerationError('IMAGE_EMPTY', 'Resposta de imagem inválida ou vazia.') from None
                    items = payload.get('data') if isinstance(payload, dict) else None
                    encoded = items[0].get('b64_json') if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict) else None
                    if not isinstance(encoded, str) or not encoded:
                        raise ImageGenerationError('IMAGE_EMPTY', 'O provedor não retornou exatamente um fundo.')
                    if len(encoded) > 48 * 1024 * 1024:
                        raise ImageGenerationError('IMAGE_FORMAT_INVALID', 'Imagem retornada excede o limite permitido.')
                    try:
                        data = base64.b64decode(encoded, validate=True)
                        if not data or len(data) > 32 * 1024 * 1024:
                            raise ValueError('Invalid image size')
                        with Image.open(BytesIO(data)) as image:
                            image.load()
                            width, height = image.size
                            if image.format != 'PNG' or width <= 0 or height <= 0 or width > 8192 or height > 8192:
                                raise ValueError('Invalid PNG')
                    except (binascii.Error, UnidentifiedImageError, OSError, ValueError):
                        raise ImageGenerationError('IMAGE_FORMAT_INVALID', 'PNG retornado é inválido.') from None
                    usage = payload.get('usage') if isinstance(payload.get('usage'), dict) else {}
                    def token(name):
                        value = usage.get(name)
                        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
                    metadata = BackgroundGenerationMetadata(generation_id=generation_id,
                        plan_id=plan_identifier(plan), model=self.settings.model, prompt=prompt,
                        created_at=datetime.now(timezone.utc), attempts=attempt,
                        duration_seconds=monotonic() - started,
                        prompt_tokens=token('input_tokens'), response_tokens=token('output_tokens'),
                        total_tokens=token('total_tokens'))
                    try:
                        reference = self.storage.save(data, 'image/png', kind='background',
                            metadata=metadata.model_dump(mode='json'), width=width, height=height)
                    except (OSError, ValueError):
                        raise ImageGenerationError('IMAGE_STORAGE_ERROR', 'Não foi possível armazenar o fundo gerado.') from None
                    return GeneratedBackground(reference, metadata)
                except httpx.TimeoutException:
                    if attempt == self.settings.max_attempts:
                        raise ImageGenerationError('IMAGE_TIMEOUT', 'Tempo de geração de fundo excedido.') from None
                except httpx.RequestError:
                    if attempt == self.settings.max_attempts:
                        raise ImageGenerationError('IMAGE_UNAVAILABLE', 'Não foi possível acessar o provedor de imagens.') from None
        except ImageGenerationError as exc:
            exc.generation_id = generation_id
            exc.plan_id = plan_identifier(plan)
            exc.prompt = prompt
            exc.attempts = attempt
            exc.duration_seconds = monotonic() - started
            raise
        finally:
            if self.client is None:
                client.close()
        raise AssertionError('unreachable')


class LocalImageBackgroundGenerator:
    """Load an explicitly supplied local demo image and store it as a background."""

    def __init__(self, storage: LocalImageStorage, image_path: str | Path, media_type: str):
        self.storage = storage
        self.image_path = Path(image_path).expanduser().resolve(strict=True)
        self.media_type = media_type
        if not self.image_path.is_file():
            raise ValueError("A imagem local de teste precisa ser um arquivo.")

    def generate(self, plan: VisualPlan) -> ImageReference:
        return self.storage.save(self.image_path.read_bytes(), self.media_type,
                                 kind="background", metadata={"source": "local_test", "channel": plan.channel.value})
