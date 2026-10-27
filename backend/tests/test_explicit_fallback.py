import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors
from sqlalchemy import func, select

from app.main import create_app
from app.models import CampaignModel, PieceModel
from app.schemas import Briefing
from app.services.catalog import Catalog, load_rules
from app.services.gemini import GeminiGenerationService
from app.services.generation import GenerationError
from app.services.image_generation import ImageGenerationError, OpenAIImageBackgroundGenerator
from app.services.storage import LocalImageStorage
from app.settings import GenerationConfig, ImageGenerationConfig
from test_render_api import BRIEF, make_app
from test_image_generation import generator as google_generator, plan


def text_app(tmp_path, monkeypatch, status, body=None):
    monkeypatch.setenv('IMAGE_STORAGE_ROOT', str(tmp_path / 'storage'))
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=body or {'error': {'message': 'test-secret'}})
    service = GeminiGenerationService(GenerationConfig(provider='gemini', api_key='test-secret',
        visual_max_attempts=1), load_rules, httpx.MockTransport(handler))
    return create_app(database_url='sqlite:///' + (tmp_path / 'text.db').as_posix(), generator=service), calls


@pytest.mark.parametrize('status', [429, 503])
def test_text_fallback_requires_click_and_persists_origin(tmp_path, monkeypatch, status):
    app, calls = text_app(tmp_path, monkeypatch, status)
    with TestClient(app) as client:
        failed = client.post('/campaigns/generate', json=BRIEF)
        assert failed.status_code == 502
        token = failed.json()['error']['details'][0]['demo_token']
        assert 'test-secret' not in failed.text
        with app.state.sessions() as db:
            assert db.scalar(select(func.count()).select_from(CampaignModel)) == 0
        assert len(calls) == 1
        demo = client.post('/campaigns/generate', params={'demo_token': token}, json=BRIEF)
        assert demo.status_code == 201
        campaign = demo.json()
        assert campaign['generation']['provider'] == 'mock'
        assert campaign['briefing']['objective'] == BRIEF['objective']
        assert campaign['pieces'][0]['price'] == '8.90'
        assert campaign['pieces'][0]['state'] == 'draft'
        assert len(calls) == 1
        assert client.get('/campaigns/' + campaign['id']).json()['generation']['provider'] == 'mock'
        repeated = client.post('/campaigns/generate', params={'demo_token': token}, json=BRIEF)
        assert repeated.json()['id'] == campaign['id']
        with app.state.sessions() as db:
            assert db.scalar(select(func.count()).select_from(CampaignModel)) == 1


def test_offer_rejects_changed_briefing_forgery_and_expiration(tmp_path, monkeypatch):
    app, calls = text_app(tmp_path, monkeypatch, 429)
    with TestClient(app) as client:
        token = client.post('/campaigns/generate', json=BRIEF).json()['error']['details'][0]['demo_token']
        assert client.post('/campaigns/generate', params={'demo_token': token}, json=BRIEF | {'objective': 'Alterado'}).status_code == 409
        assert client.post('/campaigns/generate', params={'demo_token': str(uuid4())}, json=BRIEF).status_code == 409
        app.state.demo_offers.entries[token]['until'] = 0
        assert client.post('/campaigns/generate', params={'demo_token': token}, json=BRIEF).status_code == 409
        assert len(calls) == 1


@pytest.mark.parametrize('status,body', [(400, {}), (403, {}),
    (200, {'promptFeedback': {'blockReason': 'SAFETY'}}), (200, {'candidates': []})])
def test_invalid_or_blocked_requests_never_offer_mock(tmp_path, monkeypatch, status, body):
    app, calls = text_app(tmp_path, monkeypatch, status, body)
    with TestClient(app) as client:
        failed = client.post('/campaigns/generate', json=BRIEF)
        assert failed.status_code == 502
        assert failed.json()['error']['details'] == []
        before = len(calls)
        assert client.post('/campaigns/generate', json=BRIEF | {'channels': []}).status_code == 422
        assert len(calls) == before


def test_gemini_daily_quota_suspends_requests_until_cooldown(tmp_path, monkeypatch):
    app, calls = text_app(tmp_path, monkeypatch, 429, {'error': {'details': [{'quotaId': 'GenerateRequestsPerDay'}]}})
    with TestClient(app) as client:
        for _ in range(2):
            failed = client.post('/campaigns/generate', json=BRIEF)
            assert failed.json()['error']['code'] == 'GENERATION_QUOTA_EXCEEDED'
        assert len(calls) == 1
        app.state.generator.quota.until = 0
        client.post('/campaigns/generate', json=BRIEF)
        assert len(calls) == 2


@pytest.mark.parametrize('code', ['IMAGE_RATE_LIMIT', 'IMAGE_QUOTA_EXCEEDED', 'IMAGE_UNAVAILABLE', 'IMAGE_TIMEOUT'])
def test_visual_failure_preserves_approved_text_then_explicit_local_composition(tmp_path, monkeypatch, code):
    app, fake = make_app(tmp_path, monkeypatch)
    def unavailable(plan):
        fake.calls += 1
        raise ImageGenerationError(code, 'Provedor indisponível')
    fake.generate_with_metadata = unavailable
    with TestClient(app) as client:
        created = client.post('/campaigns/generate', json=BRIEF).json()
        cid, pid = created['id'], created['pieces'][0]['id']
        client.post(f'/campaigns/{cid}/validate')
        approved = client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Teste'}).json()
        client.post(f'/pieces/{pid}/render', json={})
        failed = client.get(f'/pieces/{pid}/render').json()['visual']
        assert failed['state'] == 'failed' and failed['error_code'] == code
        current = client.get(f'/campaigns/{cid}').json()['pieces'][0]
        assert current == approved
        assert fake.calls == 1
        started = client.post(f'/pieces/{pid}/render', json={'use_local_assets': True})
        assert started.status_code == 202
        visual = client.get(f'/pieces/{pid}/render').json()['visual']
        assert visual['state'] == 'composed'
        assert visual['composition_source'] == 'local_assets'
        assert visual['fallback_reason'] == code
        assert visual['image_generation']['model'] == 'local_assets'
        assert fake.calls == 1
        image = client.get(f'/pieces/{pid}/image')
        assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
        assert image.headers['x-creative-composition-source'] == 'local_assets'
        result = client.get(f'/campaigns/{cid}').json()['pieces'][0]
        assert result['title'] == approved['title'] and result['price'] == approved['price']
        assert result['reviews'] == approved['reviews'] and result['validations'] == approved['validations']
        assert result['state'] == 'draft'  # A new successful creative requires revalidation.
        assert client.post(f'/campaigns/{cid}/validate').json()['pieces'][0]['state'] == 'validated'


def test_local_composition_not_allowed_before_failure_or_after_safety_error(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        pid = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]['id']
        assert client.post(f'/pieces/{pid}/render', json={'use_local_assets': True}).status_code == 409
        def blocked(plan):
            raise ImageGenerationError('IMAGE_EMPTY', 'Resposta bloqueada ou vazia')
        fake.generate_with_metadata = blocked
        client.post(f'/pieces/{pid}/render', json={})
        assert client.post(f'/pieces/{pid}/render', json={'use_local_assets': True}).status_code == 409


def test_disabled_provider_can_compose_locally_after_explicit_choice(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    app.state.background_generator = None
    with TestClient(app) as client:
        pid = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]['id']
        assert client.post(f'/pieces/{pid}/render', json={}).json()['visual']['error_code'] == 'IMAGE_PROVIDER_UNCONFIGURED'
        client.post(f'/pieces/{pid}/render', json={'use_local_assets': True})
        assert client.get(f'/pieces/{pid}/render').json()['visual']['composition_source'] == 'local_assets'
        assert fake.calls == 0


def test_failed_regeneration_keeps_previous_png_and_approval(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = client.post('/campaigns/generate', json=BRIEF).json()
        cid, pid = created['id'], created['pieces'][0]['id']
        client.post(f'/pieces/{pid}/render', json={})
        client.post(f'/campaigns/{cid}/validate')
        client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Teste'})
        before = client.get(f'/pieces/{pid}/image').content
        def fail(plan):
            raise ImageGenerationError('IMAGE_RATE_LIMIT', 'Limite atingido')
        fake.generate_with_metadata = fail
        client.post(f'/pieces/{pid}/render', json={'regenerate_background': True})
        assert client.get(f'/pieces/{pid}/image').content == before
        assert client.get(f'/campaigns/{cid}').json()['pieces'][0]['state'] == 'approved'


def test_google_and_openai_daily_quotas_do_not_retry(tmp_path):
    service, client, _ = google_generator(tmp_path, [errors.APIError(429,
        {'error': {'message': 'test-secret', 'details': [{'quotaId': 'ImagesPerDay'}]}})])
    for _ in range(2):
        with pytest.raises(ImageGenerationError) as error:
            service.generate(plan())
        assert error.value.code == 'IMAGE_QUOTA_EXCEEDED'
        assert 'test-secret' not in str(error.value)
    assert len(client.calls) == 1
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={'error': {'code': 'insufficient_quota', 'message': 'test-secret'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        service = OpenAIImageBackgroundGenerator(LocalImageStorage(tmp_path / 'openai'),
            ImageGenerationConfig(provider='openai', model='gpt-image-1-mini', api_key='test-secret'), http)
        for _ in range(2):
            with pytest.raises(ImageGenerationError) as error:
                service.generate(plan())
            assert error.value.code == 'IMAGE_QUOTA_EXCEEDED'
        assert len(calls) == 1
