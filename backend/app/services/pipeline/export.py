"""Renderização/exportação: reenquadra, queima legendas e codifica MP4 1080x1920."""
from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.models.schemas import Clip
from app.services.pipeline import reframe as reframe_svc
from app.services.pipeline import subtitles as sub_svc
from app.utils import ffmpeg as ff
from app.utils.helpers import clean_filename


def _export_quality_crf(quality: str) -> tuple[str, str]:
    return {
        "high": ("slow", "18"),
        "medium": ("medium", "23"),
        "fast": ("veryfast", "26"),
    }.get(quality, ("medium", "23"))


def _words_in_window(transcription_words: list[dict], t0: float, t1: float) -> list[dict]:
    return [w for w in transcription_words if t0 <= w["start"] and w["end"] <= t1]


def all_words(sentences: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in sentences:
        out.extend(s["words"])
    return out


def render_clip(
    project_id: str,
    clip: Clip,
    video_path: str,
    sentences: list[dict],
    settings: Settings,
    out_dir: str,
    on_progress=None,
    cancel_event=None,
    subtitle_style: dict | None = None,
) -> Clip:
    """Renderiza o corte vertical com legendas queimadas e salva thumbnails."""
    from app.services.project import ProjectStore

    style_cfg = subtitle_style or settings.subtitle_style
    base = ProjectStore.folder(project_id)
    clips_dir = Path(out_dir)
    subs_dir = base / "subtitles"
    thumbs_dir = base / "thumbnails"
    for d in (clips_dir, subs_dir, thumbs_dir):
        d.mkdir(parents=True, exist_ok=True)

    name = clean_filename(clip.title or f"corte_{clip.id}")
    video_out = clips_dir / f"{clip.id}_{name}.mp4"
    ass_path = subs_dir / f"{clip.id}.ass"
    srt_path = subs_dir / f"{clip.id}.srt"
    thumb_path = thumbs_dir / f"{clip.id}.jpg"

    info = ff.media_info(video_path)
    width, height = info["width"], info["height"]
    if width <= 0 or height <= 0:
        raise RuntimeError("Falha ao ler resolução do vídeo")

    words = _words_in_window(all_words(sentences), clip.source_start, clip.source_end)
    sub_svc.build_ass(words, clip.source_start, clip.source_end, style_cfg, str(ass_path))
    sub_svc.build_srt(words, clip.source_start, clip.source_end, str(srt_path))

    sw, sh = reframe_svc.scaled_dims(width, height)
    anchors = None
    if settings.face_detection:
        anchors = reframe_svc.sample_face_anchors(
            video_path,
            clip.source_start,
            clip.source_end,
            on_progress=lambda p: on_progress(p * 0.35) if on_progress else None,
            cancel_event=cancel_event,
        )
    if anchors:
        # as âncoras usam tempo absoluto (source); o filtro ffmpeg usa t relativo
        # ao início do corte (-ss), então desloca para [0, duração].
        anchors = [(t - clip.source_start, cx, cy) for t, cx, cy in anchors]
        x_expr, y_expr = reframe_svc.crop_expressions(anchors, sw, sh)
    else:
        x_expr, y_expr = reframe_svc.center_crop_exprs(sw, sh)

    # filtro subtitles do ffmpeg (Windows): caminho sem aspas,
    # ":" escapado como "\\:" (dois backslashes exigidos pelo parser do filtro);
    # fontes resolvidas via FONTCONFIG_FILE (ver app/utils/ffmpeg.py), fontdir
    # não é suportado nessa versão do ffmpeg.
    def _filter_path(p: str) -> str:
        return p.replace("\\", "/").replace(":", "\\\\:")

    ass_path_filter = _filter_path(str(ass_path))
    # expressões de crop com vírgulas (if(lt(...))) exigem aspas simples no
    # filtergraph, senão o parser do ffmpeg divide o filtro nos vírgulas.
    vf = (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"crop=1080:1920:'{x_expr}':'{y_expr}',"
        f"subtitles={ass_path_filter},"
        "fps=30,format=yuv420p"
    )
    preset, crf = _export_quality_crf(settings.export_quality)
    duration = clip.source_end - clip.source_start
    ff.run_ffmpeg(
        [
            "-ss", str(clip.source_start),
            "-i", video_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", crf,
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            str(video_out),
        ],
        on_progress=lambda p: on_progress(0.4 + p * 0.55) if on_progress else None,
        duration=duration,
        cancel_event=cancel_event,
    )
    # thumbnail: primeiro quadro útil do corte renderizado
    try:
        ff.run_ffmpeg(
            [
                "-ss", "0.5",
                "-i", str(video_out),
                "-frames:v", "1",
                "-q:v", "2",
                str(thumb_path),
            ]
        )
    except Exception:
        pass

    clip.files.video = str(video_out)
    clip.files.subtitle = str(srt_path)
    clip.files.subtitle_ass = str(ass_path)
    clip.files.thumbnail = str(thumb_path)
    clip.files.preview = str(video_out)
    if on_progress:
        on_progress(1.0)
    return clip


def make_thumbnail(video_path: str, t: float, out_path: str) -> str:
    ff.run_ffmpeg(["-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "2", out_path])
    return out_path
