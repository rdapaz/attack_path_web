"""FastAPI entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import analyze, annotations, exports, pipeline, settings, targets
from .config import CORS_ORIGINS, ensure_dirs

app = FastAPI(
    title="Attack Path Visualizer API",
    version="0.1.0",
    description="Upload PAN-OS firewall configs, analyze attack paths, export diagrams.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(targets.router)
app.include_router(analyze.router)
app.include_router(annotations.router)
app.include_router(exports.router)
app.include_router(settings.router)


@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
