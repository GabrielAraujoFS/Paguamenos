"""OpenAI Images API contract tests; all HTTP responses are local mocks."""
import base64
import json
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.schemas import VisualPlan
from app.services.generation import MockGenerationService
from app.services.image_generation import (ImageGenerationError, LocalImageBackgroundGenerator,
    OpenAIImageBackgroundGenerator)
from app.services.storage import LocalImageStorage
from app.settings import ImageGenerationConfig
from test_render_api import BRIEF, make_assets


def png():
    output = BytesIO()
    Image.new('RGB', (1024, 1536), '#d0e5f0').save(output, format='PNG')
    return output.getvalue()


def plan(channel='feed'):
    return VisualPlan(channel=channel, art_direction='Estúdio abstrato', layout='produto_centro',
        background_prompt='Fundo azul com espaço livre', palette=['#d0e5f0'])


def service(tmp_path, handler, attempts=1, timeout=5):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    storage = LocalImageStorage(tmp_path / 'images')
    settings = ImageGenerationConfig(provider='openai', api_key='fake-key', model='gpt-image-1-mini',
        max_attempts=attempts, timeout_seconds=timeout)
    return OpenAIImageBackgroundGenerator(storage, settings, client), storage, client


def image_response(data=None, usage=None):
    item = {'b64_json': base64.b64encode(data).decode()} if data is not None else {}
    return httpx.Response(200, json={'data': [item], 'usage': usage or {}})


def test_openai_png_is_saved_with_prompt_and_usage(tmp_path):
    seen = []
    def handler(request):
        seen.append(request)
        return image_response(png(), {'input_tokens': 12, 'output_tokens': 30, 'total_tokens': 42})
    generator, storage, client = service(tmp_path, handler)
    try:
        result = generator.generate_with_metadata(plan())
        body = json.loads(seen[0].content)
        assert seen[0].url.path == '/v1/images/generations'
        assert seen[0].headers['authorization'] == 'Bearer fake-key'
        assert body['model'] == 'gpt-image-1-mini' and body['output_format'] == 'png'
        assert body['n'] == 1 and body['size'] == '1024x1536'
        assert 'Não gerar preços' in body['prompt']
        assert result.reference.media_type == 'image/png'
        assert (result.reference.width, result.reference.height) == (1024, 1536)
        assert result.metadata.model == 'gpt-image-1-mini'
        assert result.metadata.prompt_tokens == 12 and result.metadata.total_tokens == 42
        assert result.metadata.estimated_cost_usd is None
        assert storage.get(result.reference).data == png()
        assert storage.get(result.reference).metadata['kind'] == 'background'
        assert storage.root == (tmp_path / 'images').resolve()
    finally:
        client.close()


@pytest.mark.parametrize('status,code', [(401, 'IMAGE_AUTH_ERROR'), (403, 'IMAGE_AUTH_ERROR'),
    (429, 'IMAGE_RATE_LIMIT'), (400, 'IMAGE_PROVIDER_ERROR')])
def test_openai_permanent_errors_are_sanitized_and_not_retried(tmp_path, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': 'private provider detail'}})
    generator, _, client = service(tmp_path, handler, attempts=2)
    try:
        with pytest.raises(ImageGenerationError) as error:
            generator.generate_with_metadata(plan())
        assert error.value.code == code and error.value.attempts == 1
        assert 'private provider detail' not in str(error.value)
        assert len(calls) == 1
    finally:
        client.close()


def test_openai_transient_error_retries_only_within_limit(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else image_response(png())
    generator, _, client = service(tmp_path, handler, attempts=2)
    try:
        assert generator.generate_with_metadata(plan()).metadata.attempts == 2
        assert len(calls) == 2
    finally:
        client.close()


def test_openai_timeout_is_reported(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout('secret timeout', request=request)
    generator, _, client = service(tmp_path, handler, attempts=1, timeout=3)
    try:
        with pytest.raises(ImageGenerationError) as error:
            generator.generate_with_metadata(plan())
        assert error.value.code == 'IMAGE_TIMEOUT'
        assert 'secret' not in str(error.value)
        assert error.value.attempts == 1
    finally:
        client.close()


def test_openai_storage_failure_is_sanitized(tmp_path, monkeypatch):
    generator, storage, client = service(tmp_path, lambda request: image_response(png()))
    def no_space(*args, **kwargs):
        raise OSError('private disk path')
    monkeypatch.setattr(storage, 'save', no_space)
    try:
        with pytest.raises(ImageGenerationError) as error:
            generator.generate_with_metadata(plan())
        assert error.value.code == 'IMAGE_STORAGE_ERROR'
        assert 'private disk path' not in str(error.value)
    finally:
        client.close()


@pytest.mark.parametrize('result,code', [(httpx.Response(200, json={'data': []}), 'IMAGE_EMPTY'),
    (httpx.Response(200, json={'data': [{'b64_json': 'not base64'}]}), 'IMAGE_FORMAT_INVALID'),
    (httpx.Response(200, content=b'not json'), 'IMAGE_EMPTY'),
    (image_response(b'not an image'), 'IMAGE_FORMAT_INVALID')])
def test_openai_invalid_images_are_rejected(tmp_path, result, code):
    generator, storage, client = service(tmp_path, lambda request: result)
    try:
        with pytest.raises(ImageGenerationError) as error:
            generator.generate_with_metadata(plan())
        assert error.value.code == code
        assert not list(storage.root.glob('*.png'))
    finally:
        client.close()


def test_provider_selection_requires_own_key_and_preserves_google_and_mock(tmp_path, monkeypatch):
    monkeypatch.setenv('IMAGE_GENERATION_PROVIDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        ImageGenerationConfig.from_environment()
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setenv('IMAGE_MODEL', 'gemini-3.1-flash-image')
    config = ImageGenerationConfig.from_environment()
    assert config.model == 'gpt-image-1-mini'
    monkeypatch.setenv('GENERATION_PROVIDER', 'mock')
    monkeypatch.setenv('IMAGE_STORAGE_ROOT', str(tmp_path / 'store'))
    app = create_app(database_url='sqlite:///' + (tmp_path / 'openai.db').as_posix())
    assert isinstance(app.state.background_generator, OpenAIImageBackgroundGenerator)
    monkeypatch.setenv('IMAGE_GENERATION_PROVIDER', 'google')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    from app.services.image_generation import GoogleImageBackgroundGenerator
    app = create_app(database_url='sqlite:///' + (tmp_path / 'google.db').as_posix())
    assert isinstance(app.state.background_generator, GoogleImageBackgroundGenerator)
    image_path = tmp_path / 'fixture.png'
    image_path.write_bytes(png())
    monkeypatch.setenv('IMAGE_GENERATION_PROVIDER', 'mock')
    monkeypatch.setenv('IMAGE_MOCK_PATH', str(image_path))
    app = create_app(database_url='sqlite:///' + (tmp_path / 'mock.db').as_posix())
    assert isinstance(app.state.background_generator, LocalImageBackgroundGenerator)
    assert app.state.image_storage.get(app.state.background_generator.generate(plan())).data == png()


def test_existing_campaign_render_uses_openai_background_without_changing_copy(tmp_path, monkeypatch):
    monkeypatch.setenv('GENERATION_PROVIDER', 'mock')
    monkeypatch.setenv('IMAGE_GENERATION_PROVIDER', 'disabled')
    monkeypatch.setenv('IMAGE_STORAGE_ROOT', str(tmp_path / 'store'))
    assets = tmp_path / 'assets'
    make_assets(assets)
    app = create_app(database_url='sqlite:///' + (tmp_path / 'campaign.db').as_posix(),
        generator=MockGenerationService(), assets_root=assets)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: image_response(png())))
    app.state.background_generator = OpenAIImageBackgroundGenerator(app.state.image_storage,
        ImageGenerationConfig(provider='openai', api_key='fake-key', model='gpt-image-1-mini', max_attempts=1), client)
    try:
        with TestClient(app) as api:
            campaign = api.post('/campaigns/generate', json=BRIEF).json()
            original = campaign['pieces'][0]
            assert api.post(f"/pieces/{original['id']}/render", json={}).status_code == 202
            visual = api.get(f"/pieces/{original['id']}/render").json()['visual']
            assert visual['state'] == 'composed'
            assert visual['image_generation']['model'] == 'gpt-image-1-mini'
            assert visual['background']['media_type'] == 'image/png'
            saved = api.get(f"/campaigns/{campaign['id']}").json()['pieces'][0]
            assert (saved['title'], saved['price'], saved['product_id']) == (original['title'], original['price'], original['product_id'])
            assert api.get(f"/pieces/{original['id']}/image").headers['content-type'] == 'image/png'
    finally:
        client.close()
