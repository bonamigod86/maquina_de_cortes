"""Composição de templates de corte sobre o vídeo 1080x1920 via ffmpeg.

O engine recebe o filtergraph base do reenquadramento (que termina em
`fps=30,format=yuv420p`) e compõe: fundo (cor/gradiente), vídeo em slot,
formas (drawbox/drawcircle), textos (ASS) e imagens/logos (movie+overlay).
"""
from __future__ import annotations

from pathlib import Path

from app.services.pipeline import subtitles as sub_svc

W, H = 1080, 1920


def _ass_color(hex_color: str, alpha: str = "00") -> str:
    return sub_svc._hex_ass(hex_color, alpha)


def _filter_path(p: str) -> str:
    return p.replace("\\", "/").replace(":", "\\\\:")


def _px(v: float, base: int) -> int:
    return int(round(v * base))


def _hex_no_hash(c: str) -> str:
    return c.lstrip("#")


def _bg_source(bg: dict) -> str:
    """Cria a camada de fundo `[bg]`. color/gradients/movie são FILTROS FONTE
    (sem entrada de vídeo) — o vídeo é sobreposto depois com overlay."""
    kind = bg.get("type", "none")
    if kind == "color":
        val = _hex_no_hash(bg.get("value", "#000000"))
        return f"color=0x{val}:s={W}x{H}:r=30[bg]"
    if kind == "gradient":
        val = bg.get("value") or {}
        colors = (val.get("colors") or ["#000000", "#000000"])[:4]
        angle = float(val.get("angle", 0))
        import math

        rad = math.radians(angle)
        cos, sin = math.cos(rad), math.sin(rad)
        x0 = 0 if abs(cos) < 0.01 else (0 if cos > 0 else W)
        y0 = 0 if abs(sin) < 0.01 else (0 if sin > 0 else H)
        x1 = W if cos > 0 else (0 if cos < 0 else x0)
        y1 = H if sin > 0 else (0 if sin < 0 else y0)
        cols = "".join(f":c{i}=0x{_hex_no_hash(c)}" for i, c in enumerate(colors))
        return (
            f"gradients=s={W}x{H}:r=30:nb_colors={len(colors)}{cols}"
            f":x0={x0}:y0={y0}:x1={x1}:y1={y1}[bg]"
        )
    if kind == "image":
        path = _filter_path(bg.get("value", ""))
        if path:
            return f"movie={path}[bg]"
    return f"color=black:s={W}x{H}:r=30[bg]"


def _build_template_ass(elements: list[dict], duration: float, out_path: str) -> str:
    """Gera um .ass com os textos do template posicionados por \\pos."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""

    styles: list[str] = []
    events: list[str] = []
    end = sub_svc._ass_time(duration)
    for i, el in enumerate(elements):
        if el.get("type") != "text" or not el.get("content"):
            continue
        st = el.get("style") or {}
        font = st.get("font", "Arial Black")
        size = max(20, min(220, int(round(float(el.get("h", 0.1)) * H * 0.8))))
        color = _ass_color(st.get("color", "#FFFFFF"))
        outline = _ass_color(st.get("outline_color", "#000000"))
        outline_w = int(st.get("outline_width", 0) or 0)
        bold = 1 if st.get("weight", 700) >= 700 else 0
        align_map = {"left": 7, "center": 8, "right": 9}
        align = align_map.get(st.get("align", "center"), 8)
        style_name = f"T{i}"
        styles.append(
            f"Style: {style_name},{font},{size},{color},&H000000FF,{outline},&H00000000,"
            f"{bold},0,0,0,100,100,0,0,1,{outline_w},0,{align},0,0,0,1"
        )
        x = float(el.get("x", 0))
        y = float(el.get("y", 0))
        w = float(el.get("w", 1))
        px = _px(x, W)
        py = _px(y, H)
        if align == 8:
            px = _px(x + w / 2, W)
        elif align == 9:
            px = _px(x + w, W)
        text = (el.get("content") or "").replace("\n", "\\N").replace("}", "\\}")
        events.append(
            f"Dialogue: 0,0:00:00.00,{end},{style_name},,0,0,0,,"
            f"{{\\pos({px},{py})}}{{\\an{align}}}{text}"
        )

    Path(out_path).write_text(header + "\n".join(styles) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


def apply_template(base_vf: str, template: dict, duration: float, temp_dir: Path) -> str:
    """Compõe o template sobre o filtergraph base e devolve o novo filtergraph."""
    suffix = "fps=30,format=yuv420p"
    if suffix not in base_vf:
        return base_vf
    main = base_vf.replace(suffix, "").rstrip(",")

    # o graph base pode já terminar com um label (ex.: [out] do logo da marca);
    # reaproveita esse label em vez de criar um novo.
    import re

    m = re.search(r"\[(\w+)\]$", main)
    if m:
        video_label, main = m.group(1), main
    else:
        main, video_label = main + "[main]", "main"

    elements = template.get("elements") or []
    bg = template.get("background") or {}
    slot = next((el for el in elements if el.get("type") == "video_slot"), None)

    parts: list[str] = []
    stage = video_label
    use_bg = slot is not None and bg.get("type") in ("color", "gradient", "image")

    if use_bg:
        parts.append(main)
        parts.append(_bg_source(bg))
        sw = _px(float(slot.get("w", 1.0)), W)
        sh = _px(float(slot.get("h", 0.5)), H)
        sx = _px(float(slot.get("x", 0.0)), W)
        sy = _px(float(slot.get("y", 0.0)), H)
        parts.append(
            f"[{video_label}]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
            f"crop={sw}:{sh}[vid]"
        )
        parts.append(f"[bg][vid]overlay={sx}:{sy}[stage]")
        stage = "stage"
    else:
        parts.append(main)
        stage = video_label

    # formas
    for el in elements:
        if el.get("type") != "shape":
            continue
        st = el.get("style") or {}
        kind = st.get("shape", "rect")
        color = _hex_no_hash(st.get("color", "#000000"))
        opacity = float(st.get("opacity", 1.0))
        outline = int(st.get("outline") or 0)
        x = _px(float(el.get("x", 0)), W)
        y = _px(float(el.get("y", 0)), H)
        w = _px(float(el.get("w", 1)), W)
        h = _px(float(el.get("h", 0.1)), H)
        col = f"0x{color}@{opacity}"
        if kind == "circle":
            r = max(1, w // 2)
            if outline > 0:
                parts.append(f"[{stage}]drawcircle=x={x + w // 2}:y={y + h // 2}:r={r}:color={col}:t={outline}[{stage}]")
            else:
                parts.append(f"[{stage}]drawcircle=x={x + w // 2}:y={y + h // 2}:r={r}:color={col}:t=fill[{stage}]")
        else:
            if outline > 0:
                parts.append(f"[{stage}]drawbox=x={x}:y={y}:w={w}:h={h}:color={col}:t={outline}[{stage}]")
            else:
                parts.append(f"[{stage}]drawbox=x={x}:y={y}:w={w}:h={h}:color={col}:t=fill[{stage}]")

    # imagens / logos
    for el in elements:
        if el.get("type") not in ("image", "logo"):
            continue
        path = el.get("content") or ""
        if not path or not Path(path).exists():
            continue
        iw = _px(float(el.get("w", 0.2)), W)
        ih = _px(float(el.get("h", 0.2)), H)
        ix = _px(float(el.get("x", 0)), W)
        iy = _px(float(el.get("y", 0)), H)
        parts.append(
            f"movie={_filter_path(path)},scale={iw}:{ih}:force_original_aspect_ratio=decrease[img];"
            f"[{stage}][img]overlay={ix}:{iy}[{stage}]"
        )

    # textos (ASS)
    texts = [el for el in elements if el.get("type") == "text" and el.get("content")]
    if texts:
        ass_path = temp_dir / "template_texts.ass"
        _build_template_ass(texts, duration, str(ass_path))
        parts.append(f"[{stage}]subtitles={_filter_path(str(ass_path))}[{stage}]")

    parts.append(f"[{stage}]{suffix}")
    return ";".join(parts)


def render_preview(template: dict, out_path: Path, work_dir: Path | None = None) -> Path:
    """Renderiza um frame (270x480) do template sobre vídeo sintético para preview."""
    import tempfile

    from app.utils import ffmpeg as ff

    tmp = work_dir or Path(tempfile.mkdtemp(prefix="tpl_preview_"))
    src = tmp / "base.mp4"
    # vídeo sintético 1080x1920 (preenche o slot), 2.5s
    ff.run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=2.5",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        str(src),
    ])
    vf = apply_template("scale=1080:1920,fps=30,format=yuv420p", template, 2.5, tmp)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ff.run_ffmpeg([
        "-ss", "1.0",
        "-i", str(src),
        "-frames:v", "1",
        "-vf", f"{vf},scale=270:480",
        "-q:v", "3",
        str(out_path),
    ])
    return out_path
