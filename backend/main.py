"""Backend application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

# Heal a broken Python SSL trust store *before* anything else imports a module
# that might open an HTTPS connection (Demucs / Torch / HuggingFace etc.).
# Idempotent and a no-op when the OS CA bundle is already usable.
from backend.ssl_bootstrap import ensure_ssl_cert_bundle as _ensure_ssl_cert_bundle
_ensure_ssl_cert_bundle()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.api.api_routes import router
from backend.config.settings import settings
from backend.db.session import close_mysql_tunnel, get_session_factory, init_database
from backend.services import analysis_service, community_service, reference_track_service, report_service, score_service
from backend.user import history_manager, user_system
import os

import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_database()
        factory = get_session_factory()
        user_system.set_db_session_factory(factory)
        history_manager.set_db_session_factory(factory)
        community_service.set_db_session_factory(factory)
        analysis_service.set_db_session_factory(factory)
        reference_track_service.set_db_session_factory(factory)
        report_service.set_db_session_factory(factory)
        logger.info(
            "Database connected – user/history/community/analysis/report/reference modules running in DB mode"
        )
    except Exception as exc:
        logger.warning("Database unavailable (%s) – falling back to in-memory mode", exc)
        user_system.USE_DB = False
        history_manager.USE_DB = False
        community_service.USE_DB = False
        analysis_service.USE_DB = False
        reference_track_service.USE_DB = False
        report_service.USE_DB = False
        score_service.USE_DB = False
    try:
        yield
    finally:
        close_mysql_tunnel()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")


@app.get("/")
def root():
    return {"message": settings.app_name, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}

UPLOAD_DIR = "D:/SeeMusic_data/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static/avatars", StaticFiles(directory=UPLOAD_DIR), name="avatars")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)
