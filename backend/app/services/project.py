"""Serviço de gestão de projetos: criação, persistência, diretórios."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from app.core.config import PROJECTS_DIR, ensure_dirs
from app.models.schemas import PipelineStep, Project, ProjectDetail
from app.utils.helpers import clean_filename, new_id, now_iso

_lock = threading.Lock()


def _atomic_write(p: Path, content: str) -> None:
    """Escrita atômica com retry: no Windows, replace() falha se outro
    processo mantém o destino aberto sem FILE_SHARE_DELETE."""
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(tmp, p)
            return
        except OSError:
            time.sleep(0.15 * (attempt + 1))
    os.replace(tmp, p)


class ProjectStore:
    """Gerencia projetos em disco (data/projects/<id>/)."""

    @staticmethod
    def create(name: str) -> Project:
        ensure_dirs()
        pid = new_id("p_")
        folder = PROJECTS_DIR / pid
        for sub in ("original", "audio", "clips", "subtitles", "thumbnails", "metadata"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        project = Project(
            id=pid,
            name=clean_filename(name) or "video",
            created_at=now_iso(),
            updated_at=now_iso(),
            steps=default_steps(),
        )
        ProjectStore.save(project)
        return project

    @staticmethod
    def folder(project_id: str) -> Path:
        return PROJECTS_DIR / project_id

    @staticmethod
    def path(project_id: str, *parts: str) -> Path:
        return ProjectStore.folder(project_id).joinpath(*parts)

    @staticmethod
    def save(project: Project) -> None:
        with _lock:
            p = ProjectStore.path(project.id, "project.json")
            p.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(p, project.model_dump_json(indent=2))

    @staticmethod
    def get(project_id: str) -> Project | None:
        p = ProjectStore.path(project_id, "project.json")
        if not p.exists():
            return None
        try:
            return Project.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def require(project_id: str) -> Project:
        p = ProjectStore.get(project_id)
        if p is None:
            raise FileNotFoundError(f"Projeto não encontrado: {project_id}")
        return p

    @staticmethod
    def update(project_id: str, **fields: Any) -> Project:
        p = ProjectStore.require(project_id)
        for k, v in fields.items():
            setattr(p, k, v)
        p.updated_at = now_iso()
        ProjectStore.save(p)
        return p

    @staticmethod
    def list_all() -> list[Project]:
        ensure_dirs()
        out = []
        for folder in PROJECTS_DIR.iterdir():
            if folder.is_dir():
                pr = ProjectStore.get(folder.name)
                if pr:
                    out.append(pr)
        out.sort(key=lambda x: x.updated_at, reverse=True)
        return out

    @staticmethod
    def delete(project_id: str) -> None:
        folder = ProjectStore.folder(project_id)
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)

    # ---- arquivos de dados ----

    @staticmethod
    def write_json(project_id: str, name: str, data: Any) -> None:
        with _lock:
            p = ProjectStore.path(project_id, name)
            p.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(p, json.dumps(data, ensure_ascii=False, indent=2))

    @staticmethod
    def read_json(project_id: str, name: str, default: Any = None) -> Any:
        p = ProjectStore.path(project_id, name)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def detail(project_id: str) -> ProjectDetail:
        pr = ProjectStore.require(project_id)
        from app.models.schemas import Analysis, Clip, ContentAnalysis, Transcription

        d = ProjectDetail(**pr.model_dump())
        d.dirs = {
            "root": str(ProjectStore.folder(project_id)),
            "original": str(ProjectStore.path(project_id, "original")),
            "clips": str(ProjectStore.path(project_id, "clips")),
            "subtitles": str(ProjectStore.path(project_id, "subtitles")),
            "transcription": str(ProjectStore.path(project_id, "transcription.json")),
            "thumbnails": str(ProjectStore.path(project_id, "thumbnails")),
            "titles": str(ProjectStore.path(project_id, "Títulos.txt")),
            "post_captions": str(ProjectStore.path(project_id, "Legendas_Postagem.txt")),
        }
        tr = ProjectStore.read_json(project_id, "transcription.json")
        if tr:
            try:
                d.transcription = Transcription.model_validate(tr)
            except Exception:
                pass
        an = ProjectStore.read_json(project_id, "analysis.json")
        if an:
            try:
                d.analysis = Analysis.model_validate(an)
            except Exception:
                pass
        ca = ProjectStore.read_json(project_id, "content_analysis.json")
        if ca:
            try:
                d.content = ContentAnalysis.model_validate(ca)
            except Exception:
                pass
        clips = ProjectStore.read_json(project_id, "clips.json", [])
        for c in clips:
            try:
                d.clips.append(Clip.model_validate(c))
            except Exception:
                continue
        return d


def default_steps() -> list[dict]:
    return [
        PipelineStep(id="audio", label="Extrair áudio", status="pending"),
        PipelineStep(id="transcription", label="Transcrever vídeo", status="pending"),
        PipelineStep(id="signals", label="Analisar cenas, silêncios e energia", status="pending"),
        PipelineStep(id="content", label="IA: entender o conteúdo", status="pending"),
        PipelineStep(id="clips", label="Gerar cortes inteligentes", status="pending"),
        PipelineStep(id="metadata", label="Gerar títulos e textos", status="pending"),
        PipelineStep(id="render", label="Renderizar cortes", status="pending"),
    ]
