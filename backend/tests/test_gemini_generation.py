import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.main import create_app
from app.models import CampaignModel
from app.schemas import Briefing
from app.services.catalog import Catalog, load_rules
from app.services.gemini import GeminiGenerationService
from app.services.generation import GenerationError, configured_generator, MockGenerationService
from app.settings import GenerationConfig


BRIEF = dict(campaign_name='Demo', product_id='syn-001', objective='Apresentar',
             target_audience='Adultos', channels=['feed'])
COPY = dict(channel='feed', title='Conheça Sabonete Brisa', subtitle='Cuidado diário.', cta='Confira')
VISUAL = dict(channel='feed', art_direction='Fundo claro e equilibrado',
    background_prompt='Fundo abstrato em tons suaves com espaço livre', layout='produto_direita',
    palette=['#DDEEFF'], concept='Clareza', visual_style='Minimalista',
    scenario='Estúdio abstrato', lighting='Difusa', decorative_elements=['formas suaves'])


def response_for(pieces=None, finish='STOP'):
    return {'candidates': [{'finishReason': finish, 'content': {'parts': [
        {'text': json.dumps({'pieces': pieces if pieces is not None else [COPY]})}
    ]}}]}


def package_response_for(pieces=None):
    return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
        {'text': json.dumps({'pieces': pieces if pieces is not None else [COPY], 'visual_plans': [VISUAL]})}
    ]}}]}


def provider(handler):
    return GeminiGenerationService(GenerationConfig(provider='gemini', api_key='test-secret'),
                                   load_rules, httpx.MockTransport(handler))


def invoke(service):
    return service.generate(Briefing(**BRIEF), Catalog().get('syn-001'))


def test_request_contains_authorized_context_and_strict_schema():
    def handler(request):
        assert request.headers['x-goog-api-key'] == 'test-secret'
        assert 'test-secret' not in str(request.url)
        payload = json.loads(request.content)
        context = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert context['briefing']['target_audience'] == 'Adultos'
        assert context['authorized_product']['price'] == '8.90'
        assert context['brand_rules']['synthetic'] is True
        schema = payload['generationConfig']['responseJsonSchema']
        assert schema['$defs']['GeneratedText']['additionalProperties'] is False
        assert 'tools' not in payload
        return httpx.Response(200, json=response_for())
    assert invoke(provider(handler))[0].title == COPY['title']


@pytest.mark.parametrize('status,code', [(401, 'GENERATION_AUTH_ERROR'), (403, 'GENERATION_AUTH_ERROR'),
    (429, 'GENERATION_RATE_LIMIT'), (500, 'GENERATION_UNAVAILABLE'), (503, 'GENERATION_UNAVAILABLE')])
def test_provider_errors_are_sanitized(status, code):
    with pytest.raises(GenerationError) as exc:
        invoke(provider(lambda request: httpx.Response(status, text='test-secret upstream detail')))
    assert exc.value.code == code
    assert 'test-secret' not in str(exc.value)


@pytest.mark.parametrize('exception,code', [(httpx.ReadTimeout, 'GENERATION_TIMEOUT'),
                                          (httpx.ConnectError, 'GENERATION_UNAVAILABLE')])
def test_network_failures(exception, code):
    def handler(request):
        raise exception('test-secret', request=request)
    with pytest.raises(GenerationError) as exc:
        invoke(provider(handler))
    assert exc.value.code == code
    assert 'test-secret' not in str(exc.value)


@pytest.mark.parametrize('body', [None, [], {}, {'candidates': []}, {'candidates': [None]},
    response_for() | {'promptFeedback': None},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': ['invalid']}}]}, response_for([]),
    response_for([COPY, COPY]), response_for([COPY | {'channel': 'story'}]),
    response_for([COPY | {'price': '0.01'}]), response_for([COPY | {'title': ''}]),
    response_for(finish='MAX_TOKENS'), response_for(finish='SAFETY'),
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'invalid json'}]}}]}])
def test_invalid_responses(body):
    with pytest.raises(GenerationError) as exc:
        invoke(provider(lambda request: httpx.Response(200, json=body)))
    assert exc.value.code == 'GENERATION_CONTRACT_ERROR'


def test_environment_selection(monkeypatch):
    monkeypatch.delenv('GENERATION_PROVIDER', raising=False)
    monkeypatch.setenv('GENERATION_TIMEOUT_SECONDS', 'invalid-unused')
    assert isinstance(configured_generator(load_rules), MockGenerationService)
    monkeypatch.setenv('GENERATION_PROVIDER', 'unknown')
    with pytest.raises(ValueError, match='GENERATION_PROVIDER'):
        configured_generator(load_rules)
    monkeypatch.setenv('GENERATION_PROVIDER', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='GEMINI_API_KEY'):
        configured_generator(load_rules)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret')
    monkeypatch.setenv('GENERATION_TIMEOUT_SECONDS', '20')
    assert isinstance(configured_generator(load_rules), GeminiGenerationService)
    monkeypatch.setenv('GEMINI_MODEL', '../invalid')
    with pytest.raises(ValueError) as exc:
        configured_generator(load_rules)
    assert 'test-secret' not in str(exc.value)


def test_failure_persists_nothing_and_never_falls_back(tmp_path, caplog):
    service = provider(lambda request: httpx.Response(429, text='test-secret'))
    app = create_app(database_url='sqlite:///' + (tmp_path / 'failure.db').as_posix(), generator=service)
    with TestClient(app) as client:
        assert client.get('/health').json()['generation_provider'] == 'gemini'
        result = client.post('/campaigns/generate', json=BRIEF)
        assert result.status_code == 502
        assert result.json()['error']['code'] == 'GENERATION_RATE_LIMIT'
        with app.state.sessions() as db:
            assert db.scalar(select(func.count()).select_from(CampaignModel)) == 0
    assert 'test-secret' not in caplog.text


@pytest.mark.parametrize('subtitle,rule', [('Por R$ 0,01', 'TEXT_PRICE_MATCH'),
    ('Ganhe 50% de desconto', 'TEXT_OFFER_MATCH'), ('Cura garantida', 'FORBIDDEN_EXPRESSION')])
def test_gemini_copy_still_requires_guardian_and_human(tmp_path, subtitle, rule):
    service = provider(lambda request: httpx.Response(200, json=package_response_for([COPY | {'subtitle': subtitle}])))
    app = create_app(database_url='sqlite:///' + (tmp_path / 'guardian.db').as_posix(), generator=service)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        piece = campaign['pieces'][0]
        assert piece['price'] == '8.90' and piece['state'] == 'draft'
        review_url = f'/pieces/{piece["id"]}/review'
        assert client.post(review_url, json={'decision': 'approved', 'reviewer_id': 'demo'}).status_code == 409
        validated = client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]
        assert any(r['rule_code'] == rule and not r['passed'] for r in validated['validations'][-1]['results'])
        assert client.post(review_url, json={'decision': 'approved', 'reviewer_id': 'demo'}).status_code == 409


def test_generation_does_not_hold_sqlite_write_lock(tmp_path):
    app = None
    def handler(request):
        # A second connection must acquire a write transaction while the provider runs.
        with app.state.engine.connect() as connection:
            connection.execute(text('BEGIN IMMEDIATE'))
            connection.rollback()
        return httpx.Response(200, json=package_response_for())
    app = create_app(database_url='sqlite:///' + (tmp_path / 'lock.db').as_posix(), generator=provider(handler))
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF)
        assert campaign.status_code == 201
        campaign = campaign.json()
        piece = client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]
        assert piece['state'] == 'validated'
        assert client.post(f'/pieces/{piece["id"]}/review', json={
            'decision': 'approved', 'reviewer_id': 'demo'}).json()['state'] == 'approved'
