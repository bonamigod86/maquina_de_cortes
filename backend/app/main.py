"""ClipForge Local — aplicação FastAPI."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import clips, projects, system, ws
from app.core.cuda import register_cuda_paths
from app.core.config import DATA_DIR, Settings, ensure_dirs
from app.services.pipeline.orchestrator import PipelineRunner
from app.services.queue.manager import queue

register_cuda_paths()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    # lê Settings a cada job: mudanças na UI valem sem reiniciar o backend
    queue.configure(lambda: PipelineRunner(Settings.load()))
    yield


app = FastAPI(title="ClipForge Local", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(clips.router)
app.include_router(system.router)
app.include_router(ws.router)

# serve arquivos de mídia gerados (videos, thumbs, legendas)
for sub in ("projects",):
    (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(DATA_DIR)), name="media")


@app.get("/api/health")
def health():
    return {"ok": True, "app": "ClipForge Local"}
