"""Runtime configuration (env-var driven)."""

from __future__ import annotations

import os
from pathlib import Path


DATA_DIR = Path(os.environ.get("ATTACK_PATH_DATA_DIR", "./data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "attack_paths.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

MAX_UPLOAD_MB = int(os.environ.get("ATTACK_PATH_MAX_UPLOAD_MB", "50"))
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("ATTACK_PATH_CORS_ORIGINS", "*").split(",")
    if o.strip()
]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
