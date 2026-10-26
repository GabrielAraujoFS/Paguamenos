from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image
from google.genai import errors

from app.schemas import VisualPlan
from app.services.image_generation import GoogleImageBackgroundGenerator, ImageGenerationError
from app.services.storage import LocalImageStorage
from app.settings import ImageGenerationConfig


def png():
    output = BytesIO()
    Image.new('RGB', (400, 500), 'blue').save(output, format='PNG')
    return output.getvalue()


def plan():
    return VisualPlan(channel='feed', art_direction='Estúdio abstrato', layout='produto_centro',
        background_prompt='Fundo azul com espaço livre', palette=['#0000FF'])


def response(data=None, media_type='image/png'):
    parts = [] if data is None else [SimpleNamespace(inline_data=SimpleNamespace(data=data, mime_type=media_type))]
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))],
        usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=100,
                                       total_token_count=120))


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def generator(tmp_path, outcomes, attempts=2):
    storage = LocalImageStorage(tmp_path / 'images')
    client = FakeClient(outcomes)
    settings = ImageGenerationConfig(provider='google', api_key='fake-key', max_attempts=attempts)
    return GoogleImageBackgroundGenerator(storage, settings, client), client, storage


def test_valid_image_is_stored_with_dimensions_usage_and_estimate(tmp_path):
    service, client, storage = generator(tmp_path, [response(png())])
    result = service.generate_with_metadata(plan())
    assert result.reference.width == 400 and result.reference.height == 500
    assert result.metadata.model == 'gemini-3.1-flash-image'
    assert result.metadata.prompt_tokens == 20 and result.metadata.total_tokens == 120
    assert str(result.metadata.estimated_cost_usd) == '0.101'
    assert result.metadata.cost_basis
    assert storage.get(result.reference).metadata['kind'] == 'background'
    assert client.calls[0]['config'].image_config.aspect_ratio == '4:5'
    assert client.calls[0]['config'].image_config.image_size == '2K'
    assert 'Não gerar preços' in client.calls[0]['contents']


@pytest.mark.parametrize('returned,code', [(response(), 'IMAGE_EMPTY'),
    (response(b'bad'), 'IMAGE_FORMAT_INVALID'), (response(png(), 'application/octet-stream'), 'IMAGE_FORMAT_INVALID'),
    (response(png(), 'image/jpeg'), 'IMAGE_FORMAT_INVALID')])
def test_invalid_provider_images_are_rejected(tmp_path, returned, code):
    service, client, _ = generator(tmp_path, [returned])
    with pytest.raises(ImageGenerationError) as error:
        service.generate_with_metadata(plan())
    assert error.value.code == code
    assert len(client.calls) == 1


@pytest.mark.parametrize('status,code', [(401, 'IMAGE_AUTH_ERROR'), (403, 'IMAGE_AUTH_ERROR'),
    (429, 'IMAGE_RATE_LIMIT')])
def test_permanent_api_errors_are_not_retried(tmp_path, status, code):
    service, client, _ = generator(tmp_path, [errors.APIError(status, {'error': {'message': 'secret'}})])
    with pytest.raises(ImageGenerationError) as error:
        service.generate_with_metadata(plan())
    assert error.value.code == code
    assert 'secret' not in str(error.value)
    assert len(client.calls) == 1


def test_timeout_is_bounded(tmp_path):
    timeout = httpx.ReadTimeout('timeout')
    service, client, _ = generator(tmp_path, [timeout, timeout])
    with pytest.raises(ImageGenerationError) as error:
        service.generate_with_metadata(plan())
    assert error.value.code == 'IMAGE_TIMEOUT'
    assert error.value.attempts == 2
    assert len(client.calls) == 2


def test_model_capability_rejects_unsupported_2k():
    with pytest.raises(ValueError, match='somente 1K'):
        ImageGenerationConfig(provider='google', api_key='fake-key',
            model='gemini-3.1-flash-lite-image', image_size='2K')
