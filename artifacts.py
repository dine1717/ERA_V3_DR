"""Content-addressable artifact store. Raw bytes live here; Memory holds the handle.

Handles: "art:<first-16-hex-of-sha256>"
On disk:  state/artifacts/<id>.bin  + <id>.json
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from schemas import Artifact

STATE_DIR = Path(__file__).parent / "state"
ART_DIR = STATE_DIR / "artifacts"
ART_DIR.mkdir(parents=True, exist_ok=True)


def _handle(blob: bytes) -> str:
    return "art:" + hashlib.sha256(blob).hexdigest()[:16]


def _bin_path(art_id: str) -> Path:
    return ART_DIR / f"{art_id.replace(':', '_')}.bin"


def _meta_path(art_id: str) -> Path:
    return ART_DIR / f"{art_id.replace(':', '_')}.json"


def put(blob: bytes, *, content_type: str, source: str, descriptor: str) -> str:
    """Store bytes content-addressably. Identical blobs deduplicate."""
    art_id = _handle(blob)
    bp = _bin_path(art_id)
    if not bp.exists():
        bp.write_bytes(blob)
    meta = Artifact(
        id=art_id,
        content_type=content_type,
        size_bytes=len(blob),
        source=source,
        descriptor=descriptor,
    )
    _meta_path(art_id).write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    return art_id


def exists(art_id: Optional[str]) -> bool:
    if not art_id or not art_id.startswith("art:"):
        return False
    return _bin_path(art_id).exists() and _meta_path(art_id).exists()


def get_bytes(art_id: str) -> bytes:
    return _bin_path(art_id).read_bytes()


def get_meta(art_id: str) -> Artifact:
    return Artifact.model_validate_json(_meta_path(art_id).read_text(encoding="utf-8"))
