"""Deterministic checks of render artifacts and recorded compositor inputs.

The recorded text proves what the trusted compositor received, not what OCR
would find in the pixels. Multimodal analysis may supplement this in future.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Protocol

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.schemas import ImageReference, Severity, TemplateConfig, ValidationResult
from app.schemas.configuration import parse_rules
from app.services.publication import published_texts
from app.services.composition import Box, CHANNEL_SIZES, TEMPLATE_NAMES, CompositionError, PillowComposer, default_template


class AdvisoryVisualAnalyzer(Protocol):
    """Future multimodal findings are advisory and never replace deterministic checks."""
    def analyze(self, image: bytes, content: dict) -> list[ValidationResult]: ...


def _result(code: str, field: str, passed: bool, message: str, severity=Severity.CRITICAL):
    return ValidationResult(rule_code=code, field=field, passed=passed, severity=severity,
                            message=('OK: ' if passed else 'Falha: ') + message)


def _asset_hash(composer: PillowComposer, directory: str, name: str) -> str:
    try:
        return hashlib.sha256(composer._asset(directory, name, 'ASSET_MISSING').read_bytes()).hexdigest()
    except (CompositionError, OSError, ValueError):
        return 'missing'


def _product_hash(composer, content):
    try:
        return composer.product_asset_hash(str(content.get('product_id') or ''), content.get('product_photo_version', 'legacy'))
    except (CompositionError, OSError, ValueError):
        return 'missing'


def _stored_hashes(storage, raw_reference) -> tuple[str, str]:
    try:
        reference = ImageReference.model_validate(raw_reference)
        suffix = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[reference.media_type]
        data = storage._path(reference.file_id, suffix).read_bytes()
        sidecar = storage._path(reference.file_id, '.json').read_bytes()
        return hashlib.sha256(data).hexdigest(), hashlib.sha256(sidecar).hexdigest()
    except (ValidationError, KeyError, TypeError, ValueError, OSError):
        return 'missing', 'missing'


def visual_fingerprint_evidence(content: dict, storage, composer) -> dict:
    """Hash current bytes, including broken/missing assets, for stale approval detection."""
    visual = content.get('visual') or {}
    if not isinstance(visual, dict) or visual.get('state') != 'composed' or storage is None or composer is None:
        return {}
    image_hash, sidecar_hash = _stored_hashes(storage, visual.get('final_image'))
    product_image_hash, product_sidecar_hash = _stored_hashes(storage, visual.get('product_image'))
    background_hash, background_sidecar_hash = _stored_hashes(storage, visual.get('background'))
    return {
        'final_image_bytes': image_hash,
        'final_image_sidecar': sidecar_hash,
        'product_image_bytes': product_image_hash,
        'product_image_sidecar': product_sidecar_hash,
        'background_bytes': background_hash,
        'background_sidecar': background_sidecar_hash,
        'product_asset': _product_hash(composer, content),
        'logo_asset': _asset_hash(composer, 'logos', composer.logo_name),
        'font_asset': _asset_hash(composer, 'fonts', composer.font_name),
    }


def validate_visual(content: dict, storage, composer, rules) -> list[ValidationResult]:
    visual = content.get('visual') or {}
    pending = content.get('visual_needs_recomposition', False)
    pending_result = _result('VISUAL_RECOMPOSITION_REQUIRED', 'visual.final_image', False, 'Conteúdo ou fundo alterado: recomponha a peça antes de validar e aprovar.')
    if not isinstance(visual, dict) or visual.get('state') != 'composed':
        if pending:
            return [pending_result]
        # Old campaigns and text-only drafts retain their existing validation behavior.
        return []
    results = [pending_result] if pending else []
    def check(code, field, passed, message, severity=Severity.CRITICAL):
        results.append(_result(code, field, bool(passed), message, severity))

    try:
        reference = ImageReference.model_validate(visual.get('final_image'))
        stored = storage.get(reference)
    except (ValidationError, TypeError, ValueError, OSError, KeyError):
        check('VISUAL_IMAGE_INTEGRITY', 'visual.final_image', False,
              'PNG final ausente, referência inválida ou SHA-256 divergente.')
        return results
    check('VISUAL_IMAGE_INTEGRITY', 'visual.final_image', stored.metadata.get('kind') == 'final',
          f'Arquivo final e SHA-256 conferidos: {reference.sha256[:12]}…')
    try:
        with Image.open(BytesIO(stored.data)) as image:
            image.load()
            actual_format, size = image.format, image.size
    except (UnidentifiedImageError, OSError, ValueError):
        actual_format, size = None, None
    check('VISUAL_PNG_FORMAT', 'visual.final_image', reference.media_type == 'image/png' and actual_format == 'PNG',
          f'Formato do arquivo: {actual_format or "ilegível"}; esperado PNG.')
    expected_size = CHANNEL_SIZES.get(content.get('channel'))
    check('VISUAL_DIMENSIONS', 'visual.final_image', expected_size is not None and size == expected_size
          and (reference.width, reference.height) == expected_size,
          f'Dimensões observadas: {size}; esperadas: {expected_size}.')
    sidecar = stored.metadata.get('metadata') or {}
    if not isinstance(sidecar, dict):
        sidecar = {}
    check('VISUAL_COMPOSITOR_METADATA', 'visual.final_image',
          sidecar.get('piece_id') is not None and sidecar.get('state') == 'composed'
          and sidecar.get('product_image') == visual.get('product_image')
          and sidecar.get('background') == visual.get('background'),
          'Metadados de peça, produto e fundo devem corresponder às referências persistidas.')
    try:
        background_ref = ImageReference.model_validate(visual.get('background'))
        background_stored = storage.get(background_ref)
        background_ok = background_stored.metadata.get('kind') == 'background'
    except (ValidationError, TypeError, ValueError, OSError, KeyError):
        background_ok = False
    upload = background_stored.metadata.get('metadata') if background_ok else None
    upload = upload if isinstance(upload, dict) else {}
    if background_ok and (upload.get('source') == 'uploaded' or visual.get('composition_source') == 'uploaded'):
        check('VISUAL_UPLOADED_BACKGROUND', 'visual.background',
              visual.get('composition_source') == 'uploaded' and upload.get('source') == 'uploaded' and upload.get('rights_confirmed') is True
              and bool(str(upload.get('uploader_id') or '').strip())
              and isinstance(upload.get('original_sha256'), str) and len(upload['original_sha256']) == 64,
              'Fundo enviado deve manter origem, autorização declarada, identificação e hash original.')
    check('VISUAL_BACKGROUND_ASSET', 'visual.background', background_ok,
          'Fundo persistido deve existir, corresponder ao SHA-256 e ser identificado como fundo.')

    template_data = visual.get('template')
    try:
        template = TemplateConfig.model_validate(template_data)
        canonical = default_template(template.name, template.channel)
        template_ok = template.model_dump() == canonical.model_dump() and template.name in TEMPLATE_NAMES
        template_ok = template_ok and sidecar.get('template') == template.model_dump(mode='json')
        template_ok = template_ok and (visual.get('plan') or {}).get('layout') == template.name
        template_ok = template_ok and template.channel == content.get('channel')
    except (ValidationError, CompositionError, TypeError, ValueError, AttributeError):
        template, template_ok = None, False
    check('VISUAL_TEMPLATE', 'visual.template', template_ok,
          'Template aplicado deve ser o template permitido, correspondente ao canal e plano visual.')

    composition = sidecar.get('composition') or {}
    if not isinstance(composition, dict):
        composition = {}
    boxes = composition.get('boxes') or {}
    if not isinstance(boxes, dict):
        boxes = {}
    if template_ok:
        try:
            expected_boxes = PillowComposer.publication_layout(template, content)
            names_ok = set(boxes) == set(expected_boxes)
            bounds_ok = names_ok
            collision_ok = names_ok
            if names_ok:
                parsed = {}
                for name, raw in boxes.items():
                    if not isinstance(raw, dict) or set(raw) != {'x', 'y', 'width', 'height'}:
                        raise ValueError('Box inválido')
                    parsed[name] = Box(**raw)
                    PillowComposer._check_box(parsed[name], template, template.safe_area)
                names = list(parsed)
                collision_ok = all(not parsed[name].intersects(parsed[other])
                                   for index, name in enumerate(names) for other in names[index + 1:])
                bounds_ok = all(vars(parsed[name]) == vars(expected_boxes[name]) for name in names)
        except (CompositionError, TypeError, ValueError, KeyError):
            bounds_ok = collision_ok = False
    else:
        bounds_ok = collision_ok = False
    check('VISUAL_SAFE_AREA', 'visual.template.safe_area', bounds_ok,
          'Áreas registradas devem coincidir com o layout canônico e permanecer dentro das margens.')
    check('VISUAL_OVERLAP', 'visual.template', collision_ok,
          'Áreas obrigatórias registradas não podem se sobrepor.')

    expected_texts = published_texts(content)
    if content.get('composition_version', 1) in (2, 3):
        check('VISUAL_PUBLICATION_PREFERENCES', 'visual.final_image',
              all(composition.get(key) == content.get(key) for key in
                  ('composition_version', 'show_price', 'theme', 'visual_style')),
              'Tema, estilo e publicação de preço devem corresponder à peça atual.')
    check('VISUAL_RENDER_INPUTS', 'visual.final_image',
          composition.get('texts_sent_to_renderer') == expected_texts
          and composition.get('product_id') == content.get('product_id'),
          'Textos e produto enviados ao compositor devem coincidir com os dados autorizados; isto não é OCR.')

    product_hash = _product_hash(composer, content)
    logo_hash = _asset_hash(composer, 'logos', composer.logo_name)
    font_hash = _asset_hash(composer, 'fonts', composer.font_name)
    product_ref_ok = False
    product_metadata = {}
    try:
        product_ref = ImageReference.model_validate(visual.get('product_image'))
        product_stored = storage.get(product_ref)
        raw_metadata = product_stored.metadata.get('metadata')
        product_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        product_ref_ok = product_stored.metadata.get('kind') == 'product_asset' and product_ref.sha256 == product_hash
    except (ValidationError, TypeError, ValueError, OSError, KeyError):
        pass
    check('VISUAL_PRODUCT_ASSET', 'visual.product_image', product_hash != 'missing' and product_ref_ok
          and composition.get('product_sha256') == product_hash,
          'Fotografia e referência de produto devem corresponder ao asset autorizado atual.')
    if content.get('product_photo_version', 'legacy') != 'legacy':
        try:
            name = composer.product_asset_name(content.get('product_id'), content['product_photo_version'])
            photo_metadata_ok = (composition.get('product_asset_name') == name
                and composition.get('product_photo_version') == content['product_photo_version']
                and composition.get('product_presentation') == 'photo_card'
                and product_metadata.get('product_id') == content.get('product_id')
                and product_metadata.get('photo_version') == content['product_photo_version'])
        except (CompositionError, TypeError, ValueError, KeyError):
            photo_metadata_ok = False
        check('VISUAL_PRODUCT_PHOTO_VERSION', 'visual.product_image', product_ref_ok and photo_metadata_ok,
              'Fotografia, produto, versão autorizada e apresentação devem corresponder ao registro e aos metadados.')
    check('VISUAL_LOGO_ASSET', 'visual.final_image', logo_hash != 'missing'
          and composition.get('logo_name') == composer.logo_name
          and composition.get('logo_sha256') == logo_hash,
          'Logotipo usado pelo compositor deve corresponder ao arquivo autorizado atual.')
    check('VISUAL_FONT_ASSET', 'visual.final_image', font_hash != 'missing'
          and composition.get('font_name') == composer.font_name
          and composition.get('font_sha256') == font_hash,
          'Fonte usada pelo compositor deve corresponder ao arquivo autorizado atual.')
    profile = parse_rules(rules).brand
    if profile.allowed_colors:
        used = {str(composition.get('text_color', '')).upper(), str(composition.get('panel_color', '')).upper()}
        check('VISUAL_BRAND_COLORS', 'visual.final_image', used <= {color.upper() for color in profile.allowed_colors},
              'Cores registradas dos textos e painéis devem estar na paleta configurada; o fundo não é analisado.')
    if profile.allowed_fonts:
        check('VISUAL_BRAND_FONT', 'visual.final_image', composer.font_name in profile.allowed_fonts
              and composition.get('font_name') == composer.font_name,
              'Fonte registrada deve estar entre as fontes permitidas.')
    return results
