"""Deterministic composition of authorized campaign content with Pillow."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.schemas import (Channel, GenerationMetadata, ImageReference, Piece,
                         TemplateConfig, VisualMetadata, VisualProcessingState)
from app.services.storage import LocalImageStorage


class CompositionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class Composer(Protocol):
    def compose(self, piece: Piece, background: ImageReference,
                template: TemplateConfig) -> ImageReference: ...


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def intersects(self, other: "Box") -> bool:
        return self.x < other.x + other.width and other.x < self.x + self.width and self.y < other.y + other.height and other.y < self.y + self.height


TEMPLATE_NAMES = {"produto_centro", "produto_direita"}
CHANNEL_SIZES = {Channel.FEED: (1080, 1350), Channel.STORY: (1080, 1920)}


def default_template(name: str, channel: Channel) -> TemplateConfig:
    if name not in TEMPLATE_NAMES or channel not in CHANNEL_SIZES:
        raise CompositionError("TEMPLATE_UNSUPPORTED", "Template ou canal não suportado.")
    width, height = CHANNEL_SIZES[channel]
    return TemplateConfig(name=name, channel=channel, width=width, height=height,
                          safe_area={"left": 64, "right": 64, "top": 64, "bottom": 64})


class PillowComposer:
    """Uses local PNG product/logo assets; never changes commercial copy."""

    def __init__(self, storage: LocalImageStorage, assets_root: str | Path | None = None,
                 logo_name: str = "logo.png", font_name: str = "brand.ttf"):
        self.storage = storage
        self.assets_root = Path(assets_root or Path(__file__).resolve().parents[1] / "data" / "assets").resolve()
        self.logo_name = logo_name
        self.font_name = font_name

    def _asset(self, directory: str, name: str, code: str) -> Path:
        base = (self.assets_root / directory).resolve()
        target = (base / name).resolve()
        if target.parent != base or not target.is_file():
            raise CompositionError(code, f"Asset obrigatório ausente ou fora da pasta autorizada: {directory}/{name}.")
        return target

    @staticmethod
    def _open_image(data: bytes, code: str) -> Image.Image:
        try:
            with Image.open(BytesIO(data)) as source:
                source.load()
                return source.convert("RGBA")
        except (UnidentifiedImageError, OSError, ValueError):
            raise CompositionError(code, "Imagem obrigatória inválida.") from None

    def _load_png_asset(self, directory: str, name: str, code: str) -> tuple[bytes, Image.Image]:
        data = self._asset(directory, name, code).read_bytes()
        image = self._open_image(data, code)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise CompositionError(code, "O asset obrigatório precisa ser PNG.")
        return data, image

    def check_assets(self, product_id: str) -> None:
        """Fail before any paid call when an authorized composition asset is missing."""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", product_id):
            raise CompositionError("PRODUCT_ASSET_MISSING", "ID do produto inválido para asset.")
        self._load_png_asset("product_photographs", f"{product_id}.png", "PRODUCT_ASSET_MISSING")
        self._load_png_asset("logos", self.logo_name, "LOGO_MISSING")
        font = self._asset("fonts", self.font_name, "FONT_MISSING")
        try:
            ImageFont.truetype(str(font), 20)
        except OSError:
            raise CompositionError("FONT_INVALID", "Fonte obrigatória inválida.") from None

    @staticmethod
    def _check_box(box: Box, template: TemplateConfig, margins: dict[str, int]):
        if (box.width <= 0 or box.height <= 0 or box.x < margins["left"] or box.y < margins["top"]
                or box.x + box.width > template.width - margins["right"]
                or box.y + box.height > template.height - margins["bottom"]):
            raise CompositionError("LAYOUT_OUT_OF_BOUNDS", "Elemento ultrapassa a área segura do canvas.")

    @staticmethod
    def _check_collisions(boxes: dict[str, Box]):
        names = list(boxes)
        for index, name in enumerate(names):
            for other in names[index + 1:]:
                if boxes[name].intersects(boxes[other]):
                    raise CompositionError("LAYOUT_COLLISION", f"Elementos obrigatórios se sobrepõem: {name} e {other}.")

    @staticmethod
    def _layout(template: TemplateConfig) -> dict[str, Box]:
        margins = {side: template.safe_area.get(side, 64) for side in ("left", "right", "top", "bottom")}
        if any(key not in margins for key in template.safe_area):
            raise CompositionError("TEMPLATE_INVALID", "safe_area aceita somente left, right, top e bottom.")
        w, h = template.width, template.height
        left, right, top, bottom = (margins[side] for side in ("left", "right", "top", "bottom"))
        usable_w, usable_h = w - left - right, h - top - bottom
        if usable_w <= 0 or usable_h <= 0:
            raise CompositionError("LAYOUT_OUT_OF_BOUNDS", "Margens maiores que o canvas.")
        title_h, subtitle_h, product_name_h = int(usable_h * .115), int(usable_h * .105), int(usable_h * .06)
        logo_h, disclaimer_h = int(usable_h * .075), int(usable_h * .043)
        cta_h, offer_h, price_h = int(usable_h * .050), int(usable_h * .060), int(usable_h * .090)
        gap = max(12, int(usable_h * .012))
        footer_y = h - bottom
        logo = Box(left, footer_y - logo_h, usable_w, logo_h)
        disclaimer = Box(left, logo.y - gap - disclaimer_h, usable_w, disclaimer_h)
        cta = Box(left, disclaimer.y - gap - cta_h, usable_w, cta_h)
        offer = Box(left, cta.y - gap - offer_h, usable_w, offer_h)
        price = Box(left, offer.y - gap - price_h, usable_w, price_h)
        title = Box(left, top, usable_w, title_h)
        subtitle = Box(left, title.y + title.height + gap, usable_w, subtitle_h)
        product_name = Box(left, subtitle.y + subtitle.height + gap, usable_w, product_name_h)
        body_top, body_bottom = product_name.y + product_name.height + gap, price.y - gap
        if template.name == "produto_centro":
            product = Box(left + int(usable_w * .13), body_top, int(usable_w * .74), body_bottom - body_top)
        else:
            product = Box(left + int(usable_w * .48), body_top, int(usable_w * .52), body_bottom - body_top)
            price = Box(left, price.y, int(usable_w * .43), price.height)
        boxes = {"title": title, "subtitle": subtitle, "product_name": product_name, "product": product, "price": price,
                 "offer": offer, "cta": cta, "disclaimer": disclaimer, "logo": logo}
        for box in boxes.values():
            PillowComposer._check_box(box, template, margins)
        PillowComposer._check_collisions(boxes)
        return boxes

    @staticmethod
    def _fit_lines(draw: ImageDraw.ImageDraw, text: str, font_path: Path, box: Box,
                   min_size: int, max_size: int) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
        for size in range(max_size, min_size - 1, -1):
            font = ImageFont.truetype(str(font_path), size)
            lines = []
            for paragraph in text.splitlines() or [""]:
                line = ""
                for word in paragraph.split():
                    candidate = f"{line} {word}".strip()
                    if draw.textbbox((0, 0), candidate, font=font, anchor="lt")[2] <= box.width:
                        line = candidate
                    else:
                        if not line:
                            break
                        lines.append(line)
                        line = word
                        if draw.textbbox((0, 0), line, font=font, anchor="lt")[2] > box.width:
                            break
                else:
                    lines.append(line)
                    continue
                break
            else:
                line_height = int(size * 1.2)
                if lines and len(lines) * line_height <= box.height:
                    return font, lines, line_height
        raise CompositionError("TEXT_OVERFLOW", "Texto autorizado não cabe na área reservada.")

    @staticmethod
    def _paste_contained(canvas: Image.Image, image: Image.Image, box: Box):
        scale = min(box.width / image.width, box.height / image.height)
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        resized = image.resize(size, Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (box.x + (box.width - size[0]) // 2,
                                         box.y + (box.height - size[1]) // 2))

    def compose(self, piece: Piece, background: ImageReference,
                template: TemplateConfig) -> ImageReference:
        if template.name not in TEMPLATE_NAMES or template.channel != piece.channel or CHANNEL_SIZES.get(piece.channel) != (template.width, template.height):
            raise CompositionError("TEMPLATE_UNSUPPORTED", "Template, canal ou dimensões não suportados.")
        if template.min_font_size > template.max_font_size:
            raise CompositionError("TEMPLATE_INVALID", "Limites de fonte inválidos.")
        boxes = self._layout(template)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", piece.product_id):
            raise CompositionError("PRODUCT_ASSET_MISSING", "ID do produto inválido para asset.")
        try:
            bg = self._open_image(self.storage.get(background).data, "BACKGROUND_MISSING")
        except (FileNotFoundError, ValueError):
            raise CompositionError("BACKGROUND_MISSING", "Fundo não encontrado ou inválido.") from None
        product_data, product = self._load_png_asset("product_photographs", f"{piece.product_id}.png", "PRODUCT_ASSET_MISSING")
        logo_data, logo = self._load_png_asset("logos", self.logo_name, "LOGO_MISSING")
        font_path = self._asset("fonts", self.font_name, "FONT_MISSING")
        try:
            ImageFont.truetype(str(font_path), template.min_font_size)
        except OSError:
            raise CompositionError("FONT_INVALID", "Fonte obrigatória inválida.") from None
        canvas = ImageOps.fit(bg, (template.width, template.height), method=Image.Resampling.LANCZOS, centering=(.5, .5))
        draw = ImageDraw.Draw(canvas, "RGBA")
        for name in ("title", "subtitle", "product_name", "price", "offer", "cta", "disclaimer"):
            box = boxes[name]
            draw.rounded_rectangle((box.x, box.y, box.x + box.width, box.y + box.height),
                                   radius=12, fill=(255, 255, 255, 224))
        self._paste_contained(canvas, product, boxes["product"])
        self._paste_contained(canvas, logo, boxes["logo"])
        texts = {"title": piece.title, "subtitle": piece.subtitle, "product_name": piece.product_name,
                 "price": f"R$ {piece.price:.2f}".replace(".", ","),
                 "offer": piece.authorized_offer, "cta": piece.cta, "disclaimer": piece.disclaimer}
        for name, value in texts.items():
            box = boxes[name]
            inner = Box(box.x + 12, box.y + 6, box.width - 24, box.height - 12)
            if inner.width <= 0 or inner.height <= 0:
                raise CompositionError("LAYOUT_OUT_OF_BOUNDS", "Área de texto insuficiente.")
            font, lines, line_height = self._fit_lines(draw, value, font_path, inner,
                template.min_font_size, template.max_font_size if name in ("title", "price") else min(template.max_font_size, 48))
            for index, line in enumerate(lines):
                draw.text((inner.x, inner.y + index * line_height), line, font=font, fill=(36, 92, 114, 255), anchor="lt")
        output = BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        product_ref = self.storage.save(product_data, "image/png", kind="product_asset",
                                        metadata={"product_id": piece.product_id}, width=product.width, height=product.height)
        created_at = datetime.now(timezone.utc).isoformat()
        return self.storage.save(output.getvalue(), "image/png", kind="final",
            metadata={"background": background.model_dump(mode="json"),
                      "product_image": product_ref.model_dump(mode="json"),
                      "template": template.model_dump(mode="json"), "state": VisualProcessingState.COMPOSED.value,
                      "created_at": created_at, "piece_id": piece.id,
                      "composition": {
                          "boxes": {name: vars(box) for name, box in boxes.items()},
                          "texts_sent_to_renderer": texts,
                          "product_id": piece.product_id,
                          "product_sha256": hashlib.sha256(product_data).hexdigest(),
                          "logo_name": self.logo_name,
                          "logo_sha256": hashlib.sha256(logo_data).hexdigest(),
                          "font_name": self.font_name,
                          "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
                          "text_color": "#245C72", "panel_color": "#FFFFFF",
                      }},
            width=template.width, height=template.height)

    def compose_model(self, piece_model, background: ImageReference, template: TemplateConfig) -> ImageReference:
        """Compose an ORM PieceModel and update its JSON; caller commits the session."""
        piece = Piece.model_validate({"id": piece_model.id, "campaign_id": piece_model.campaign_id,
            **piece_model.content, "state": piece_model.state, "validations": [], "reviews": []})
        result = self.compose(piece, background, template)
        metadata = self.storage.get(result).metadata["metadata"]
        visual = VisualMetadata.model_validate(piece_model.content.get("visual") or {})
        visual.state = VisualProcessingState.COMPOSED
        visual.background = background
        visual.product_image = ImageReference.model_validate(metadata["product_image"])
        visual.template = template
        visual.final_image = result
        visual.composed_at = datetime.fromisoformat(metadata["created_at"])
        if visual.generation is None:
            visual.generation = GenerationMetadata(provider="pillow", model="PillowComposer",
                                                   created_at=metadata["created_at"])
        piece_model.content = {**piece_model.content, "visual": visual.model_dump(mode="json")}
        return result
