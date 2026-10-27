"""Real provided photographs, isolated storage/DB; no paid providers or historical rewrites."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.models import PieceModel
from app.schemas import ImageReference
from app.services.catalog import Catalog
from app.services.composition import PillowComposer, default_template
from app.services.workflow import context
from test_render_api import BRIEF, make_app
from test_visual_brandguard import failures

PHOTO_ROOT = Path(__file__).parents[1] / 'app/data/assets/product_photographs'
PHOTO_NAMES = {'syn-001': 'sabonete_brisa.png', 'syn-002': 'shampoo_aurora.png',
    'syn-003': 'hidratante_nuvem.png', 'syn-004': 'escova_sorriso.png', 'syn-005': 'algodao_sereno.png', 'syn-006': 'protetor_solar_solara.png'}


def install_photos(assets):
    target = assets / 'product_photographs'
    for name in [*PHOTO_NAMES.values(), 'photos-2026-10.json']:
        shutil.copyfile(PHOTO_ROOT / name, target / name)


@pytest.mark.parametrize('pid,name', list(PHOTO_NAMES.items()))
def test_registered_association_and_original_source_integrity(pid, name):
    entry = json.loads((PHOTO_ROOT / 'photos-2026-10.json').read_text(encoding='utf-8'))['products'][pid]
    assert entry['filename'] == name
    data = (PHOTO_ROOT / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    with Image.open(BytesIO(data)) as image:
        image.verify()
    # Root originals are outside the backend Docker build context, so optional there.
    source = Path(__file__).parents[2] / 'assets/produtos' / name
    if pid == 'syn-006' and not source.is_file():
        source = source.with_suffix('.png.png')
    if source.is_file():
        assert source.read_bytes() == data
    product = Catalog().get(pid)
    assert product.name == {'syn-001': 'Sabonete Brisa', 'syn-002': 'Shampoo Aurora',
        'syn-003': 'Hidratante Nuvem', 'syn-004': 'Escova Sorriso', 'syn-005': 'Algodão Sereno', 'syn-006': 'Protetor Solar Solara'}[pid]


@pytest.mark.parametrize('pid,name', list(PHOTO_NAMES.items()))
@pytest.mark.parametrize('show_price', [False, True])
@pytest.mark.parametrize('channel', ['feed', 'story'])
def test_catalog_image_composition_guardian_and_png_export(tmp_path, monkeypatch, pid, name, show_price, channel):
    app, fake = make_app(tmp_path, monkeypatch)
    install_photos(tmp_path / 'assets')
    with TestClient(app) as client:
        catalog = client.get(f'/products/{pid}').json()
        expected_product = Catalog().get(pid).model_dump(mode='json')
        assert catalog == expected_product  # No changes to names, money or offers.
        image_response = client.get(f'/products/{pid}/image')
        expected = (PHOTO_ROOT / name).read_bytes()
        digest = hashlib.sha256(expected).hexdigest()
        assert image_response.status_code == 200 and image_response.headers['content-type'] == 'image/png'
        assert image_response.content == expected
        assert image_response.headers['etag'] == f'"{digest}"'
        campaign = client.post('/campaigns/generate', json=BRIEF | {'product_id': pid, 'show_price': show_price, 'channels': [channel], 'theme': 'Verão fictício', 'visual_style': 'Minimalista'}).json()
        piece = campaign['pieces'][0]
        assert piece['product_photo_version'] == 'photos-2026-10'
        assert piece['price'] == expected_product['price'] and piece['authorized_offer'] == expected_product['authorized_offer']
        assert client.post(f'/pieces/{piece["id"]}/render', json={}).status_code == 202
        status = client.get(f'/pieces/{piece["id"]}/render').json()['visual']
        assert status['state'] == 'composed'
        assert status['product_image']['sha256'] == digest
        stored_product = app.state.image_storage.get(ImageReference.model_validate(status['product_image']))
        assert stored_product.data == expected  # Entire original photo, not a generated/cropped replacement.
        stored_final = app.state.image_storage.get(ImageReference.model_validate(status['final_image']))
        composition = stored_final.metadata['metadata']['composition']
        assert composition['product_asset_name'] == name
        assert composition['product_presentation'] == 'photo_card'
        assert composition['product_photo_version'] == piece['product_photo_version']
        assert ('price' in composition['texts_sent_to_renderer']) == show_price
        validated = client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]
        assert validated['state'] == 'validated', failures(validated)
        assert not failures(validated)
        approved = client.post(f'/pieces/{piece["id"]}/review', json={'decision': 'approved', 'reviewer_id': 'Photo integration test'})
        assert approved.status_code == 200
        assert client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]['state'] == 'approved'
        png = client.get(f'/pieces/{piece["id"]}/image')
        assert png.status_code == 200 and png.headers['content-type'] == 'image/png'
        with Image.open(BytesIO(png.content)) as canvas:
            assert canvas.size == ((1080, 1350) if channel == 'feed' else (1080, 1920))
            area = composition['boxes']['product']
            with Image.open(BytesIO(expected)) as photo:
                width, height = photo.size
                scale = min((area['width'] - 24) / width, (area['height'] - 24) / height)
                fitted = photo.convert('RGBA').resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
                # Full fitted photograph is present pixel-for-pixel, preserving its scene/proportions.
                x = area['x'] + (area['width'] - fitted.width) // 2
                y = area['y'] + (area['height'] - fitted.height) // 2
                assert canvas.crop((x, y, x + fitted.width, y + fitted.height)).convert('RGB').tobytes() == fitted.convert('RGB').tobytes()
        assert fake.calls == 1


def test_installing_photos_preserves_legacy_approval_fingerprint_and_png(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        pid = campaign['pieces'][0]['id']
        # Truly old persisted pieces have no photo version property.
        with app.state.sessions.begin() as db:
            piece = db.get(PieceModel, pid)
            piece.content = {key: val for key, val in piece.content.items() if key != 'product_photo_version'}
        client.post(f'/pieces/{pid}/render', json={})
        client.post(f'/campaigns/{campaign["id"]}/validate')
        assert client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Legacy reviewer'}).status_code == 200
        old_png = client.get(f'/pieces/{pid}/image').content
        with app.state.sessions() as db:
            piece = db.get(PieceModel, pid)
            original_content = deepcopy(piece.content)
            before = context(piece, app.state.catalog, app.state.rules_loader(), app.state.image_storage, app.state.composer)[1]
        install_photos(tmp_path / 'assets')
        with app.state.sessions() as db:
            piece = db.get(PieceModel, pid)
            after = context(piece, app.state.catalog, app.state.rules_loader(), app.state.image_storage, app.state.composer)[1]
            assert piece.content == original_content and before == after
        saved = client.get(f'/campaigns/{campaign["id"]}').json()['pieces'][0]
        assert saved['state'] == 'approved' and saved['product_photo_version'] == 'legacy'
        assert len(saved['reviews']) == 1 and len(saved['validations']) == 1
        assert client.get(f'/pieces/{pid}/image').content == old_png
        assert client.post(f'/campaigns/{campaign["id"]}/validate').json()['pieces'][0]['state'] == 'approved'
        new = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        assert new['product_photo_version'] == 'photos-2026-10'


@pytest.mark.parametrize('damage', ['photo', 'registry_hash', 'association', 'composition_metadata', 'product_metadata'])
def test_asset_or_association_tampering_blocks_approval(tmp_path, monkeypatch, damage):
    app, _ = make_app(tmp_path, monkeypatch)
    install_photos(tmp_path / 'assets')
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        pid = campaign['pieces'][0]['id']
        client.post(f'/pieces/{pid}/render', json={})
        status = client.get(f'/pieces/{pid}/render').json()['visual']
        if damage == 'photo':
            (tmp_path / 'assets/product_photographs' / PHOTO_NAMES['syn-001']).write_bytes(b'broken')
        elif damage in ('registry_hash', 'association'):
            path = tmp_path / 'assets/product_photographs/photos-2026-10.json'
            registry = json.loads(path.read_text(encoding='utf-8'))
            if damage == 'registry_hash':
                registry['products']['syn-001']['sha256'] = '0' * 64
            else:
                registry['products']['syn-001'] = registry['products']['syn-002']
            path.write_text(json.dumps(registry), encoding='utf-8')
        else:
            target = status['final_image'] if damage == 'composition_metadata' else status['product_image']
            path = app.state.image_storage._path(target['file_id'], '.json')
            metadata = json.loads(path.read_text(encoding='utf-8'))
            if damage == 'composition_metadata':
                metadata['metadata']['composition']['product_asset_name'] = PHOTO_NAMES['syn-002']
            else:
                metadata['metadata'] = None
            path.write_text(json.dumps(metadata), encoding='utf-8')
        result = client.post(f'/campaigns/{campaign["id"]}/validate')
        assert result.status_code == 200
        assert failures(result.json()['pieces'][0]) & {'VISUAL_PRODUCT_ASSET', 'VISUAL_PRODUCT_PHOTO_VERSION'}
        assert client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Human'}).status_code == 409


def test_missing_corrupt_or_unknown_catalog_photo(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    install_photos(tmp_path / 'assets')
    with TestClient(app) as client:
        assert client.get('/products/missing/image').status_code == 404
        path = tmp_path / 'assets/product_photographs' / PHOTO_NAMES['syn-001']
        path.write_bytes(b'broken')
        assert client.get('/products/syn-001/image').status_code == 409
        path.unlink()  # Isolated test file only.
        assert client.get('/products/syn-001/image').status_code == 404
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        result = client.post(f'/pieces/{campaign["pieces"][0]["id"]}/render', json={}).json()
        assert result['visual']['state'] == 'blocked'


def test_solara_authorized_catalog_and_existing_products_unchanged():
    products = Catalog().all()
    assert [p.id for p in products] == [f'syn-{i:03}' for i in range(1, 7)]
    previous = [
        ('Sabonete Brisa', 'higiene', 'Sabonete corporal fictício de uso diário.', '8.90'),
        ('Shampoo Aurora', 'cabelos', 'Shampoo fictício para limpeza dos cabelos.', '24.50'),
        ('Hidratante Nuvem', 'cuidados pessoais', 'Loção corporal fictícia.', '32.90'),
        ('Escova Sorriso', 'higiene bucal', 'Escova dental fictícia de cerdas macias.', '12.00'),
        ('Algodão Sereno', 'acessórios', 'Algodão fictício para cuidados pessoais.', '6.75'),
    ]
    for product, expected in zip(products[:5], previous):
        assert (product.name, product.category, product.description, str(product.price)) == expected
        assert product.authorized_offer == 'Preço sintético de demonstração, sem desconto adicional.'
    assert products[-1].model_dump(mode='json') == {
        'id': 'syn-006', 'name': 'Protetor Solar Solara', 'category': 'Proteção solar',
        'description': 'Protetor solar facial fictício FPS 50, toque seco, 60 g.',
        'price': '39.90', 'authorized_offer': 'Preço sintético de demonstração, sem desconto adicional.',
    }
