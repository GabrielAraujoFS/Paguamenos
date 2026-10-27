"""Marketing workflow with isolated databases/assets and no external AI requests."""
from io import BytesIO
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.main import create_app
from app.models import PieceModel
from app.schemas import ImageReference
from app.services.uploads import MAX_UPLOAD_BYTES
from test_render_api import BRIEF, make_app
from test_visual_brandguard import failures


def image_data(fmt='PNG', size=(600, 400), *, orientation=None):
    stream = BytesIO()
    image = Image.new('RGB', size, (190, 35, 65))
    if fmt == 'JPEG':
        exif = Image.Exif()
        if orientation:
            exif[274] = orientation
        exif[270] = 'Metadata must not persist'
        image.save(stream, format=fmt, exif=exif)
    else:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Comment', 'Metadata must not persist')
        image.save(stream, format=fmt, pnginfo=metadata)
    return stream.getvalue()


def campaign(client):
    response = client.post('/campaigns/generate', json=BRIEF)
    assert response.status_code == 201
    return response.json()


def edit_body(piece, **changes):
    return dict(title=piece['title'], subtitle=piece['subtitle'], cta=piece['cta'], show_price=piece.get('show_price', True),
        visual_style=piece.get('visual_style'), editor_id='Marketing', expected_version=piece.get('edit_version', 0)) | changes


def upload(client, piece, *, data=None, mime='image/png', **params):
    return client.post(f'/pieces/{piece["id"]}/background',
        params=dict(editor_id='Marketing', rights_confirmed=True, expected_version=piece.get('edit_version', 0)) | params,
        content=image_data() if data is None else data, headers={'Content-Type': mime})


def test_edit_recompose_revalidate_human_and_visual_history(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        pid = piece['id']
        client.post(f'/pieces/{pid}/render', json={})
        old_status = client.get(f'/pieces/{pid}/render').json()
        old_ref = old_status['visual']['final_image']
        old_bytes = client.get(f'/pieces/{pid}/image').content
        assert client.post(f'/campaigns/{current["id"]}/validate').json()['pieces'][0]['state'] == 'validated'
        assert client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Human'}).status_code == 200
        unchanged = client.post(f'/pieces/{pid}/edit', json=edit_body(piece)).json()
        assert unchanged['state'] == 'approved' and unchanged['edit_version'] == 0
        assert unchanged['edit_history'] == []
        response = client.post(f'/pieces/{pid}/edit', json=edit_body(piece, title=piece['title'] + '!', subtitle=piece['subtitle'] + ' Confira.', cta='Confira agora', visual_style='Elegante', template='produto_direita', show_price=True))
        assert response.status_code == 200, response.text
        updated = response.json()
        assert updated['state'] == 'draft' and len(updated['reviews']) == 1 and len(updated['validations']) == 1
        assert updated['price'] == piece['price'] and updated['authorized_offer'] == piece['authorized_offer']
        assert updated['title'].endswith('!') and updated['cta'] == 'Confira agora'
        assert updated['visual_needs_recomposition'] is True and updated['edit_version'] == 1
        assert updated['edit_history'][0]['before']['title'] == piece['title']
        assert updated['edit_history'][0]['after']['title'] == updated['title']
        assert client.get(f'/pieces/{pid}/image').content == old_bytes
        checks = client.post(f'/campaigns/{current["id"]}/validate').json()['pieces'][0]
        assert 'VISUAL_RECOMPOSITION_REQUIRED' in failures(checks)
        assert client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Human'}).status_code == 409
        client.post(f'/pieces/{pid}/render', json={'force': True})
        fresh = client.get(f'/campaigns/{current["id"]}').json()['pieces'][0]
        assert fresh['visual_needs_recomposition'] is False
        assert fake.calls == 1  # The previous background was reused.
        assert fresh['visual_history'][0]['final_image']['file_id'] == old_ref['file_id']
        assert client.get(f'/pieces/{pid}/image', params={'version_id': old_ref['file_id']}).content == old_bytes
        assert client.get(f'/pieces/{pid}/image', params={'version_id': '0' * 32}).status_code == 404
        validated = client.post(f'/campaigns/{current["id"]}/validate').json()['pieces'][0]
        assert validated['state'] == 'validated', failures(validated)
        assert client.post(f'/pieces/{pid}/review', json={'decision': 'approved', 'reviewer_id': 'Second human'}).status_code == 200


@pytest.mark.parametrize('changes', [{'price': '0.01'}, {'authorized_offer': '50% de desconto'}, {'product_id': 'syn-002'}, {'product_name': 'Outro'}, {'disclaimer': 'Outro'}, {'title': ''}, {'title': 'x' * 91}, {'template': 'livre'}, {'visual_style': 'Outra'}, {'title': 'Por R$ 8,90'}, {'subtitle': 'Ganhe 50% de desconto'}])
def test_editor_rejects_unauthorized_fields_or_commercial_claims(tmp_path, monkeypatch, changes):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        response = client.post(f'/pieces/{piece["id"]}/edit', json=edit_body(piece, **changes))
        assert response.status_code == 422
        actual = client.get(f'/campaigns/{current["id"]}').json()['pieces'][0]
        assert actual == piece


def test_edit_conflict_and_processing_block(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        body = edit_body(piece, cta='Confira agora')
        assert client.post(f'/pieces/{piece["id"]}/edit', json=body).status_code == 200
        assert client.post(f'/pieces/{piece["id"]}/edit', json=body).status_code == 409
        with app.state.sessions.begin() as db:
            record = db.get(PieceModel, piece['id'])
            record.content = record.content | {'_render_job': {'state': 'processing'}}
        assert client.post(f'/pieces/{piece["id"]}/edit', json=body | {'expected_version': 1}).json()['error']['code'] == 'PIECE_BUSY'
        assert upload(client, piece, expected_version=1).json()['error']['code'] == 'PIECE_BUSY'


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_uploaded_background_used_normalized_and_persistent(tmp_path, monkeypatch, fmt, mime):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        response = upload(client, piece, data=image_data(fmt, orientation=6), mime=mime)
        assert response.status_code == 200, response.text
        updated = response.json()
        reference = updated['selected_background']
        assert updated['visual_needs_recomposition'] is True
        stored = app.state.image_storage.get(ImageReference.model_validate(reference))
        assert stored.metadata['metadata']['source'] == 'uploaded'
        assert stored.metadata['metadata']['rights_confirmed'] is True
        assert stored.metadata['metadata']['uploader_id'] == 'Marketing'
        assert len(stored.metadata['metadata']['original_sha256']) == 64
        image = Image.open(BytesIO(stored.data))
        assert not image.info and not image.getexif()
        assert image.size == ((400, 600) if fmt == 'JPEG' else (600, 400))
        assert fake.calls == 0
        assert 'VISUAL_RECOMPOSITION_REQUIRED' in failures(client.post(f'/campaigns/{current["id"]}/validate').json()['pieces'][0])
        response = client.post(f'/pieces/{piece["id"]}/render', json={'force': True})
        assert response.status_code == 202
        visual = client.get(f'/pieces/{piece["id"]}/render').json()['visual']
        assert visual['state'] == 'composed' and visual['composition_source'] == 'uploaded'
        assert visual['background']['sha256'] == reference['sha256']
        assert visual['image_generation'] is None and fake.calls == 0
        png = client.get(f'/pieces/{piece["id"]}/image')
        assert png.headers['x-creative-composition-source'] == 'uploaded'
        pixel = Image.open(BytesIO(png.content)).getpixel((0, 0))
        assert pixel[:3] == image.convert('RGB').getpixel((0, 0))
        assert client.post(f'/campaigns/{current["id"]}/validate').json()['pieces'][0]['state'] == 'validated'
        # Reopening the actual app against this isolated DB/storage retains the asset.
    with TestClient(app) as restarted:
        piece_again = restarted.get(f'/campaigns/{current["id"]}').json()['pieces'][0]
        assert piece_again['selected_background'] == reference
        assert restarted.get(f'/pieces/{piece["id"]}/image').status_code == 200


@pytest.mark.parametrize('kind', ['invalid', 'svg', 'mismatch', 'small', 'wide', 'pixels', 'large', 'rights', 'identity', 'version', 'animated'])
def test_reject_invalid_uploads_without_changing_piece(tmp_path, monkeypatch, kind):
    app, fake = make_app(tmp_path, monkeypatch)
    kwargs = {}
    if kind == 'invalid': kwargs['data'] = b'\x89PNG\r\n\x1a\ninvalid'
    if kind == 'svg': kwargs.update(data=b'<svg/>', mime='image/svg+xml')
    if kind == 'mismatch': kwargs.update(data=image_data('JPEG'), mime='image/png')
    if kind == 'small': kwargs['data'] = image_data(size=(255, 400))
    if kind == 'wide': kwargs['data'] = image_data(size=(4097, 256))
    if kind == 'pixels': kwargs['data'] = image_data(size=(4000, 4000))
    if kind == 'large': kwargs['data'] = b'x' * (MAX_UPLOAD_BYTES + 1)
    if kind == 'rights': kwargs['rights_confirmed'] = False
    if kind == 'identity': kwargs['editor_id'] = ' '
    if kind == 'version': kwargs['expected_version'] = 12
    if kind == 'animated':
        data = BytesIO()
        Image.new('RGB', (300, 300), 'red').save(data, format='PNG', save_all=True, append_images=[Image.new('RGB', (300, 300), 'blue')], duration=100, loop=0)
        kwargs['data'] = data.getvalue()
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        response = upload(client, piece, **kwargs)
        assert response.status_code == (413 if kind == 'large' else 409 if kind == 'version' else 422)
        assert client.get(f'/campaigns/{current["id"]}').json()['pieces'][0] == piece
        assert fake.calls == 0


def test_uploaded_asset_tampering_blocks_render_and_approval(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        uploaded = upload(client, piece).json()['selected_background']
        app.state.image_storage._path(uploaded['file_id'], '.png').write_bytes(b'corrupt')
        result = client.post(f'/pieces/{piece["id"]}/render', json={'force': True})
        assert result.json()['visual']['state'] == 'blocked'
        assert result.json()['visual']['error_code'] == 'BACKGROUND_MISSING'
        assert client.post(f'/pieces/{piece["id"]}/review', json={'decision': 'approved', 'reviewer_id': 'Human'}).status_code == 409


def test_old_text_only_campaign_can_be_edited_and_uploaded(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        with app.state.sessions.begin() as db:
            record = db.get(PieceModel, piece['id'])
            record.content = {key: val for key, val in record.content.items() if key not in ('visual', 'show_price', 'composition_version', 'visual_style', 'theme')}
        legacy = client.get(f'/campaigns/{current["id"]}').json()['pieces'][0]
        assert legacy['show_price'] is True and legacy['edit_version'] == 0
        changed = client.post(f'/pieces/{piece["id"]}/edit', json=edit_body(legacy, cta='Confira agora')).json()
        assert changed['cta'] == 'Confira agora' and changed['state'] == 'draft'
        assert upload(client, changed).status_code == 200
        assert client.post(f'/pieces/{piece["id"]}/render', json={'force': True}).status_code == 202
        assert client.get(f'/pieces/{piece["id"]}/image').status_code == 200


def test_damaged_upload_metadata_blocks_guardian_without_crashing(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        current = campaign(client)
        piece = current['pieces'][0]
        reference = upload(client, piece).json()['selected_background']
        client.post(f'/pieces/{piece["id"]}/render', json={'force': True})
        path = app.state.image_storage._path(reference['file_id'], '.json')
        sidecar = json.loads(path.read_text(encoding='utf-8'))
        sidecar['metadata'] = None
        path.write_text(json.dumps(sidecar), encoding='utf-8')
        result = client.post(f'/campaigns/{current["id"]}/validate')
        assert result.status_code == 200
        assert 'VISUAL_UPLOADED_BACKGROUND' in failures(result.json()['pieces'][0])
        assert client.post(f'/pieces/{piece["id"]}/review', json={'decision': 'approved', 'reviewer_id': 'Human'}).status_code == 409


@pytest.mark.parametrize('channel', ['feed', 'story'])
def test_versioned_product_positions_preserve_previous_layouts(channel):
    from app.services.composition import PillowComposer, default_template
    content = dict(composition_version=3, show_price=False, authorized_offer='Sem oferta')
    center = PillowComposer.publication_layout(default_template('produto_centro', channel), content)
    right = PillowComposer.publication_layout(default_template('produto_direita', channel), content)
    assert right['product'].x > center['product'].x
    assert right['product'].x + right['product'].width <= 1080 - 64
    old = PillowComposer.publication_layout(default_template('produto_direita', channel), content | {'composition_version': 2})
    assert old['product'].x < right['product'].x
