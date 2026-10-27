"""Generate a synthetic, unpublished PNG to exercise PillowComposer locally."""
from io import BytesIO
import os
from pathlib import Path
import shutil

from PIL import Image, ImageDraw

from app.schemas import Piece
from app.services.composition import PillowComposer, default_template
from app.services.storage import LocalImageStorage


def png(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


root = Path(os.getenv("IMAGE_STORAGE_ROOT", Path(__file__).resolve().parents[1] / "creative-assets"))
assets = root / "demo-assets"
for name in ("product_photographs", "logos", "fonts"):
    (assets / name).mkdir(parents=True, exist_ok=True)
font = next((path for path in (Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) if path.is_file()), None)
if font is None:
    raise SystemExit("Fonte demonstrativa ausente no sistema.")
shutil.copyfile(font, assets / "fonts" / "brand.ttf")

product = Image.new("RGBA", (260, 540), (0, 0, 0, 0))
draw = ImageDraw.Draw(product)
draw.rounded_rectangle((25, 20, 235, 520), radius=60, fill=(65, 155, 210, 255), outline="white", width=8)
draw.rounded_rectangle((40, 170, 220, 370), radius=18, fill=(245, 249, 255, 255))
(assets / "product_photographs" / "demo.png").write_bytes(png(product))
logo = Image.new("RGBA", (300, 90), (0, 0, 0, 0))
ImageDraw.Draw(logo).rounded_rectangle((2, 2, 298, 88), radius=20, fill=(20, 70, 170, 255))
(assets / "logos" / "logo.png").write_bytes(png(logo))

storage = LocalImageStorage(root)
background = storage.save(png(Image.new("RGBA", (1600, 1200), (195, 225, 245, 255))),
                          "image/png", kind="background", metadata={"source": "synthetic_demo"})
piece = Piece(id="demo-piece", campaign_id="demo-campaign", channel="feed",
    title="Criativo demonstrativo", subtitle="Composição local com dados sintéticos.",
    cta="Conheça", disclaimer="Demonstração. Não publicar.", product_id="demo",
    product_name="Produto sintético", price="8.90", authorized_offer="Preço sintético de demonstração.",
    state="draft", validations=[], reviews=[])
reference = PillowComposer(storage, assets).compose(piece, background, default_template("produto_centro", "feed"))
preview = root / "demo-creative.png"
preview.write_bytes(storage.get(reference).data)
print(preview)
