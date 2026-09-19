"""File storage abstraction for uploaded resumes and generated versions.

Dev/test: local disk under ./storage (gitignored). Production: Supabase Storage
private bucket `user-files`; the PostgREST + signed-URL wiring is completed during
the credential-backed phase.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from app.core.config import get_settings

_LOCAL_ROOT = Path(__file__).resolve().parent.parent.parent / ".storage"


def _safe_path(user_id: str, filename: str) -> Path:
    safe = Path(filename).name  # strip any directory components
    return _LOCAL_ROOT / user_id / safe


def store_user_file(user_id: str, filename: str, content: bytes) -> str:
    """Store a user-owned file. Returns the stored key."""
    settings = get_settings()
    stored_name = f"{uuid.uuid4().hex[:12]}_{Path(filename).name}"
    if settings.environment == "production":
        raise NotImplementedError("Supabase Storage upload is wired during the credential-backed phase.")
    path = _LOCAL_ROOT / user_id / stored_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return stored_name


def read_user_file(user_id: str, stored_name: str) -> bytes | None:
    path = (_LOCAL_ROOT / user_id / stored_name).resolve()
    if not path.is_relative_to((_LOCAL_ROOT / user_id).resolve()):
        return None
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_user_file(user_id: str, stored_name: str) -> None:
    path = (_LOCAL_ROOT / user_id / stored_name).resolve()
    if path.is_relative_to((_LOCAL_ROOT / user_id).resolve()) and path.is_file():
        path.unlink()


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reset_local_storage() -> None:
    if _LOCAL_ROOT.exists():
        shutil.rmtree(_LOCAL_ROOT)
