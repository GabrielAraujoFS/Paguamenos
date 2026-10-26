"""Visual BrandGuard tests use synthetic assets and a fake background generator."""
import hashlib
import json
from copy import deepcopy
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.models import PieceModel
from app.schemas import ImageReference
from app.services.catalog import Catalog, load_rules
from app.services.validation import validate_content
from app.services.visual_validation import validate_visual
from test_render_api import BRIEF, make_app, png


def rendered(client):
    campaign = client.post('/campaigns/generate', json=BRIEF).json()
    piece_id = campaign['pieces'][0]['id']
    assert client.post(f'/pieces/{piece_id}/render', json={}).status_code == 202
    return campaign['id'], piece_id


def validate(client, campaign_id, piece_id):
    piece = client.post(f'/campaigns/{campaign_id}/validate').json()['pieces'][0]
    assert piece['id'] == piece_id
    return piece


def failures(piece):
    return {result['rule_code'] for result in piece['validations'][-1]['results'] if not result['passed']}


def mutate_content(app, piece_id, change):
    with app.state.sessions.begin() as db:
        piece = db.get(PieceModel, piece_id)
        content = deepcopy(piece.content)
        change(content)
        piece.content = content


def mutate_sidecar(app, piece_id, change):
    with app.state.sessions() as db:
        ref = db.get(PieceModel, piece_id).content['visual']['final_image']
    path = app.state.image_storage._path(ref['file_id'], '.json')
    sidecar = json.loads(path.read_text(encoding='utf-8'))
    change(sidecar['metadata'])
    path.write_text(json.dumps(sidecar), encoding='utf-8')


def test_rendered_png_and_compositor_evidence_pass(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        piece = validate(client, campaign_id, piece_id)
        codes = {result['rule_code'] for result in piece['validations'][-1]['results']}
        assert piece['state'] == 'validated'
        assert {'VISUAL_IMAGE_INTEGRITY', 'VISUAL_PNG_FORMAT', 'VISUAL_DIMENSIONS',
                'VISUAL_SAFE_AREA', 'VISUAL_OVERLAP', 'VISUAL_RENDER_INPUTS',
                'VISUAL_PRODUCT_ASSET', 'VISUAL_LOGO_ASSET', 'VISUAL_FONT_ASSET'} <= codes
        assert not {code for code in failures(piece) if code.startswith('VISUAL_')}


def test_wrong_dimensions_and_template_block_approval(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        mutate_content(app, piece_id, lambda content: content['visual']['final_image'].update(width=999))
        piece = validate(client, campaign_id, piece_id)
        assert 'VISUAL_DIMENSIONS' in failures(piece)
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'}).status_code == 409
        mutate_content(app, piece_id, lambda content: content['visual']['template'].update(name='desconhecido'))
        assert 'VISUAL_TEMPLATE' in failures(validate(client, campaign_id, piece_id))


def test_corrupt_png_and_invalid_product_reference(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        with app.state.sessions() as db:
            visual = db.get(PieceModel, piece_id).content['visual']
        path = app.state.image_storage._path(visual['final_image']['file_id'], '.png')
        path.write_bytes(b'broken')
        assert 'VISUAL_IMAGE_INTEGRITY' in failures(validate(client, campaign_id, piece_id))
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'}).status_code == 409

    app, _ = make_app(tmp_path / 'second', monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        mutate_content(app, piece_id, lambda content: content['visual']['product_image'].update(file_id='a' * 32))
        assert 'VISUAL_PRODUCT_ASSET' in failures(validate(client, campaign_id, piece_id))


def test_format_checked_from_pixels_not_filename(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        with app.state.sessions() as db:
            reference = db.get(PieceModel, piece_id).content['visual']['final_image']
        image_path = app.state.image_storage._path(reference['file_id'], '.png')
        buffer = BytesIO()
        Image.new('RGB', (1080, 1350), 'white').save(buffer, format='JPEG')
        image_path.write_bytes(buffer.getvalue())
        digest = hashlib.sha256(buffer.getvalue()).hexdigest()
        sidecar_path = app.state.image_storage._path(reference['file_id'], '.json')
        sidecar = json.loads(sidecar_path.read_text(encoding='utf-8'))
        sidecar['sha256'] = digest
        sidecar['size_bytes'] = len(buffer.getvalue())
        sidecar_path.write_text(json.dumps(sidecar), encoding='utf-8')
        mutate_content(app, piece_id, lambda content: content['visual']['final_image'].update(sha256=digest))
        assert 'VISUAL_PNG_FORMAT' in failures(validate(client, campaign_id, piece_id))


def test_missing_logo_and_divergent_price(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        (tmp_path / 'assets' / 'logos' / 'logo.png').unlink()
        piece = validate(client, campaign_id, piece_id)
        assert 'VISUAL_LOGO_ASSET' in failures(piece)
        mutate_content(app, piece_id, lambda content: content.update(price='1.00'))
        piece = validate(client, campaign_id, piece_id)
        assert {'PRICE_MATCH', 'VISUAL_RENDER_INPUTS'} <= failures(piece)


def test_margins_and_overlap_from_recorded_boxes(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        mutate_sidecar(app, piece_id, lambda metadata: metadata['composition']['boxes']['title'].update(x=0))
        assert 'VISUAL_SAFE_AREA' in failures(validate(client, campaign_id, piece_id))
        mutate_sidecar(app, piece_id, lambda metadata: metadata['composition']['boxes']['price'].update(x=64, y=64))
        assert 'VISUAL_OVERLAP' in failures(validate(client, campaign_id, piece_id))


def test_image_change_after_approval_invalidates_fingerprint(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        piece = validate(client, campaign_id, piece_id)
        first_fingerprint = piece['validations'][-1]['fingerprint']
        approved = client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'})
        assert approved.status_code == 200
        with app.state.sessions() as db:
            reference = ImageReference.model_validate(db.get(PieceModel, piece_id).content['visual']['final_image'])
        app.state.image_storage._path(reference.file_id, '.png').write_bytes(png())
        preview = client.get(f'/pieces/{piece_id}/image')
        assert preview.status_code == 409
        assert client.get(f'/campaigns/{campaign_id}').json()['pieces'][0]['state'] == 'draft'
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'}).status_code == 409
        piece = validate(client, campaign_id, piece_id)
        assert piece['validations'][-1]['fingerprint'] != first_fingerprint
        assert 'VISUAL_IMAGE_INTEGRITY' in failures(piece)


def test_asset_change_after_approval_invalidates_and_legacy_campaign_works(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        validate(client, campaign_id, piece_id)
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'}).status_code == 200
        changed_product = BytesIO()
        Image.new('RGBA', (160, 420), (20, 30, 40, 255)).save(changed_product, format='PNG')
        (tmp_path / 'assets' / 'product_photographs' / 'syn-001.png').write_bytes(changed_product.getvalue())
        assert client.get(f'/campaigns/{campaign_id}').json()['pieces'][0]['state'] == 'draft'
        assert 'VISUAL_PRODUCT_ASSET' in failures(validate(client, campaign_id, piece_id))
        old = client.post('/campaigns/generate', json=BRIEF).json()
        old_id = old['pieces'][0]['id']
        mutate_content(app, old_id, lambda content: content.pop('visual'))
        legacy = validate(client, old['id'], old_id)
        assert legacy['state'] == 'validated'
        assert not any(result['rule_code'].startswith('VISUAL_') for result in legacy['validations'][-1]['results'])


def test_persisted_background_change_invalidates_approval(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign_id, piece_id = rendered(client)
        validate(client, campaign_id, piece_id)
        assert client.post(f'/pieces/{piece_id}/review', json={'decision': 'approved', 'reviewer_id': 'tester'}).status_code == 200
        with app.state.sessions() as db:
            background = db.get(PieceModel, piece_id).content['visual']['background']
        app.state.image_storage._path(background['file_id'], '.png').write_bytes(b'corrupted')
        assert client.get(f'/campaigns/{campaign_id}').json()['pieces'][0]['state'] == 'draft'
        piece = validate(client, campaign_id, piece_id)
        assert 'VISUAL_BACKGROUND_ASSET' in failures(piece)


def test_optional_brand_colors_and_font_rules(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _, piece_id = rendered(client)
        with app.state.sessions() as db:
            content = db.get(PieceModel, piece_id).content
        rules = load_rules()
        rules['brand']['allowed_fonts'] = ['other.ttf']
        codes = {result.rule_code for result in validate_visual(content, app.state.image_storage, app.state.composer, rules)
                 if not result.passed}
        assert 'VISUAL_BRAND_FONT' in codes
        rules['brand']['allowed_fonts'] = ['brand.ttf']
        rules['brand']['allowed_colors'] = ['#FFFFFF']
        codes = {result.rule_code for result in validate_visual(content, app.state.image_storage, app.state.composer, rules)
                 if not result.passed}
        assert 'VISUAL_BRAND_COLORS' in codes


def test_unapproved_pharmaceutical_claim_is_advisory_not_regulatory_clearance():
    product = Catalog().get('syn-001').model_copy(update={'category': 'farmacêutico'})
    content = {'channel': 'feed', 'title': 'Cura para tudo', 'subtitle': 'Produto sintético',
               'cta': 'Conheça', 'disclaimer': 'Campanha fictícia. Dados sintéticos.',
               'product_id': product.id, 'product_name': product.name, 'price': str(product.price),
               'authorized_offer': product.authorized_offer}
    findings = [result for result in validate_content(content, product, load_rules())
                if result.rule_code == 'HEALTH_CLAIM_REVIEW']
    assert findings and not findings[0].passed and findings[0].severity == 'warning'
