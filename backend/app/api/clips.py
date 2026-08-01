"""Rotas de cortes: edição, exportação, feedback e regeneração de textos."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import Settings
from app.models.schemas import Clip, ClipEditIn, ClipMergeIn, ClipSplitIn, ExportResult, FeedbackIn, RegenerateTextIn
from app.services.learning.store import FeedbackStore
from app.services.pipeline import export, metadata as meta_svc
from app.services.project import ProjectStore
from app.utils.helpers import new_id, now_iso

router = APIRouter(prefix="/api/clips", tags=["clips"])

_feedback = FeedbackStore()


def _load_clip(clip_id: str) -> tuple[list[dict], dict]:
    project_id = clip_id.rsplit("_", 1)[0] if clip_id.startswith("c_") else ""
    # encontra o projeto pelo prefixo do id
    for p in ProjectStore.list_all():
        clips = ProjectStore.read_json(p.id, "clips.json", [])
        if any(c.get("id") == clip_id for c in clips):
            return clips, p.model_dump()
    raise HTTPException(404, "Corte não encontrado")


def _save_clips(project_id: str, clips: list[dict]) -> None:
    ProjectStore.write_json(project_id, "clips.json", clips)


class ExportAllIn(BaseModel):
    clip_ids: list[str] | None = None


@router.post("/{clip_id}/export", response_model=ExportResult)
def export_clip(clip_id: str, settings: Settings = None):
    settings = settings or Settings.load()
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    if not c:
        raise HTTPException(404, "Corte não encontrado")
    project = ProjectStore.require(c["project_id"])
    if c.get("files", {}).get("video") and Path(c["files"]["video"]).exists():
        return ExportResult(clip_id=clip_id, ok=True, path=c["files"]["video"])
    try:
        clip = Clip.model_validate(c)
        sentences = ProjectStore.read_json(c["project_id"], "sentences.json", [])
        clips_dir = str(ProjectStore.path(c["project_id"], "clips"))
        clip = export.render_clip(
            c["project_id"], clip, project.source, sentences, settings, clips_dir
        )
        c.update(clip.model_dump())
        _save_clips(c["project_id"], clips)
        return ExportResult(clip_id=clip_id, ok=True, path=clip.files.video)
    except Exception as e:
        return ExportResult(clip_id=clip_id, ok=False, error=str(e))


@router.post("/{project_id}/export-all", response_model=list[ExportResult])
def export_all(project_id: str, body: ExportAllIn | None = None, settings: Settings = None):
    settings = settings or Settings.load()
    project = ProjectStore.require(project_id)
    clips = ProjectStore.read_json(project_id, "clips.json", [])
    sentences = ProjectStore.read_json(project_id, "sentences.json", [])
    ids = body.clip_ids if body and body.clip_ids else [c["id"] for c in clips]
    results: list[ExportResult] = []
    for c in clips:
        if c["id"] not in ids:
            continue
        try:
            clip = Clip.model_validate(c)
            clips_dir = str(ProjectStore.path(project_id, "clips"))
            clip = export.render_clip(project_id, clip, project.source, sentences, settings, clips_dir)
            c.update(clip.model_dump())
            results.append(ExportResult(clip_id=clip.id, ok=True, path=clip.files.video))
        except Exception as e:
            results.append(ExportResult(clip_id=clip.id, ok=False, error=str(e)))
    _save_clips(project_id, clips)
    return results


@router.patch("/{clip_id}", response_model=Clip)
def edit_clip(clip_id: str, body: ClipEditIn):
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    if not c:
        raise HTTPException(404, "Corte não encontrado")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            c[field] = val
    if body.source_start is not None and body.source_end is not None:
        c["duration"] = round(body.source_end - body.source_start, 2)
        # invalida vídeo renderizado (precisa re-render)
        c["files"] = {}
    _save_clips(c["project_id"], clips)
    return Clip.model_validate(c)


@router.post("/{clip_id}/split", response_model=list[Clip])
def split_clip(clip_id: str, body: ClipSplitIn):
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    if not c:
        raise HTTPException(404, "Corte não encontrado")
    if not (c["source_start"] < body.at < c["source_end"]):
        raise HTTPException(400, "Ponto de divisão fora do corte")
    a = {**c, "id": new_id("c_"), "source_end": body.at, "duration": round(body.at - c["source_start"], 2), "created_at": now_iso(), "files": {}}
    b = {**c, "id": new_id("c_"), "source_start": body.at, "duration": round(c["source_end"] - body.at, 2), "created_at": now_iso(), "files": {}}
    a["title"] = c["title"] + " (parte 1)"
    b["title"] = c["title"] + " (parte 2)"
    idx = clips.index(c)
    clips[idx : idx + 1] = [a, b]
    _save_clips(c["project_id"], clips)
    return [Clip.model_validate(x) for x in (a, b)]


@router.post("/{clip_id}/merge", response_model=Clip)
def merge_clips(clip_id: str, body: ClipMergeIn):
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    other = next((x for x in clips if x["id"] == body.other_clip_id), None)
    if not c or not other:
        raise HTTPException(404, "Corte não encontrado")
    if c["project_id"] != other["project_id"]:
        raise HTTPException(400, "Cortes de projetos diferentes")
    start = min(c["source_start"], other["source_start"])
    end = max(c["source_end"], other["source_end"])
    c["source_start"] = start
    c["source_end"] = end
    c["duration"] = round(end - start, 2)
    c["files"] = {}
    c["title"] = c.get("title", "") + " + " + other.get("title", "")
    clips = [x for x in clips if x["id"] != other["id"]]
    _save_clips(c["project_id"], clips)
    return Clip.model_validate(c)


@router.post("/{clip_id}/feedback")
def clip_feedback(clip_id: str, body: FeedbackIn):
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    if not c:
        raise HTTPException(404, "Corte não encontrado")
    if body.rating not in ("excellent", "good", "bad", "ignore", "none"):
        raise HTTPException(400, "Avaliação inválida")
    c["feedback"] = None if body.rating == "none" else body.rating
    _save_clips(c["project_id"], clips)
    if body.rating == "none":
        _feedback.clear(clip_id)
    else:
        _feedback.record(
            clip_id,
            c["project_id"],
            body.rating,
            c.get("tags", []),
            c.get("duration", 0),
            c.get("title", ""),
            c.get("caption", ""),
        )
    return {"ok": True, "feedback": c["feedback"]}


@router.post("/{clip_id}/regenerate", response_model=dict)
def regenerate_text(clip_id: str, body: RegenerateTextIn):
    clips, _ = _load_clip(clip_id)
    c = next((c for c in clips if c["id"] == clip_id), None)
    if not c:
        raise HTTPException(404, "Corte não encontrado")
    clip = Clip.model_validate(c)
    settings = Settings.load()
    text = meta_svc.regenerate_field(clip, body.field, settings, body.prompt_hint)
    if not text:
        raise HTTPException(502, "IA indisponível — verifique se o Ollama está rodando")
    c[body.field] = text
    _save_clips(c["project_id"], clips)
    if body.field == "caption":
        _refresh_post_files(c["project_id"])
    return {"ok": True, body.field: text}


def _refresh_post_files(project_id: str) -> None:
    clips = ProjectStore.read_json(project_id, "clips.json", [])
    titles = [c.get("title", "") for c in clips if c.get("title")]
    caps = [
        f"--- {c.get('title', '')} ---\n{c.get('caption', '')}\n{c.get('description', '')}\n\n{' '.join(c.get('hashtags', []))}"
        for c in clips
    ]
    folder = ProjectStore.folder(project_id)
    (folder / "Títulos.txt").write_text("\n".join(titles), encoding="utf-8")
    (folder / "Legendas_Postagem.txt").write_text("\n\n".join(caps), encoding="utf-8")
