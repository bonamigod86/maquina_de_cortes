"""Orquestrador do pipeline completo de processamento de um projeto."""
from __future__ import annotations

import traceback
from pathlib import Path

from app.core.config import Settings
from app.core.events import bus
from app.models.schemas import Clip, Project
from app.services.learning.profiler import user_profile
from app.services.pipeline import audio, clips as clips_svc, content_analysis, export, metadata as meta_svc, signals, subtitles as sub_svc, transcription
from app.services.project import ProjectStore
from app.utils.helpers import new_id, now_iso

STEP_LABELS = {
    "audio": "Extrair áudio",
    "transcription": "Transcrever vídeo",
    "signals": "Analisar cenas, silêncios e energia",
    "content": "IA: entender o conteúdo",
    "clips": "Gerar cortes inteligentes",
    "metadata": "Gerar títulos e textos",
    "render": "Renderizar cortes",
}


class PipelineCancelled(Exception):
    pass


class PipelineRunner:
    """Executa o pipeline em background com eventos de progresso."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _set_step(self, project: Project, step_id: str, status: str, progress: float = 0.0, detail: str = "") -> Project:
        for s in project.steps:
            if s.id == step_id:
                s.status = status
                s.progress = progress
                s.detail = detail
        project.current_step = step_id
        project.progress = self._overall_progress(project)
        ProjectStore.save(project)
        bus.publish(project.id, {"type": "step", "step": step_id, "status": status, "progress": progress, "detail": detail})
        bus.publish(project.id, {"type": "progress", "project": project.model_dump()})
        return project

    def _overall_progress(self, project: Project) -> float:
        weights = {"audio": 0.05, "transcription": 0.25, "signals": 0.15, "content": 0.15, "clips": 0.1, "metadata": 0.1, "render": 0.2}
        total = 0.0
        for s in project.steps:
            if s.status == "done":
                total += weights.get(s.id, 0.1)
            elif s.status in ("running", "error"):
                total += weights.get(s.id, 0.1) * s.progress
        return round(min(total, 1.0), 3)

    def run(self, project_id: str, cancel_event=None) -> None:
        ProjectStore.update(project_id, status="processing", progress=0.0, current_step="", error="")
        project = ProjectStore.require(project_id)
        video_path = project.source
        if not Path(video_path).exists():
            self._fail(project, "Arquivo de vídeo não encontrado")
            return

        try:
            # 1. áudio
            project = self._set_step(project, "audio", "running", 0.0, "Convertendo áudio para WAV 16kHz")
            wav_path = str(ProjectStore.path(project_id, "audio", "audio.wav"))
            duration = project.duration or 0
            audio.extract_audio(
                video_path, wav_path,
                on_progress=lambda p: self._set_step(project, "audio", "running", p * 0.9),
                duration=duration,
                cancel_event=cancel_event,
            )
            project = self._set_step(project, "audio", "done", 1.0)

            # 2. transcrição
            project = self._set_step(project, "transcription", "running", 0.0, f"Modelo: {self.settings.whisper_model} (primeira vez faz download)")
            tr = transcription.transcribe(
                wav_path, self.settings,
                on_progress=lambda p: self._set_step(project, "transcription", "running", p * 0.95),
                cancel_event=cancel_event,
            )
            sentences = transcription.sentences_from_segments(tr)
            transcription.save_transcription(project_id, tr, sentences)
            project = self._set_step(project, "transcription", "done", 1.0, f"{len(tr.segments)} segmentos")
            if self.settings.download_subtitles:
                try:
                    sub_svc.generate_full(project_id, sentences, self.settings)
                except Exception:
                    pass

            # 3. sinais
            project = self._set_step(project, "signals", "running", 0.0, "Detectando cenas, silêncios, energia e ritmo")
            analysis = signals.run_signals(
                project_id, video_path, wav_path, sentences,
                on_progress=lambda p: self._set_step(project, "signals", "running", p * 0.95),
                cancel_event=cancel_event,
            )
            ProjectStore.write_json(project_id, "analysis.json", analysis.model_dump())
            project = self._set_step(project, "signals", "done", 1.0, f"{len(analysis.scenes)} cenas, {len(analysis.silences)} silêncios")

            # 4. análise de conteúdo (LLM)
            project = self._set_step(project, "content", "running", 0.0, "IA lendo e compreendendo todo o vídeo")
            profile = user_profile()
            content = content_analysis.analyze_content(
                project_id, sentences, [s.model_dump() for s in analysis.sentence_signals],
                self.settings, profile,
                on_progress=lambda p: self._set_step(project, "content", "running", p * 0.9),
                cancel_event=cancel_event,
            )
            ProjectStore.write_json(project_id, "content_analysis.json", content.model_dump())
            project = self._set_step(project, "content", "done", 1.0, f"{len(content.highlights)} destaques encontrados")

            # 5. cortes
            project = self._set_step(project, "clips", "running", 0.0, "Pontuando e selecionando os melhores trechos")
            clips = clips_svc.build_clips(
                project_id, sentences, content,
                [s.model_dump() for s in analysis.silences],
                self.settings, profile, tr.duration,
            )
            if not clips:
                raise RuntimeError("Nenhum corte com qualidade suficiente foi encontrado")
            for c in clips:
                c.id = new_id("c_")
                c.created_at = now_iso()
            project = self._set_step(project, "clips", "done", 1.0, f"{len(clips)} cortes selecionados")

            # 6. metadados IA
            project = self._set_step(project, "metadata", "running", 0.0, "Criando títulos, legendas e hashtags")
            context = {"summary": content.summary, "themes": content.themes}
            for i, c in enumerate(clips):
                m = meta_svc.generate_clip_metadata(c, context, self.settings)
                c.title = m["title"]
                c.caption = m["caption"]
                c.description = m["description"]
                c.hashtags = m["hashtags"]
                c.hook = m["hook"]
                c.cta = m["cta"]
                c.keywords = m["keywords"]
                project = self._set_step(project, "metadata", "running", (i + 1) / len(clips) * 0.8)
            meta_svc.write_metadata_files(project_id, clips, self.settings, content.summary, content.themes)
            project = self._set_step(project, "metadata", "done", 1.0)

            # 7. render
            project = self._set_step(project, "render", "running", 0.0, "Reenquadrando, legendando e exportando")
            clips_dir = str(ProjectStore.path(project_id, "clips"))
            for i, c in enumerate(clips):
                if cancel_event and cancel_event.is_set():
                    raise PipelineCancelled("Cancelado pelo usuário")
                base_progress = i / max(len(clips), 1)
                export.render_clip(
                    project_id, c, video_path, sentences, self.settings, clips_dir,
                    on_progress=lambda p: self._set_step(project, "render", "running", base_progress + p / max(len(clips), 1) * 0.95),
                    cancel_event=cancel_event,
                )
                ProjectStore.write_json(project_id, "clips.json", [c.model_dump() for c in clips])
            project = self._set_step(project, "render", "done", 1.0)

            project = ProjectStore.update(
                project_id,
                status="ready",
                progress=1.0,
                current_step="",
                has_transcription=True,
                has_analysis=True,
                has_clips=True,
                clip_count=len(clips),
            )
            bus.publish(project_id, {"type": "pipeline_done", "project": project.model_dump()})

        except PipelineCancelled:
            ProjectStore.update(project_id, status="error", error="Processamento cancelado pelo usuário")
            bus.publish(project_id, {"type": "pipeline_error", "message": "Processamento cancelado"})
        except Exception as e:
            tb = traceback.format_exc()
            ProjectStore.update(project_id, status="error", error=str(e))
            bus.publish(project_id, {"type": "pipeline_error", "message": str(e), "detail": tb[-3000:]})

    def _fail(self, project: Project, msg: str) -> None:
        ProjectStore.update(project.id, status="error", error=msg)
        bus.publish(project.id, {"type": "pipeline_error", "message": msg})
