import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.models import PieceModel
from app.schemas import GeneratedText
from app.schemas.configuration import parse_rules
from app.services.catalog import Catalog, load_rules
from app.services.validation import fingerprint, successful, validate_content


BRIEFING = dict(
    campaign_name='Demonstração configurável', product_id='syn-001',
    objective='Apresentar produto fictício', target_audience='Público adulto',
    channels=['feed', 'story', 'banner'],
)


@pytest.fixture
def environment(tmp_path):
    rules = load_rules()
    app = create_app(
        database_url='sqlite:///' + (tmp_path / 'brand.db').as_posix(),
        rules_loader=lambda: copy.deepcopy(rules),
    )
    with TestClient(app) as client:
        yield client, app, rules


def generate(client):
    response = client.post('/campaigns/generate', json=BRIEFING)
    assert response.status_code == 201, response.text
    return response.json()


def validate(client, campaign):
    response = client.post(f'/campaigns/{campaign["id"]}/validate')
    assert response.status_code == 200, response.text
    return response.json()['pieces']


def approve(client, piece_id):
    return client.post(f'/pieces/{piece_id}/review', json={
        'decision': 'approved', 'reviewer_id': 'revisor-sintetico',
    })


def content(product=None, **changes):
    product = product or Catalog().get('syn-001')
    return dict(
        channel='feed', title='Conheça o produto', subtitle='Cuidados do dia a dia',
        cta='Confira', disclaimer='Campanha fictícia. Dados sintéticos.',
        product_id=product.id, product_name=product.name,
        price=str(product.price), authorized_offer=product.authorized_offer,
    ) | changes


def failed(results, code):
    return [r for r in results if r.rule_code == code and not r.passed]


def test_legacy_configuration_defaults():
    legacy = {key: value for key, value in load_rules().items() if key in (
        'version', 'notice', 'allowed_channels', 'required_fields',
        'character_limits', 'required_information',
    )}
    parsed = parse_rules(legacy)
    assert parsed.generation.disclaimer == 'Campanha fictícia. Dados sintéticos.'
    assert parsed.brand.tone_of_voice == 'neutro'
    assert parsed.commercial.text_price_policy == 'catalog_only'
    piece = content()
    assert fingerprint(piece, Catalog().get('syn-001'), legacy) == fingerprint(
        piece, Catalog().get('syn-001'), parsed.model_dump(mode='json'),
    )


@pytest.mark.parametrize('section,changes', [
    ('brand', {'allowed_colors': ['red']}),
    ('brand', {'tone_of_voice': 'desconhecido'}),
    ('severities', {'PRICE_MATCH': 'warning'}),
    ('severities', {'TEXT_OFFER_MATCH': 'info'}),
    ('severities', {'REQUIRED_FIELD': 'warning'}),
    ('commercial', {'text_price_policy': 'ignore'}),
])
def test_rejects_invalid_configuration(section, changes):
    rules = load_rules()
    rules[section].update(changes)
    with pytest.raises(ValidationError):
        parse_rules(rules)


@pytest.mark.parametrize('template', ['{price}', '{brand_name.__class__}', '{cta!r}', '{product_name:100}', '{'])
def test_rejects_unsafe_or_unknown_template_fields(template):
    rules = load_rules()
    rules['generation']['templates']['feed']['title'] = template
    with pytest.raises(ValidationError):
        parse_rules(rules)


@pytest.mark.parametrize('limits', [
    {'feed': {'title': 90, 'subtitle': 240, 'cta': 40}},
    {channel: {'title': 90} for channel in ('feed', 'story', 'banner')},
    {channel: {'title': -1, 'subtitle': 240, 'cta': 40} for channel in ('feed', 'story', 'banner')},
])
def test_rejects_incomplete_or_invalid_limits(limits):
    rules = load_rules()
    rules['character_limits'] = limits
    with pytest.raises(ValidationError):
        parse_rules(rules)


def test_invalid_configuration_fails_before_serving(tmp_path):
    rules = load_rules()
    rules['synthetic'] = False
    with pytest.raises(ValidationError):
        create_app(database_url='sqlite:///' + (tmp_path / 'invalid.db').as_posix(), rules_loader=lambda: rules)


@pytest.mark.parametrize('tone,cta', [('neutro', 'Conheça o produto'), ('acolhedor', 'Conheça com calma'), ('direto', 'Confira agora')])
def test_mock_respects_brand_templates_tone_and_backend_disclaimer(environment, tone, cta):
    client, _, rules = environment
    rules['brand'].update(name='Marca teste', textual_identity='Informação de demonstração.', tone_of_voice=tone)
    rules['generation']['disclaimer'] = 'Campanha fictícia. Dados sintéticos. Aviso configurável.'
    campaign = generate(client)
    assert len(campaign['pieces']) == 3
    feed = campaign['pieces'][0]
    assert feed['title'].startswith('Marca teste:')
    assert feed['subtitle'].endswith('Informação de demonstração.')
    assert feed['cta'] == cta
    assert feed['disclaimer'] == rules['generation']['disclaimer']
    assert feed['price'] == '8.90'
    assert client.get('/health').json()['generation_provider'] == 'mock'
    assert all(piece['state'] == 'validated' for piece in validate(client, campaign))


def test_colors_are_only_configuration_metadata():
    rules = parse_rules(load_rules())
    assert rules.brand.allowed_colors
    results = validate_content(content(), Catalog().get('syn-001'), rules)
    assert not any('COLOR' in r.rule_code or 'VISUAL' in r.rule_code for r in results)


def test_normalized_forbidden_expression_blocks_approval_and_preserves_history(environment):
    client, app, _ = environment
    campaign = generate(client)
    piece_id = campaign['pieces'][0]['id']
    with app.state.sessions.begin() as db:
        piece = db.get(PieceModel, piece_id)
        piece.content = piece.content | {'title': 'CÚRA   GARANTIDA!'}
    piece = validate(client, campaign)[0]
    failures = [r for r in piece['validations'][-1]['results'] if r['rule_code'] == 'FORBIDDEN_EXPRESSION' and not r['passed']]
    assert piece['state'] == 'draft'
    assert failures[0]['severity'] == 'critical'
    assert failures[0]['field'] == 'title'
    assert approve(client, piece_id).status_code == 409
    with app.state.sessions.begin() as db:
        record = db.get(PieceModel, piece_id)
        assert not record.reviews
        record.content = record.content | {'title': 'Cuidados de demonstração'}
    assert validate(client, campaign)[0]['state'] == 'validated'
    assert approve(client, piece_id).status_code == 200
    with app.state.sessions() as db:
        record = db.get(PieceModel, piece_id)
        assert len(record.validations) == 2
        assert not record.validations[0].success
        assert record.validations[1].success
        assert len(record.reviews) == 1
        assert record.reviews[0].fingerprint == record.validations[-1].fingerprint


def test_whole_expression_avoids_partial_word_match():
    rules = load_rules()
    rules['forbidden_expressions'] = [{'expression': 'cura', 'fields': ['title']}]
    results = validate_content(content(title='Procura por cuidados'), Catalog().get('syn-001'), rules)
    assert not failed(results, 'FORBIDDEN_EXPRESSION')


def test_required_information_is_normalized():
    results = validate_content(content(disclaimer='CAMPANHA FICTICIA.  DADOS SINTETICOS.'), Catalog().get('syn-001'), load_rules())
    assert not failed(results, 'REQUIRED_INFORMATION')


def test_required_expression_respects_fields_and_channel():
    rules = load_rules()
    rules['required_expressions'] = [{
        'expression': 'Orientação segura', 'fields': ['subtitle', 'cta'], 'channels': ['feed'],
    }]
    product = Catalog().get('syn-001')
    assert failed(validate_content(content(title='Orientação segura'), product, rules), 'REQUIRED_EXPRESSION')
    assert not failed(validate_content(content(cta='ORIENTACAO   SEGURA!'), product, rules), 'REQUIRED_EXPRESSION')
    assert not failed(validate_content(content(channel='story'), product, rules), 'REQUIRED_EXPRESSION')


@pytest.mark.parametrize('severity', ['warning', 'info'])
def test_noncritical_expression_allows_human_approval(environment, severity):
    client, _, rules = environment
    rules['required_expressions'] = [{
        'expression': 'Mensagem recomendada', 'fields': ['subtitle'], 'severity': severity,
    }]
    campaign = generate(client)
    piece = validate(client, campaign)[0]
    assert piece['state'] == 'validated'
    assert piece['validations'][-1]['success']
    assert any(r['severity'] == severity and not r['passed'] for r in piece['validations'][-1]['results'])
    assert approve(client, piece['id']).json()['state'] == 'approved'


def test_forbidden_warning_is_channel_specific(environment):
    client, _, rules = environment
    rules['forbidden_expressions'] = [{
        'expression': 'Conheça', 'fields': ['cta'], 'channels': ['story'], 'severity': 'warning',
    }]
    pieces = validate(client, generate(client))
    for piece in pieces:
        violations = [r for r in piece['validations'][-1]['results'] if r['rule_code'] == 'FORBIDDEN_EXPRESSION' and not r['passed']]
        assert bool(violations) == (piece['channel'] == 'story')
        assert piece['state'] == 'validated'


def test_limits_can_be_warnings_but_core_fields_cannot_be_disabled():
    rules = load_rules()
    rules['severities']['CHARACTER_LIMIT'] = 'warning'
    rules['required_fields'] = []
    product = Catalog().get('syn-001')
    results = validate_content(content(title='x' * 100), product, rules)
    assert failed(results, 'CHARACTER_LIMIT')[0].severity == 'warning'
    assert successful(results)
    results = validate_content(content(title='', price='0.01', authorized_offer='Inventada'), product, rules)
    assert failed(results, 'REQUIRED_FIELD')[0].severity == 'critical'
    assert failed(results, 'PRICE_MATCH')[0].severity == 'critical'
    assert failed(results, 'OFFER_MATCH')[0].severity == 'critical'
    assert not successful(results)


@pytest.mark.parametrize('text,passes', [
    ('Por R$ 8,90', True), ('Por R$8,90.', True), ('Por R$ 8,90, confira!', True),
    ('R$ 8,90 ou R$ 8,90', True), ('R$ 0,01', False), ('R$ 8,90 ou R$ 0,01', False),
    ('R$ 8.90', False), ('R$ 8,900', False), ('R$ -8,90', False),
    ('R$ 1.234,56', False), ('8,90 reais', False), ('BRL 8.90', False),
    ('US$ 8.90', False), ('€ 8,90', False), ('R$ NaN', False),
])
def test_text_price_syntax_and_catalog_match(text, passes):
    results = validate_content(content(subtitle=text), Catalog().get('syn-001'), load_rules())
    assert (not failed(results, 'TEXT_PRICE_MATCH')) == passes


def test_grouped_thousands_use_decimal():
    product = Catalog().get('syn-001').model_copy(update={'price': Decimal('1234.56')})
    results = validate_content(content(product, subtitle='R$ 1.234,56.'), product, load_rules())
    assert not failed(results, 'TEXT_PRICE_MATCH')


@pytest.mark.parametrize('text', ['R$ 8,90', 'R$ 0,01'])
def test_policy_can_forbid_text_prices(text):
    rules = load_rules()
    rules['commercial']['text_price_policy'] = 'forbid'
    assert failed(validate_content(content(subtitle=text), Catalog().get('syn-001'), rules), 'TEXT_PRICE_MATCH')


@pytest.mark.parametrize('text', ['10% OFF', '20,5 % de economia', 'Frete GRÁTIS', 'PROMOCAO', 'cupom TESTE', 'Leve 2 pague 1', '2 por R$ 8,90'])
def test_unapproved_recognized_offers_are_critical(text):
    results = validate_content(content(subtitle=text), Catalog().get('syn-001'), load_rules())
    failures = failed(results, 'TEXT_OFFER_MATCH')
    assert failures and failures[0].severity == 'critical'


def test_only_complete_catalog_offer_authorizes_bundle():
    product = Catalog().get('syn-001').model_copy(update={'authorized_offer': 'Oferta sintética: leve 2 por R$ 15,00.'})
    rules = load_rules()
    complete = content(product, subtitle=product.authorized_offer)
    assert successful(validate_content(complete, product, rules))
    assert not successful(validate_content(content(product, subtitle='Leve 2 por R$ 15,00'), product, rules))
    assert not successful(validate_content(content(product, subtitle=product.authorized_offer + ' Mais 10% de desconto.'), product, rules))
    rules['commercial']['text_price_policy'] = 'forbid'
    assert failed(validate_content(complete, product, rules), 'TEXT_PRICE_MATCH')


def test_config_change_invalidates_approval_without_erasing_audit(environment):
    client, _, rules = environment
    campaign = generate(client)
    validate(client, campaign)
    piece_id = campaign['pieces'][0]['id']
    assert approve(client, piece_id).status_code == 200
    rules['brand']['textual_identity'] = 'Nova identidade sintética.'
    assert approve(client, piece_id).status_code == 409
    piece = client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]
    assert piece['state'] == 'draft'
    assert len(piece['reviews']) == 1
    assert len(piece['validations']) == 1
    piece = validate(client, campaign)[0]
    assert len(piece['validations']) == 2
    assert piece['validations'][0]['fingerprint'] != piece['validations'][1]['fingerprint']
    assert approve(client, piece_id).status_code == 200


@pytest.mark.parametrize('subtitle,code', [('Por R$ 0,01', 'TEXT_PRICE_MATCH'), ('Hoje com 10% de desconto', 'TEXT_OFFER_MATCH')])
def test_free_text_commercial_failure_blocks_approval(environment, subtitle, code):
    client, _, rules = environment
    rules['generation']['templates']['feed']['subtitle'] = subtitle
    campaign = generate(client)
    piece = validate(client, campaign)[0]
    assert piece['state'] == 'draft'
    assert any(r['rule_code'] == code and not r['passed'] and r['severity'] == 'critical'
               for r in piece['validations'][-1]['results'])
    assert approve(client, piece['id']).status_code == 409


def test_custom_provider_keeps_interface_and_backend_commercial_data(environment):
    client, app, rules = environment

    class Provider:
        def generate(self, briefing, product):
            return [GeneratedText(channel=c, title='Texto de teste', subtitle='Descrição sintética', cta='Confira') for c in briefing.channels]

    app.state.generator = Provider()
    piece = generate(client)['pieces'][0]
    assert piece['title'] == 'Texto de teste'
    assert piece['price'] == '8.90'
    assert piece['authorized_offer'] == Catalog().get('syn-001').authorized_offer
    assert piece['disclaimer'] == rules['generation']['disclaimer']


@pytest.mark.parametrize('bad_result', [None, [{'channel': 'feed', 'title': 'Título', 'subtitle': 'Texto', 'cta': 'Confira', 'price': '0.01'}]])
def test_invalid_provider_output_has_structured_502(environment, bad_result):
    client, app, _ = environment

    class InvalidProvider:
        def generate(self, briefing, product):
            return bad_result

    app.state.generator = InvalidProvider()
    response = client.post('/campaigns/generate', json=BRIEFING)
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'GENERATION_CONTRACT_ERROR'


def test_existing_openapi_and_response_contracts_are_unchanged(environment):
    client, _, _ = environment
    # The committed OpenAPI snapshot describes the original seven endpoints.
    baseline = json.loads((Path(__file__).parents[1] / 'examples' / 'openapi.json').read_text(encoding='utf-8'))
    assert client.get('/openapi.json').json() == baseline
    campaign = generate(client)
    assert set(campaign) == {'id', 'created_at', 'briefing', 'pieces'}
    assert set(campaign['pieces'][0]) == {
        'id', 'campaign_id', 'channel', 'title', 'subtitle', 'cta', 'disclaimer',
        'product_id', 'product_name', 'price', 'authorized_offer', 'state', 'validations', 'reviews',
    }
    assert [p['channel'] for p in campaign['pieces']] == BRIEFING['channels']
