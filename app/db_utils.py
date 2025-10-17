"""Helpers for resolving the SQLite database path used by the app."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_RELATIVE = Path("instance/pla.db")


def _clean_path(value: Optional[str]) -> str:
    """Normalize an environment-provided path string."""
    if not value:
        return str(DEFAULT_DB_RELATIVE)
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or str(DEFAULT_DB_RELATIVE)


def resolve_db_path(raw: Optional[str] = None) -> Path:
    """Return the absolute path to the SQLite database."""
    candidate = Path(_clean_path(raw))
    if not candidate.is_absolute():
        candidate = APP_ROOT / candidate
    return candidate


def ensure_db_path(raw: Optional[str] = None) -> Path:
    """Resolve the database path and ensure the parent directory exists."""
    path = resolve_db_path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["resolve_db_path", "ensure_db_path", "DEFAULT_DB_RELATIVE"]
