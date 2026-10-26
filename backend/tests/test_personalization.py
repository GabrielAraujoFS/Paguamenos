"""Offline personalization integration: isolated SQLite and synthetic images."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.models import CampaignModel, PieceModel
from app.schemas import Briefing, ImageReference
from app.services.catalog import Catalog, load_rules
from app.services.composition import PillowComposer, default_template
from app.services.generation import GenerationError, MockGenerationService
from app.services.publication import published_texts
from app.services.validation import validate_content
from test_render_api import BRIEF, make_app
from test_visual_brandguard import failures, mutate_content


@pytest.mark.parametrize('channel', ['feed', 'story'])
@pytest.mark.parametrize('show_price', [False, True])
@pytest.mark.parametrize('style', ['Minimalista', 'Moderno', 'Acolhedor', 'Vibrante', 'Elegante'])
def test_personalized_render_guardian_and_approval(tmp_path, monkeypatch, channel, show_price, style):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        brief = BRIEF | dict(channels=[channel], theme='Verão', visual_style=style, show_price=show_price)
        response = client.post('/campaigns/generate', json=brief)
        assert response.status_code == 201
        campaign = response.json()
        piece_id = campaign['pieces'][0]['id']
        assert campaign['briefing']['theme'] == 'Verão'
        assert campaign['pieces'][0]['price'] == '8.90'
        assert client.post(f'/pieces/{piece_id}/render', json={}).status_code == 202
        with app.state.sessions() as db:
            content = db.get(PieceModel, piece_id).content
            metadata = app.state.image_storage.get(ImageReference.model_validate(content['visual']['final_image'])).metadata['metadata']['composition']
        assert metadata['visual_style'] == style
        assert metadata['show_price'] == show_price
        assert ('price' in metadata['texts_sent_to_renderer']) == show_price
        assert ('price' in metadata['boxes']) == show_price
        if show_price:
            assert metadata['texts_sent_to_renderer']['price'] == 'R$ 8,90'
        legacy = PillowComposer._layout(default_template(content['visual']['template']['name'], channel))
        assert metadata['boxes']['product']['height'] > legacy['product'].height
        piece = client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]
        assert not failures(piece)
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'test'}).status_code == 200
        mutate_content(app, piece_id, lambda value: value.update(visual_style='Elegante' if style != 'Elegante' else 'Moderno'))
        updated = client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]
        assert updated['state'] == 'draft' and len(updated['reviews']) == 1
        stale = client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]
        assert 'VISUAL_PUBLICATION_PREFERENCES' in failures(stale)


def test_default_hidden_and_legacy_behavior(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        assert campaign['briefing']['show_price'] is False
        assert campaign['pieces'][0]['show_price'] is False
        piece_id = campaign['pieces'][0]['id']
        # Simulate a stored campaign created before personalization existed.
        with app.state.sessions.begin() as db:
            record = db.get(CampaignModel, campaign['id'])
            record.briefing = {key: val for key, val in record.briefing.items() if key not in ('show_price', 'theme', 'visual_style')}
            piece = db.get(PieceModel, piece_id)
            piece.content = {key: val for key, val in piece.content.items() if key not in ('show_price', 'theme', 'visual_style', 'composition_version')}
        legacy = client.get(f'/campaigns/{campaign["id"]}').json()
        assert legacy['briefing']['show_price'] is True
        assert legacy['pieces'][0]['show_price'] is True
        assert legacy['pieces'][0]['composition_version'] == 1
        client.post(f'/pieces/{piece_id}/render', json={})
        assert client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]['state'] == 'validated'


@pytest.mark.parametrize('copy,code', [('R$ 8,90', 'PUBLICATION_PRICE_HIDDEN'), ('R$ 1,00', 'TEXT_PRICE_MATCH'), ('50% de desconto', 'TEXT_OFFER_MATCH')])
def test_commercial_validation_remains_strict(tmp_path, monkeypatch, copy, code):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        results = validate_content(piece | {'title': copy}, Catalog().get('syn-001'), load_rules())
        assert any(result.rule_code == code and not result.passed for result in results)
        for changes, rule in [({'price': '0.01'}, 'PRICE_MATCH'), ({'authorized_offer': 'Oferta inventada'}, 'OFFER_MATCH')]:
            assert any(result.rule_code == rule and not result.passed for result in validate_content(piece | changes, Catalog().get('syn-001'), load_rules()))


def test_monetary_offer_is_internal_when_price_hidden():
    content = dict(title='Olá', subtitle='Descrição', cta='Conheça', disclaimer='Aviso', product_name='Produto', price='8.90', authorized_offer='Por R$ 8,90', show_price=False)
    assert 'offer' not in published_texts(content)
    assert 'price' not in published_texts(content)
    assert published_texts(content | {'authorized_offer': None})['offer'] == ''
    assert 'offer' not in published_texts(content | {'authorized_offer': 'Preço sintético de demonstração.'})
    assert published_texts(content | {'show_price': True})['offer'] == 'Por R$ 8,90'


def test_demo_confirmation_preserves_personalization(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    class Unavailable:
        calls = 0
        def generate(self, briefing, product):
            self.calls += 1
            raise GenerationError('GENERATION_RATE_LIMIT', 'Indisponível temporariamente')
    unavailable = Unavailable()
    app.state.generator = unavailable
    with TestClient(app) as client:
        brief = BRIEF | dict(theme='Um cuidado especial', visual_style='Elegante', show_price=False)
        result = client.post('/campaigns/generate', json=brief)
        assert result.status_code == 502
        assert client.get('/campaigns').json()['total'] == 0
        token = result.json()['error']['details'][0]['demo_token']
        campaign = client.post('/campaigns/generate', params={'demo_token': token}, json=brief).json()
        assert campaign['generation']['provider'] == 'mock'
        assert campaign['briefing']['theme'] == brief['theme']
        assert campaign['pieces'][0]['visual_style'] == 'Elegante'
        assert campaign['pieces'][0]['show_price'] is False
        assert unavailable.calls == 1


def test_local_confirmation_keeps_preferences(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    from app.services.image_generation import ImageGenerationError
    def unavailable(plan):
        raise ImageGenerationError('IMAGE_RATE_LIMIT', 'Cota temporariamente indisponível')
    fake.generate_with_metadata = unavailable
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF | dict(theme='Autocuidado', visual_style='Acolhedor')).json()
        piece_id = campaign['pieces'][0]['id']
        client.post(f'/pieces/{piece_id}/render', json={})
        assert client.get(f'/pieces/{piece_id}/render').json()['visual']['state'] == 'failed'
        client.post(f'/pieces/{piece_id}/render', json={'use_local_assets': True})
        status = client.get(f'/pieces/{piece_id}/render').json()['visual']
        assert status['composition_source'] == 'local_assets' and status['state'] == 'composed'
        content = client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]
        assert content['theme'] == 'Autocuidado' and content['visual_style'] == 'Acolhedor'
        assert content['show_price'] is False
        assert client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]['state'] == 'validated'


def test_mock_copy_unchanged_and_plan_considers_style():
    service = MockGenerationService()
    product = Catalog().get('syn-001')
    before = service.generate(Briefing(**BRIEF), product)
    brief = Briefing(**(BRIEF | dict(theme='Verão', visual_style='Vibrante', show_price=False)))
    package = service.generate_package(brief, product)
    assert package.pieces == before
    assert package.visual_plans[0].visual_style == 'Vibrante'
    assert package.visual_plans[0].concept == 'Leveza e luminosidade'


@pytest.mark.parametrize('updates', [{'theme': ''}, {'theme': 'x' * 121}, {'visual_style': 'Outra'}])
def test_invalid_preferences_rejected(tmp_path, monkeypatch, updates):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert client.post('/campaigns/generate', json=BRIEF | updates).status_code == 422

@pytest.mark.parametrize('package', [False, True])
def test_gemini_receives_preferences_without_weakening_rules(package):
    from app.services.gemini import GeminiGenerationService
    from app.settings import GenerationConfig
    from test_gemini_generation import response_for, package_response_for
    brief = Briefing(**(BRIEF | dict(theme='Dia das Mães', visual_style='Elegante', show_price=False)))
    def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert context['briefing'] == brief.model_dump(mode='json')
        assert context['authorized_product']['price'] == '8.90'
        assert context['brand_rules']['commercial'] == load_rules()['commercial']
        instruction = payload['systemInstruction']['parts'][0]['text']
        assert 'theme' in instruction and 'visual_style' in instruction and 'show_price' in instruction
        assert 'datas, ofertas ou benefícios médicos inventados' in instruction
        assert 'prioridade sobre a' in instruction
        return httpx.Response(200, json=package_response_for() if package else response_for())
    service = GeminiGenerationService(GenerationConfig(provider='gemini', api_key='test-secret'), load_rules, httpx.MockTransport(handler))
    method = service.generate_package if package else service.generate
    method(brief, Catalog().get('syn-001'))


def test_hidden_price_in_generated_copy_rejected_without_demo(tmp_path, monkeypatch):
    from app.schemas import GeneratedText
    app, _ = make_app(tmp_path, monkeypatch)
    class InvalidCopy:
        def generate(self, briefing, product):
            return [GeneratedText(channel='feed', title='Por R$ 8,90', subtitle='Descrição', cta='Confira')]
    app.state.generator = InvalidCopy()
    with TestClient(app) as client:
        response = client.post('/campaigns/generate', json=BRIEF)
        assert response.status_code == 502
        assert response.json()['error']['code'] == 'GENERATION_CONTRACT_ERROR'
        assert response.json()['error']['details'] == []
        assert client.get('/campaigns').json()['total'] == 0
