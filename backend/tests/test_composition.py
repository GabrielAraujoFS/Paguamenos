"""Synthetic images and a system test font; never publication assets."""
from io import BytesIO
from decimal import Decimal
from pathlib import Path
import shutil

import pytest
from PIL import Image

from app.schemas import ImageReference, Piece, TemplateConfig
from app.database import Base, make_engine, make_session_factory
from app.models import CampaignModel, PieceModel
from app.services.composition import CompositionError, PillowComposer, default_template
from app.services.storage import LocalImageStorage


def png(size, color):
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def demo_font_path():
    for path in (Path("C:/Windows/Fonts/arial.ttf"),
                 Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if path.is_file():
            return path
    pytest.skip("Fonte demonstrativa do sistema não encontrada.")


@pytest.fixture
def setup(tmp_path):
    assets = tmp_path / "assets"
    for directory in ("product_photographs", "logos", "fonts", "templates"):
        (assets / directory).mkdir(parents=True)
    (assets / "product_photographs" / "demo.png").write_bytes(png((160, 420), (240, 80, 50, 255)))
    (assets / "logos" / "logo.png").write_bytes(png((240, 70), (20, 70, 170, 255)))
    shutil.copyfile(demo_font_path(), assets / "fonts" / "brand.ttf")
    storage = LocalImageStorage(tmp_path / "storage")
    background = storage.save(png((1600, 900), (190, 210, 235, 255)), "image/png", kind="background")
    piece = Piece(id="piece", campaign_id="campaign", channel="feed", title="Conheça o produto",
        subtitle="Um produto de demonstração.", cta="Confira", disclaimer="Campanha fictícia.",
        product_id="demo", product_name="Produto demonstrativo", price="8.90",
        authorized_offer="Preço de demonstração.", state="draft", validations=[], reviews=[])
    return assets, storage, background, piece


@pytest.mark.parametrize("name", ["produto_centro", "produto_direita"])
@pytest.mark.parametrize("channel,size", [("feed", (1080, 1350)), ("story", (1080, 1920))])
def test_render_templates_and_channels(setup, name, channel, size):
    assets, storage, background, piece = setup
    piece.channel = channel
    template = default_template(name, channel)
    reference = PillowComposer(storage, assets).compose(piece, background, template)
    stored = storage.get(reference)
    assert stored.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert reference.width == size[0] and reference.height == size[1]
    assert Image.open(BytesIO(stored.data)).size == size
    assert stored.metadata["metadata"]["background"]["file_id"] == background.file_id
    assert stored.metadata["metadata"]["product_image"]["file_id"] != background.file_id


@pytest.mark.parametrize("product_size", [(480, 140), (140, 480)])
def test_product_proportions_and_long_text(setup, product_size):
    assets, storage, background, piece = setup
    (assets / "product_photographs" / "demo.png").write_bytes(png(product_size, (240, 80, 50, 255)))
    piece.title = "Conheça este produto de demonstração autorizado"
    piece.subtitle = "Texto de demonstração com palavras suficientes para exigir quebra automática de linha."
    reference = PillowComposer(storage, assets).compose(piece, background, default_template("produto_centro", "feed"))
    assert storage.get(reference).metadata["kind"] == "final"
    rendered = Image.open(BytesIO(storage.get(reference).data)).convert("RGB")
    red_pixels = [(x, y) for y in range(rendered.height) for x in range(rendered.width)
                  if (pixel := rendered.getpixel((x, y)))[0] > 220 and pixel[1] < 120 and pixel[2] < 100]
    product_width = max(x for x, _ in red_pixels) - min(x for x, _ in red_pixels) + 1
    product_height = max(y for _, y in red_pixels) - min(y for _, y in red_pixels) + 1
    assert abs(product_width / product_height - product_size[0] / product_size[1]) < .02


@pytest.mark.parametrize("price", ["8.90", "1234.50", "0.99"])
def test_valid_prices_render(setup, price):
    assets, storage, background, piece = setup
    piece.channel = "story"
    piece.price = Decimal(price)
    assert PillowComposer(storage, assets).compose(piece, background, default_template("produto_direita", "story")).media_type == "image/png"


@pytest.mark.parametrize("missing,code", [("product_photographs/demo.png", "PRODUCT_ASSET_MISSING"),
    ("logos/logo.png", "LOGO_MISSING"), ("fonts/brand.ttf", "FONT_MISSING")])
def test_missing_assets(setup, missing, code):
    assets, storage, background, piece = setup
    (assets / missing).unlink()
    with pytest.raises(CompositionError) as error:
        PillowComposer(storage, assets).compose(piece, background, default_template("produto_centro", "feed"))
    assert error.value.code == code


def test_missing_background(setup):
    assets, storage, _, piece = setup
    nonexistent = ImageReference(file_id="a" * 32, media_type="image/png", sha256="b" * 64)
    with pytest.raises(CompositionError) as error:
        PillowComposer(storage, assets).compose(piece, nonexistent, default_template("produto_centro", "feed"))
    assert error.value.code == "BACKGROUND_MISSING"


def test_invalid_margins_and_collisions(setup):
    assets, storage, background, piece = setup
    composer = PillowComposer(storage, assets)
    template = default_template("produto_centro", "feed")
    template.safe_area = {"left": 1000, "right": 1000, "top": 64, "bottom": 64}
    with pytest.raises(CompositionError) as error:
        composer.compose(piece, background, template)
    assert error.value.code == "LAYOUT_OUT_OF_BOUNDS"
    from app.services.composition import Box
    with pytest.raises(CompositionError) as error:
        composer._check_collisions({"product": Box(0, 0, 100, 100), "price": Box(50, 50, 100, 100)})
    assert error.value.code == "LAYOUT_COLLISION"


def test_text_overflow(setup):
    assets, storage, background, piece = setup
    piece.title = "Palavraininterruptagrande" * 50
    with pytest.raises(CompositionError) as error:
        PillowComposer(storage, assets).compose(piece, background, default_template("produto_centro", "feed"))
    assert error.value.code == "TEXT_OVERFLOW"


def test_compose_model_persists_visual_references(setup, tmp_path):
    assets, storage, background, piece = setup
    engine = make_engine("sqlite:///" + (tmp_path / "visual.db").as_posix())
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    content = piece.model_dump(mode="json", exclude={"id", "campaign_id", "state", "validations", "reviews"})
    with sessions.begin() as db:
        campaign = CampaignModel(briefing={"campaign_name": "Demo"})
        campaign.pieces.append(PieceModel(position=0, content=content, state="draft"))
        db.add(campaign)
        db.flush()
        piece_id = campaign.pieces[0].id
        ref = PillowComposer(storage, assets).compose_model(campaign.pieces[0], background,
            default_template("produto_centro", "feed"))
    with sessions() as db:
        saved = db.get(PieceModel, piece_id)
        visual = saved.content["visual"]
        assert visual["state"] == "composed"
        assert visual["background"]["file_id"] == background.file_id
        assert visual["product_image"]["file_id"]
        assert visual["template"]["name"] == "produto_centro"
        assert visual["final_image"]["sha256"] == ref.sha256
        assert visual["generation"]["created_at"]
        assert storage.get(ref).data.startswith(b"\x89PNG")
    engine.dispose()
