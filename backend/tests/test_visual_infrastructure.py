import json

import pytest

from app.database import Base, make_engine, make_session_factory
from app.models import CampaignModel, PieceModel
from app.schemas import (
    Briefing, GenerationMetadata, ImageReference, TemplateConfig, VisualMetadata,
    VisualPlan, VisualProcessingState,
)
from app.services.catalog import load_rules
from app.services.generation import MockGenerationService
from app.services.image_generation import LocalImageBackgroundGenerator
from app.services.storage import LocalImageStorage


def test_visual_contracts_round_trip():
    plan = VisualPlan(channel="feed", art_direction="Fundo leve", background_prompt="Formas abstratas", layout="product_right", palette=["#ffffff"])
    template = TemplateConfig(name="feed-demo", channel="feed", width=1080, height=1080, safe_area={"left": 40})
    ref = ImageReference(file_id="a" * 32, media_type="image/png", sha256="b" * 64)
    metadata = VisualMetadata(state=VisualProcessingState.BACKGROUND_READY, plan=plan, template=template, background=ref,
                              generation=GenerationMetadata(provider="local", model="fixture", created_at="2026-10-25T00:00:00Z"))
    restored = VisualMetadata.model_validate_json(metadata.model_dump_json())
    assert restored == metadata
    assert restored.background.file_id == ref.file_id


def test_storage_round_trip_unique_ids_and_metadata(tmp_path):
    storage = LocalImageStorage(tmp_path / "persisted")
    first = storage.save(b"\x89PNG\r\n\x1a\n-one", "image/png", kind="background", metadata={"channel": "feed"})
    second = storage.save(b"\x89PNG\r\n\x1a\n-two", "image/png", kind="final", metadata={})
    assert first.file_id != second.file_id
    loaded = storage.get(first)
    assert loaded.data == b"\x89PNG\r\n\x1a\n-one"
    assert loaded.metadata["kind"] == "background"
    assert json.loads((tmp_path / "persisted" / f"{first.file_id}.json").read_text())["size_bytes"] == len(loaded.data)


def test_storage_rejects_path_traversal(tmp_path):
    storage = LocalImageStorage(tmp_path / "images")
    with pytest.raises(ValueError):
        storage._path("../outside", ".png")
    with pytest.raises(ValueError):
        storage._path("a" * 32, "../../outside")
    with pytest.raises(ValueError):
        storage.save(b"not an image", "image/png", kind="test")


def test_local_background_generator_uses_local_fixture(tmp_path):
    image_path = tmp_path / "demo.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n-demo image")
    storage = LocalImageStorage(tmp_path / "store")
    generator = LocalImageBackgroundGenerator(storage, image_path, "image/png")
    ref = generator.generate(VisualPlan(channel="story", art_direction="Teste", background_prompt="Demo", layout="center"))
    assert storage.get(ref).metadata["metadata"] == {"channel": "story", "source": "local_test"}


def test_existing_campaign_contract_and_mock_remain_compatible(tmp_path):
    from app.schemas import Piece
    from app.services.catalog import Catalog
    from app.services.workflow import campaign_output
    engine = make_engine("sqlite:///" + (tmp_path / "campaign.db").as_posix())
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    briefing = Briefing(campaign_name="Demo", product_id="syn-001", objective="Divulgar",
                        target_audience="Adultos", channels=["feed"])
    product = Catalog().get("syn-001")
    generated = MockGenerationService().generate(briefing, product)[0]
    content = generated.model_dump(mode="json") | {"product_id": product.id, "product_name": product.name,
        "price": str(product.price), "authorized_offer": product.authorized_offer,
        "disclaimer": load_rules()["generation"]["disclaimer"], "visual": VisualMetadata().model_dump(mode="json")}
    with sessions.begin() as db:
        campaign = CampaignModel(briefing=briefing.model_dump(mode="json"))
        campaign.pieces.append(PieceModel(position=0, content=content, state="draft"))
        db.add(campaign)
        db.flush()
        campaign_id = campaign.id
    with sessions() as db:
        saved = db.get(CampaignModel, campaign_id)
        output = campaign_output(saved)
        piece = Piece.model_validate(output["pieces"][0])
        assert piece.title == generated.title
        assert "visual" not in piece.model_dump(mode="json")
        assert saved.pieces[0].content["visual"]["state"] == "pending"
    engine.dispose()
