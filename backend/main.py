"""Backend application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.api.api_routes import router
from backend.config.settings import settings
from backend.db.session import init_database
from backend.services.analysis_service import analyze_audio


app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/")
def root():
    return {"message": settings.app_name, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    content = await file.read()
    return {"code": 0, "message": "success", "data": analyze_audio(file.filename or "audio", content)}


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)
