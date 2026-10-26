from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import shutil

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.models import PieceModel
from app.schemas import BackgroundGenerationMetadata, VisualMetadata
from app.services.generation import MockGenerationService
from app.services.image_generation import GeneratedBackground, plan_identifier
from app.services.image_generation import ImageGenerationError


BRIEF = dict(campaign_name='Demo', product_id='syn-001', objective='Apresentar',
             target_audience='Adultos', channels=['feed'])


def png(size=(400, 500)):
    output = BytesIO()
    Image.new('RGBA', size, (175, 210, 240, 255)).save(output, format='PNG')
    return output.getvalue()


def font_path():
    for path in (Path('C:/Windows/Fonts/arial.ttf'),
                 Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')):
        if path.is_file():
            return path
    raise RuntimeError('Fonte de teste ausente')


class FakeBackgroundGenerator:
    def __init__(self):
        self.storage = None
        self.calls = 0
        self.settings = SimpleNamespace(model='fake-image')

    def generate_with_metadata(self, plan):
        self.calls += 1
        reference = self.storage.save(png(), 'image/png', kind='background', width=400, height=500)
        return GeneratedBackground(reference, BackgroundGenerationMetadata(
            generation_id=str(uuid4()), plan_id=plan_identifier(plan), model='fake-image',
            prompt=plan.background_prompt, created_at=datetime.now(timezone.utc),
            attempts=1, duration_seconds=.01))


def make_assets(root):
    for directory in ('product_photographs', 'logos', 'fonts'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'product_photographs' / 'syn-001.png').write_bytes(png((160, 420)))
    (root / 'logos' / 'logo.png').write_bytes(png((240, 70)))
    shutil.copyfile(font_path(), root / 'fonts' / 'brand.ttf')


def make_app(tmp_path, monkeypatch, *, assets=True):
    monkeypatch.setenv('IMAGE_STORAGE_ROOT', str(tmp_path / 'storage'))
    root = tmp_path / 'assets'
    if assets:
        make_assets(root)
    fake = FakeBackgroundGenerator()
    app = create_app(database_url='sqlite:///' + (tmp_path / 'campaign.db').as_posix(),
        generator=MockGenerationService(), background_generator=fake, assets_root=root)
    fake.storage = app.state.image_storage
    return app, fake


def test_render_persists_background_and_final_then_allows_review(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        piece = campaign['pieces'][0]
        request_id = str(uuid4())
        started = client.post(f"/pieces/{piece['id']}/render", json={'request_id': request_id})
        assert started.status_code == 202
        status = client.get(f"/pieces/{piece['id']}/render").json()['visual']
        assert status['state'] == 'composed'
        assert status['background']['width'] == 400
        assert status['final_image']['width'] == 1080
        assert status['image_generation']['model'] == 'fake-image'
        assert fake.calls == 1
        assert app.state.image_storage.get(VisualMetadata.model_validate(status).final_image).metadata['kind'] == 'final'
        assert client.post(f"/pieces/{piece['id']}/render", json={'request_id': request_id}).status_code == 200
        assert fake.calls == 1
        with app.state.sessions() as db:
            saved = db.get(PieceModel, piece['id'])
            assert saved.content['price'] == '8.90' and saved.content['product_id'] == 'syn-001'
        validated = client.post(f"/campaigns/{campaign['id']}/validate").json()['pieces'][0]
        assert validated['state'] == 'validated'
        reviewed = client.post(f"/pieces/{piece['id']}/review", json={
            'decision': 'approved', 'reviewer_id': 'demo'}).json()
        assert reviewed['state'] == 'approved'


def test_recompose_reuses_background_without_new_paid_call(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        client.post(f"/pieces/{piece['id']}/render", json={})
        before = client.get(f"/pieces/{piece['id']}/render").json()['visual']
        client.post(f"/pieces/{piece['id']}/render", json={'force': True})
        after = client.get(f"/pieces/{piece['id']}/render").json()['visual']
        assert fake.calls == 1
        assert before['background']['file_id'] == after['background']['file_id']
        assert before['final_image']['file_id'] != after['final_image']['file_id']


def test_reuse_other_piece_same_campaign_and_channel(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        source_id = campaign['pieces'][0]['id']
        client.post(f'/pieces/{source_id}/render', json={})
        with app.state.sessions.begin() as db:
            source = db.get(PieceModel, source_id)
            content = dict(source.content)
            visual = dict(content['visual'])
            visual.update(state='pending', background=None, final_image=None, render_request_id=None)
            content['visual'] = visual
            target = PieceModel(campaign_id=source.campaign_id, position=1, content=content, state='draft')
            db.add(target)
            db.flush()
            target_id = target.id
        started = client.post(f'/pieces/{target_id}/render', json={'source_piece_id': source_id})
        assert started.status_code == 202
        source = client.get(f'/pieces/{source_id}/render').json()['visual']
        target = client.get(f'/pieces/{target_id}/render').json()['visual']
        assert target['state'] == 'composed'
        assert target['background']['file_id'] == source['background']['file_id']
        assert fake.calls == 1


def test_missing_assets_block_before_paid_call_and_preserve_campaign(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch, assets=False)
    with TestClient(app) as client:
        campaign = client.post('/campaigns/generate', json=BRIEF).json()
        piece = campaign['pieces'][0]
        result = client.post(f"/pieces/{piece['id']}/render", json={})
        assert result.status_code == 200
        assert result.json()['visual']['state'] == 'blocked'
        assert result.json()['visual']['error_code'] == 'PRODUCT_ASSET_MISSING'
        assert fake.calls == 0
        assert client.get(f"/campaigns/{campaign['id']}").json()['pieces'][0]['title'] == piece['title']
        make_assets(tmp_path / 'assets')
        assert client.post(f"/pieces/{piece['id']}/render", json={}).status_code == 202
        assert client.get(f"/pieces/{piece['id']}/render").json()['visual']['state'] == 'composed'
        assert fake.calls == 1


def test_duplicate_while_processing_schedules_one_job(tmp_path, monkeypatch):
    from app.api import render
    app, fake = make_app(tmp_path, monkeypatch)
    scheduled = []
    monkeypatch.setattr(render, 'run_visual_render', lambda *args: scheduled.append(args))
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        first = client.post(f"/pieces/{piece['id']}/render", json={})
        second = client.post(f"/pieces/{piece['id']}/render", json={})
        assert first.status_code == second.status_code == 202
        assert first.json()['visual']['render_request_id'] == second.json()['visual']['render_request_id']
        assert len(scheduled) == 1 and fake.calls == 0


def test_provider_failure_preserves_text_and_is_retryable(tmp_path, monkeypatch):
    app, fake = make_app(tmp_path, monkeypatch)
    def fail_once(plan):
        fake.calls += 1
        raise ImageGenerationError('IMAGE_RATE_LIMIT', 'Quota de imagens atingida.')
    fake.generate_with_metadata = fail_once
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        client.post(f"/pieces/{piece['id']}/render", json={})
        status = client.get(f"/pieces/{piece['id']}/render").json()['visual']
        assert status['state'] == 'failed' and status['error_code'] == 'IMAGE_RATE_LIMIT'
        assert client.get(f"/campaigns/{piece['campaign_id']}").json()['pieces'][0]['title'] == piece['title']
        assert fake.calls == 1


def test_render_job_interruption_is_recoverable(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        with app.state.sessions.begin() as db:
            record = db.get(PieceModel, piece['id'])
            record.content = {**record.content, 'visual': {**record.content['visual'], 'state': 'processing'}}
    restarted, _ = make_app(tmp_path, monkeypatch)
    with TestClient(restarted) as client:
        status = client.get(f"/pieces/{piece['id']}/render").json()['visual']
        assert status['state'] == 'failed'
        assert status['error_code'] == 'IMAGE_JOB_INTERRUPTED'


def test_image_delivery_and_preview_headers(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        assert client.get(f"/pieces/{piece['id']}/image").json()['error']['code'] == 'IMAGE_NOT_READY'
        client.post(f"/pieces/{piece['id']}/render", json={})
        result = client.get(f"/pieces/{piece['id']}/image")
        assert result.status_code == 200
        assert result.headers['content-type'] == 'image/png'
        assert result.headers['x-creative-asset-use'] == 'internal-preview'
        assert result.headers['x-creative-approval-state'] == 'draft'
        assert result.headers['cache-control'] == 'private, no-store'
        assert result.content.startswith(b'\x89PNG')


def test_missing_corrupt_and_invalid_image_reference(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        piece = client.post('/campaigns/generate', json=BRIEF).json()['pieces'][0]
        client.post(f"/pieces/{piece['id']}/render", json={})
        with app.state.sessions.begin() as db:
            record = db.get(PieceModel, piece['id'])
            original = dict(record.content['visual'])
            record.content = {**record.content, 'visual': {**original,
                'final_image': {**original['final_image'], 'file_id': '../outside'}}}
        invalid = client.get(f"/pieces/{piece['id']}/image")
        assert invalid.status_code == 409 and invalid.json()['error']['code'] == 'IMAGE_REFERENCE_INVALID'
        with app.state.sessions.begin() as db:
            record = db.get(PieceModel, piece['id'])
            record.content = {**record.content, 'visual': original}
        image_file = app.state.image_storage._path(original['final_image']['file_id'], '.png')
        image_file.write_bytes(b'corrupted')
        corrupt = client.get(f"/pieces/{piece['id']}/image")
        assert corrupt.status_code == 409 and corrupt.json()['error']['code'] == 'IMAGE_CORRUPT'
        image_file.unlink()
        missing = client.get(f"/pieces/{piece['id']}/image")
        assert missing.status_code == 404 and missing.json()['error']['code'] == 'IMAGE_NOT_FOUND'
