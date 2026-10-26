"""Bounded, decoded marketing backgrounds, normalized without source metadata."""
import hashlib
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 12_000_000
MIN_DIMENSION = 256

class UploadError(ValueError):
    pass


def normalize_background(data: bytes, media_type: str):
    if media_type not in ('image/png', 'image/jpeg'):
        raise UploadError('Envie somente PNG ou JPEG.')
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise UploadError('A imagem deve ter entre 1 byte e 5 MiB.')
    expected = 'PNG' if media_type == 'image/png' else 'JPEG'
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format != expected or getattr(source, 'n_frames', 1) != 1:
                    raise UploadError('O conteúdo precisa corresponder ao formato informado e conter uma única imagem.')
                width, height = source.size
                if min(width, height) < MIN_DIMENSION or max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
                    raise UploadError('Dimensões permitidas: 256–4096 pixels por lado, até 12 milhões de pixels.')
                source.verify()
            with Image.open(BytesIO(data)) as source:
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                clean = Image.new('RGBA', oriented.size)
                clean.paste(oriented)
                result = BytesIO()
                clean.save(result, format='PNG')
                if len(result.getvalue()) > 50 * 1024 * 1024:
                    raise UploadError('A imagem normalizada excede o limite de armazenamento.')
                return result.getvalue(), clean.size, hashlib.sha256(data).hexdigest()
    except UploadError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UploadError('Arquivo de imagem inválido, incompleto ou inseguro.') from None
