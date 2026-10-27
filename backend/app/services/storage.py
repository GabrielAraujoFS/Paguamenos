"""Persistent local image storage with opaque identifiers and path containment."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.schemas import ImageReference

_MEDIA_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_IMAGE_SIGNATURES = {
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}


@dataclass(frozen=True)
class StoredImage:
    reference: ImageReference
    data: bytes
    metadata: dict


class LocalImageStorage:
    """Store image data and a JSON sidecar; file names are generated internally."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getenv("IMAGE_STORAGE_ROOT", "./creative-assets")).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, file_id: str, suffix: str) -> Path:
        if not _ID_PATTERN.fullmatch(file_id) or suffix not in (*_MEDIA_EXTENSIONS.values(), ".json"):
            raise ValueError("Referência de arquivo inválida.")
        path = (self.root / f"{file_id}{suffix}").resolve()
        if path.parent != self.root:
            raise ValueError("Caminho fora do armazenamento permitido.")
        return path

    def save(self, data: bytes, media_type: str, *, kind: str, metadata: dict | None = None,
             width: int | None = None, height: int | None = None) -> ImageReference:
        if media_type not in _MEDIA_EXTENSIONS:
            raise ValueError("Tipo de imagem não suportado.")
        if not data:
            raise ValueError("Arquivo de imagem vazio.")
        if not _IMAGE_SIGNATURES[media_type](data):
            raise ValueError("O conteúdo não corresponde ao tipo de imagem informado.")
        file_id = uuid4().hex
        digest = hashlib.sha256(data).hexdigest()
        image_path = self._path(file_id, _MEDIA_EXTENSIONS[media_type])
        sidecar_path = self._path(file_id, ".json")
        reference = ImageReference(file_id=file_id, media_type=media_type, sha256=digest,
                                   width=width, height=height)
        record = {"file_id": file_id, "kind": kind, "media_type": media_type,
                  "sha256": digest, "size_bytes": len(data), "width": width, "height": height,
                  "metadata": metadata or {}}
        # Exclusive create prevents accidental overwrite even in the unlikely event of an ID collision.
        with image_path.open("xb") as image_file:
            image_file.write(data)
        try:
            with sidecar_path.open("x", encoding="utf-8") as metadata_file:
                json.dump(record, metadata_file, ensure_ascii=False, sort_keys=True)
        except Exception:
            image_path.unlink(missing_ok=True)
            raise
        return reference

    def get(self, reference: ImageReference) -> StoredImage:
        image_path = self._path(reference.file_id, _MEDIA_EXTENSIONS[reference.media_type])
        sidecar_path = self._path(reference.file_id, ".json")
        data = image_path.read_bytes()
        record = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Metadados de arquivo inválidos.")
        digest = hashlib.sha256(data).hexdigest()
        if (digest != reference.sha256 or digest != record.get("sha256")
                or record.get("file_id") != reference.file_id
                or record.get("media_type") != reference.media_type
                or record.get("size_bytes") != len(data)):
            raise ValueError("Integridade do arquivo não confere.")
        return StoredImage(reference=reference, data=data, metadata=record)


def image_storage_from_environment() -> LocalImageStorage:
    return LocalImageStorage()
