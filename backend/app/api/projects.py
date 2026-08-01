"""Rotas de projetos: importação, status, transcrição e busca."""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import Settings
from app.core.events import bus
from app.models.schemas import CreateProjectResponse, Project, ProjectDetail
from app.services.pipeline import subtitles as sub_svc
from app.services.pipeline.audio import extract_audio
from app.services.project import ProjectStore
from app.services.queue.manager import queue
from app.utils.helpers import clean_filename, new_id

router = APIRouter(prefix="/api/projects", tags=["projects"])

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts"}


class SearchIn(BaseModel):
    query: str
    max_results: int = 20


class ProcessIn(BaseModel):
    pass


class ImportUrlIn(BaseModel):
    url: str


def _download_and_finalize(project_id: str, url: str) -> None:
    """Baixa o vídeo da URL em background e finaliza o projeto."""
    from app.services.downloader import download_youtube
    from app.utils.ffmpeg import media_info

    try:
        final, title = download_youtube(url, project_id)
        info = media_info(final)
        project = ProjectStore.update(
            project_id,
            name=clean_filename(title) or "YouTube",
            source=str(final),
            source_size=Path(final).stat().st_size,
            duration=info["duration"],
            width=info["width"],
            height=info["height"],
            fps=info["fps"],
            status="ready",
        )
        if not info["has_audio"]:
            ProjectStore.update(project_id, status="error", error="Vídeo do YouTube não possui trilha de áudio")
            bus.publish(project_id, {"type": "import_error", "message": "Vídeo sem trilha de áudio"})
            return
        bus.publish(project_id, {"type": "import_done", "project": project.model_dump()})
    except Exception as e:
        ProjectStore.update(project_id, status="error", error=str(e))
        bus.publish(project_id, {"type": "import_error", "message": str(e)})


@router.get("", response_model=list[Project])
def list_projects():
    return ProjectStore.list_all()


@router.post("", response_model=CreateProjectResponse)
def create_project(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, f"Formato não suportado: {ext}. Use MP4, MOV, MKV, AVI, WebM etc.")
    project = ProjectStore.create(Path(file.filename or "video").stem)
    dest = ProjectStore.path(project.id, "original", f"original{ext}")
    try:
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception:
        ProjectStore.delete(project.id)
        raise HTTPException(500, "Falha ao salvar o vídeo")
    # mede duração/resolução via ffprobe
    try:
        from app.utils.ffmpeg import media_info

        info = media_info(str(dest))
        project = ProjectStore.update(
            project.id,
            source=str(dest),
            source_size=dest.stat().st_size,
            duration=info["duration"],
            width=info["width"],
            height=info["height"],
            fps=info["fps"],
            status="ready",
        )
        if not info["has_audio"]:
            ProjectStore.update(project.id, status="error", error="O vídeo não possui trilha de áudio")
    except Exception as e:
        ProjectStore.update(project.id, status="error", error=f"Falha ao analisar vídeo: {e}")
    return CreateProjectResponse(project=project, upload_id=project.id)


@router.post("/import-url", response_model=CreateProjectResponse)
def import_url(body: ImportUrlIn):
    """Cria um projeto a partir de um link (YouTube etc.), baixando em background."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL inválida")
    project = ProjectStore.create("YouTube")
    ProjectStore.update(project.id, status="downloading")
    threading.Thread(target=_download_and_finalize, args=(project.id, url), daemon=True).start()
    return CreateProjectResponse(project=ProjectStore.require(project.id), upload_id=project.id)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str):
    try:
        return ProjectStore.detail(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Projeto não encontrado")


@router.delete("/{project_id}")
def delete_project(project_id: str):
    queue.cancel(project_id)
    ProjectStore.delete(project_id)
    return {"ok": True}


@router.post("/{project_id}/process")
def process_project(project_id: str):
    import logging
    log = logging.getLogger("debug.process")
    log.warning("process: inicio")
    project = ProjectStore.require(project_id)
    log.warning("process: require ok")
    snap = queue.snapshot()
    log.warning("process: snapshot ok")
    if project_id in snap.get("pending", []) or project_id == snap.get("current"):
        raise HTTPException(409, "Projeto já está na fila de processamento")
    # reset steps (permite reprocessar após restart com status preso)
    from app.services.project import default_steps

    project.steps = default_steps()
    ProjectStore.update(project_id, status="processing", error="", progress=0.0)
    log.warning("process: update ok")
    queued = queue.enqueue(project_id)
    log.warning("process: enqueue ok")
    return {"ok": True, "queued": queued}


@router.post("/{project_id}/cancel")
def cancel_project(project_id: str):
    queue.cancel(project_id)
    return {"ok": True}


@router.post("/{project_id}/search")
def search_transcription(project_id: str, body: SearchIn):
    """Busca palavras na transcrição; retorna trechos com frases correspondentes."""
    project = ProjectStore.require(project_id)
    sentences = ProjectStore.read_json(project_id, "sentences.json", [])
    q = body.query.strip().lower()
    if not q:
        return {"results": []}
    q_words = q.split()
    results = []
    for s in sentences:
        text_low = s["text"].lower()
        if all(w in text_low for w in q_words) or any(w in text_low for w in q_words[:1]):
            results.append(
                {
                    "index": s["index"],
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"],
                }
            )
            if len(results) >= body.max_results:
                break
    return {"results": results}


@router.get("/{project_id}/queue-position")
def queue_position(project_id: str):
    snap = queue.snapshot()
    pending = snap.get("pending", [])
    return {
        "current": snap.get("current"),
        "position": (pending.index(project_id) + 1) if project_id in pending else (0 if snap.get("current") == project_id else None),
    }


@router.post("/{project_id}/subtitles")
def generate_subtitles(project_id: str):
    """Gera legendas do vídeo inteiro (srt/vtt/txt) e retorna os caminhos."""
    ProjectStore.require(project_id)
    sentences = ProjectStore.read_json(project_id, "sentences.json", [])
    if not sentences:
        raise HTTPException(400, "Nenhuma transcrição encontrada — processe o vídeo primeiro")
    files = sub_svc.generate_full(project_id, sentences, Settings.load())
    return {"ok": True, "files": files}
