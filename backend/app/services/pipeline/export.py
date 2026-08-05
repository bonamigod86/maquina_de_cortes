"""Renderização/exportação: reenquadra, queima legendas e codifica MP4 1080x1920."""
from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.models.schemas import Clip
from app.services.pipeline import reframe as reframe_svc
from app.services.pipeline import subtitles as sub_svc
from app.utils import ffmpeg as ff
from app.utils.helpers import clean_filename, new_id, now_iso


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
        for w in s["words"]:
            if out:
                prev = out[-1]
                same_text = prev.get("word", "").strip().lower() == str(w.get("word", "")).strip().lower()
                tiny_gap = abs(float(prev.get("start", 0) or 0) - float(w.get("start", 0) or 0)) < 0.2
                if same_text and tiny_gap:
                    continue
            out.append(w)
    return out


def _reframe_vf(
    width: int,
    height: int,
    duration: float,
    source_start: float,
    settings: Settings,
    anchors: list[tuple[float, float, float]] | None,
    face_segments: list[tuple[float, float]],
    subtitle_filter: str | None,
) -> str:
    """Monta o filtro ffmpeg de reenquadramento 9:16 (blur / crop / híbrido).

    - `anchors`/`face_segments` usam tempo absoluto (source); o filtro usa t
      relativo ao início do trecho, então desloca por `source_start`.
    - `subtitle_filter` é o filtro `subtitles=...` já com o caminho escapado
      (ou None para não queimar legendas).
    """
    sw, sh = reframe_svc.scaled_dims(width, height)
    mode = getattr(settings, "reframe_mode", "auto")
    landscape = width / height > 1080 / 1920

    rel_segments = [
        (max(0.0, s - source_start), min(duration, e - source_start))
        for s, e in face_segments
    ]
    rel_segments = [(s, e) for s, e in rel_segments if e - s >= 0.05]
    face_dur = sum(e - s for s, e in rel_segments)

    if mode == "blur":
        use_blur, use_hybrid = True, False
    elif mode == "auto" and landscape and not anchors:
        use_blur, use_hybrid = True, False
    elif mode == "auto" and landscape:
        # rosto presente: decide entre cortar tudo, blur tudo ou híbrido.
        if face_dur < 0.4:
            use_blur, use_hybrid = True, False
        elif face_dur > duration - 0.4:
            use_blur, use_hybrid = False, False
        else:
            use_blur, use_hybrid = False, True
    else:
        use_blur, use_hybrid = False, False

    sub_part = f"subtitles={subtitle_filter}," if subtitle_filter else ""

    if use_blur:
        return (
            "split=2[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25[bg];"
            "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"{sub_part}"
            "fps=30,format=yuv420p"
        )
    if use_hybrid:
        # híbrido: take aberto (sem rosto) mostra o quadro inteiro com fundo
        # desfocado; nos trechos com rosto o zoom 9:16 cobre a tela. Uma única
        # passada: o overlay com enable alterna entre base (blur) e zoom (rosto).
        anchors_shifted = [(t - source_start, cx, cy) for t, cx, cy in anchors]
        x_expr, y_expr = reframe_svc.crop_expressions(anchors_shifted, sw, sh)
        enable = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in rel_segments)
        return (
            "split=3[a][b][c];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25[bg];"
            "[b]scale=1080:1920:force_original_aspect_ratio=decrease[full];"
            f"[c]scale={sw}:{sh}:flags=lanczos,crop=1080:1920:'{x_expr}':'{y_expr}'[zoom];"
            "[bg][full]overlay=(W-w)/2:(H-h)/2:shortest=1[base];"
            f"[base][zoom]overlay=0:0:enable='{enable}',"
            f"{sub_part}"
            "fps=30,format=yuv420p"
        )

    if anchors:
        # as âncoras usam tempo absoluto (source); o filtro ffmpeg usa t relativo
        # ao início do corte (-ss), então desloca para [0, duração].
        anchors = [(t - source_start, cx, cy) for t, cx, cy in anchors]
        x_expr, y_expr = reframe_svc.crop_expressions(anchors, sw, sh)
    else:
        x_expr, y_expr = reframe_svc.center_crop_exprs(sw, sh)
    return (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"crop=1080:1920:'{x_expr}':'{y_expr}',"
        f"{sub_part}"
        "fps=30,format=yuv420p"
    )


_LOGO_POSITIONS = {
    "top-left": ("40", "40"),
    "top-right": ("W-w-40", "40"),
    "bottom-left": ("40", "H-h-40"),
    "bottom-right": ("W-w-40", "H-h-40"),
}


def _brand_overlay_vf(vf: str, brand_kit: dict | None) -> str:
    """Sobrepõe o logo da marca ao final do filtergraph, se configurado.

    As cadeias de `_reframe_vf` terminam em `fps=30,format=yuv420p`; troca esse
    trecho por uma ramificação `movie`+`overlay` antes do encodificador.
    """
    bk = brand_kit or {}
    logo = bk.get("logo_path") or ""
    if not logo or not bk.get("use_logo") or not Path(logo).exists():
        return vf
    suffix = "fps=30,format=yuv420p"
    if suffix not in vf:
        return vf
    path = logo.replace("\\", "/").replace(":", "\\\\:")
    x, y = _LOGO_POSITIONS.get(bk.get("logo_position", "top-right"), _LOGO_POSITIONS["top-right"])
    main = vf.replace(suffix, "").rstrip(",")
    return (
        f"{main}[main];"
        f"movie={path},scale='min(iw,180)':-2[logo];"
        f"[main][logo]overlay={x}:{y}:format=auto[out];"
        f"[out]{suffix}"
    )


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

    base = ProjectStore.folder(project_id)
    clips_dir = Path(out_dir)
    subs_dir = base / "subtitles"
    thumbs_dir = base / "thumbnails"
    for d in (clips_dir, subs_dir, thumbs_dir):
        d.mkdir(parents=True, exist_ok=True)

    # template + estilo das legendas com prioridade: corte > template > global
    template = None
    template_id = getattr(clip, "template_id", None)
    if template_id:
        from app.services import template_store

        template = template_store.get_template(template_id)
    style_cfg = (
        (clip.subtitle_style or {})
        or (template.subtitle_style_override if template else {})
        or (subtitle_style or {})
        or settings.subtitle_style
    )

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
    sub_svc.build_ass(
        words,
        clip.source_start,
        clip.source_end,
        style_cfg,
        str(ass_path),
        getattr(settings, "brand_kit", None),
    )
    sub_svc.build_srt(words, clip.source_start, clip.source_end, str(srt_path))

    # filtro subtitles do ffmpeg (Windows): caminho sem aspas, ":" escapado como
    # "\\:" (dois backslashes exigidos pelo parser do filtro); fontes resolvidas
    # via FONTCONFIG_FILE (ver app/utils/ffmpeg.py).
    def _filter_path(p: str) -> str:
        return p.replace("\\", "/").replace(":", "\\\\:")

    ass_path_filter = _filter_path(str(ass_path))

    duration = clip.source_end - clip.source_start
    mode = getattr(settings, "reframe_mode", "auto")

    anchors = None
    face_segments: list[tuple[float, float]] = []
    if mode != "blur" and settings.face_detection:
        anchors, face_segments = reframe_svc.sample_faces(
            video_path,
            clip.source_start,
            clip.source_end,
            on_progress=lambda p: on_progress(p * 0.35) if on_progress else None,
            cancel_event=cancel_event,
        )

    vf = _reframe_vf(width, height, duration, clip.source_start, settings, anchors, face_segments, ass_path_filter)
    vf = _brand_overlay_vf(vf, getattr(settings, "brand_kit", None))

    # aplica template de layout, se o corte tiver um associado
    if template is not None:
        from app.services.pipeline import template_render as tpl_render

        vf = tpl_render.apply_template(
            vf,
            template.model_dump(),
            duration,
            subs_dir,
        )

    preset, crf = _export_quality_crf(settings.export_quality)
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


def render_clip_preview(
    project_id: str,
    clip: Clip,
    video_path: str,
    sentences: list[dict],
    settings: Settings,
    out_dir: str,
    subtitle_style: dict | None = None,
    max_seconds: float = 4.0,
) -> str:
    """Renderiza um preview curto (até `max_seconds`, 540x960, rápido) do corte
    final, com template e estilo de legenda, para validar antes do render total."""
    from app.services.project import ProjectStore

    base = ProjectStore.folder(project_id)
    clips_dir = Path(out_dir)
    subs_dir = base / "subtitles"
    clips_dir.mkdir(parents=True, exist_ok=True)
    subs_dir.mkdir(parents=True, exist_ok=True)

    template = None
    template_id = getattr(clip, "template_id", None)
    if template_id:
        from app.services import template_store

        template = template_store.get_template(template_id)
    style_cfg = (
        (clip.subtitle_style or {})
        or (template.subtitle_style_override if template else {})
        or (subtitle_style or {})
        or settings.subtitle_style
    )

    name = clean_filename(clip.title or f"corte_{clip.id}")
    video_out = clips_dir / f"{clip.id}_{name}_preview.mp4"
    ass_path = subs_dir / f"{clip.id}_preview.ass"

    words = _words_in_window(all_words(sentences), clip.source_start, clip.source_end)
    sub_svc.build_ass(
        words,
        clip.source_start,
        clip.source_end,
        style_cfg,
        str(ass_path),
        getattr(settings, "brand_kit", None),
    )

    def _filter_path(p: str) -> str:
        return p.replace("\\", "/").replace(":", "\\\\:")

    ass_path_filter = _filter_path(str(ass_path))
    duration = clip.duration
    pv_duration = min(duration, max_seconds)
    if pv_duration < 0.5:
        pv_duration = min(duration, 1.0)

    info = ff.media_info(video_path)
    width, height = info["width"], info["height"]
    vf = _reframe_vf(width, height, duration, clip.source_start, settings, None, [], ass_path_filter)
    vf = _brand_overlay_vf(vf, getattr(settings, "brand_kit", None))
    if template is not None:
        from app.services.pipeline import template_render as tpl_render

        vf = tpl_render.apply_template(vf, template.model_dump(), duration, subs_dir)
    vf = f"{vf},scale=540:960:flags=bilinear"

    ff.run_ffmpeg(
        [
            "-ss", str(clip.source_start),
            "-i", video_path,
            "-t", str(pv_duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "28",
            "-an",
            str(video_out),
        ],
        duration=pv_duration,
    )
    return str(video_out)


def render_shorts(
    project_id: str,
    video_path: str,
    settings: Settings,
    out_dir: str,
    on_progress=None,
    cancel_event=None,
) -> Clip:
    """Converte o vídeo inteiro para 9:16 (Shorts/Reels) sem legendas nem IA.

    Respeita o modo de reenquadramento das configurações (blur/crop/híbrido).
    """
    from app.services.project import ProjectStore

    base = ProjectStore.folder(project_id)
    clips_dir = Path(out_dir)
    thumbs_dir = base / "thumbnails"
    for d in (clips_dir, thumbs_dir):
        d.mkdir(parents=True, exist_ok=True)

    info = ff.media_info(video_path)
    width, height = info["width"], info["height"]
    duration = info["duration"]
    if width <= 0 or height <= 0 or duration <= 0:
        raise RuntimeError("Falha ao ler informações do vídeo")

    clip = Clip(
        id=new_id("c_"),
        project_id=project_id,
        source_start=0.0,
        source_end=round(duration, 2),
        duration=round(duration, 2),
        title="Vídeo completo 9:16",
        created_at=now_iso(),
    )
    name = clean_filename("shorts_9x16")
    video_out = clips_dir / f"{clip.id}_{name}.mp4"
    thumb_path = thumbs_dir / f"{clip.id}.jpg"

    mode = getattr(settings, "reframe_mode", "auto")
    anchors = None
    face_segments: list[tuple[float, float]] = []
    if mode != "blur" and settings.face_detection:
        anchors, face_segments = reframe_svc.sample_faces(
            video_path,
            0.0,
            clip.source_end,
            on_progress=lambda p: on_progress(p * 0.35) if on_progress else None,
            cancel_event=cancel_event,
        )

    vf = _reframe_vf(width, height, duration, 0.0, settings, anchors, face_segments, None)
    vf = _brand_overlay_vf(vf, getattr(settings, "brand_kit", None))

    preset, crf = _export_quality_crf(settings.export_quality)
    ff.run_ffmpeg(
        [
            "-i", video_path,
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
    clip.files.thumbnail = str(thumb_path)
    clip.files.preview = str(video_out)
    if on_progress:
        on_progress(1.0)
    return clip


def make_thumbnail(video_path: str, t: float, out_path: str) -> str:
    ff.run_ffmpeg(["-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "2", out_path])
    return out_path
