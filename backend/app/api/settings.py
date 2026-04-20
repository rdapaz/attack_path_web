"""Categories (annotation classification) — persisted to settings.json."""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import SETTINGS_PATH, ensure_dirs

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_CATEGORIES = [
    {"name": "TEMPORARY", "color": "#fff9c4"},
    {"name": "OVERLY PERMISSIVE", "color": "#ffcdd2"},
    {"name": "CHANGE TO DPI", "color": "#b2ebf2"},
]


class Category(BaseModel):
    name: str
    color: str


class CategoriesIn(BaseModel):
    categories: list[Category]


def _load() -> dict:
    if not SETTINGS_PATH.exists():
        return {"categories": DEFAULT_CATEGORIES}
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {"categories": DEFAULT_CATEGORIES}


def _save(data: dict) -> None:
    ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))


@router.get("/categories")
def get_categories() -> dict:
    return _load()


@router.put("/categories")
def put_categories(payload: CategoriesIn) -> dict:
    data = _load()
    data["categories"] = [c.model_dump() for c in payload.categories]
    _save(data)
    return data
