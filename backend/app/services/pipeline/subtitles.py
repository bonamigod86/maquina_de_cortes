"""GeraÃ§Ã£o de legendas ASS com estilos (TikTok, Instagram, Minimalista, KaraokÃª)."""
from __future__ import annotations

import re
from pathlib import Path

STYLE_PRESETS = {
    "tiktok": {
        "font": "Arial Black",
        "font_size": 72,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 5,
        "shadow": True,
        "position": "bottom",
        "animation": "pop",
        "words_per_line": 5,
    },
    "instagram": {
        "font": "Montserrat ExtraBold",
        "font_size": 64,
        "color": "#FFFFFF",
        "outline_color": "#E1306C",
        "outline_width": 4,
        "shadow": True,
        "position": "bottom",
        "animation": "fade",
        "words_per_line": 5,
    },
    "minimalist": {
        "font": "Segoe UI Light",
        "font_size": 56,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "shadow": False,
        "position": "bottom",
        "animation": "none",
        "words_per_line": 5,
    },
    "word_by_word": {
        "font": "Arial Black",
        "font_size": 80,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 5,
        "shadow": True,
        "position": "bottom",
        "animation": "word_pop",
        "words_per_line": 5,
    },
    "karaoke": {
        "font": "Arial Black",
        "font_size": 76,
        "color": "#B3B3B3",
        "outline_color": "#000000",
        "outline_width": 4,
        "shadow": True,
        "position": "bottom",
        "animation": "karaoke",
        "words_per_line": 5,
    },
}

POS_Y = {"bottom": "0.85", "middle": "0.45", "top": "0.08"}


def _hex_ass(hex_color: str, alpha: str = "00") -> str:
    """Converte #RRGGBB para &HAABBGGRR (formato ASS)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{alpha}{b}{g}{r}"


def _ass_time(seconds: float) -> str:
    ms = int(round(seconds * 100))
    s = ms // 100
    centi = ms % 100
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}.{centi:02d}"


def _group_words(words: list[dict], per_line: int) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for i in range(0, len(words), per_line):
        lines.append(words[i : i + per_line])
    return lines


def _karaoke_line(word_chunks: list[list[dict]]) -> str:
    """Estilo karaokÃª: palavra corrente destacada com tag karaoke."""
    return "".join(f"{{\\k{int((w['end'] - w['start']) * 100)}}}{w['word']} " for w in word_chunks)


def _word_pop_line(word_chunks: list[list[dict]], base_style: dict) -> str:
    """Estilo palavra-por-palavra: cada palavra aparece destacada ao ser falada."""
    out = []
    for w in word_chunks:
        out.append(f"{{\\k{int((w['end'] - w['start']) * 100)}}}{{\\c{_hex_ass(base_style['color'])} \\fscx130 \\fscy130}}{w['word']} {{\\c{_hex_ass('#888888')}\\fscx100\\fscy100}}")
    return "".join(out)


def _ass_line(text: str, start: float, end: float, style: str, anim: str) -> str:
    # campo Effect preenchido com "0" Ã© obrigatÃ³rio: vazio desloca o texto
    # para o campo Effect (e MarginV fica vazio), quebrando posiÃ§Ã£o e conteÃºdo.
    fmt = f"{_ass_time(start)},{_ass_time(end)},{style}"
    if anim == "fade":
        return f"Dialogue: 0,{fmt},0,0,0,0,,{{\\fad(150,150)}}{text}"
    if anim == "bounce":
        return f"Dialogue: 0,{fmt},0,0,0,0,,{{\\pos(540,1560)}}{text}"
    return f"Dialogue: 0,{fmt},0,0,0,0,,{text}"


def build_ass(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    style_cfg: dict,
    out_path: str,
) -> str:
    """Gera arquivo .ass com legendas da janela do corte (tempos relativos)."""
    style_key = style_cfg.get("style", "tiktok")
    base = STYLE_PRESETS.get(style_key, STYLE_PRESETS["tiktok"])
    merged = {**base, **{k: v for k, v in style_cfg.items() if v not in (None, "")}}

    font = merged["font"]
    size = int(merged["font_size"])
    color = _hex_ass(merged["color"])
    outline = _hex_ass(merged["outline_color"])
    outline_w = int(merged["outline_width"])
    shadow = 4 if merged.get("shadow") else 0
    pos_key = merged.get("position", "bottom")
    pos = POS_Y.get(pos_key, "0.85")
    anim = merged.get("animation", "pop")
    per_line = max(1, int(merged.get("words_per_line", 5)))

    # ASS: Alignment + MarginV. Para alinhamento inferior, MarginV Ã© a distÃ¢ncia
    # da base do vÃ­deo (nÃ£o a coordenada Y) â€” valor grande empurra o texto para cima.
    play_res_y = 1920
    if pos_key == "top":
        align = 8
        margin_v = int(play_res_y * float(pos))
    elif pos_key == "middle":
        align = 9
        margin_v = 0
    else:  # bottom
        align = 2
        margin_v = int(play_res_y * (1.0 - float(pos)))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{size},{color},&H000000FF,{outline},&H00000000,{1 if style_key in ("tiktok", "word_by_word", "karaoke", "instagram") else 0},0,0,0,100,100,0,0,1,{outline_w},{shadow},{align},60,60,{margin_v},1
Style: Secondary,{font},{int(size * 0.9)},&H00AAAAAA,&H000000FF,{outline},&H00000000,0,0,0,0,100,100,0,0,1,{outline_w},{shadow},{align},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    rel_words = []
    for w in words:
        ws = w["start"] - clip_start
        we = w["end"] - clip_start
        if we < 0 or ws > clip_end - clip_start:
            continue
        rel_words.append(
            {
                "word": w["word"].strip(),
                "start": max(ws, 0.0),
                "end": min(we, clip_end - clip_start),
            }
        )
    # remove palavras fora da janela e palavras duplicadas no limite
    rel_words = [w for w in rel_words if w["end"] > w["start"] and w["word"]]
    if not rel_words:
        rel_words = [{"word": " ", "start": 0.0, "end": 0.5}]

    events: list[str] = []
    style = "Main"
    if anim == "karaoke":
        style = "Secondary"
        for line_words in _group_words(rel_words, per_line):
            t0 = line_words[0]["start"]
            t1 = line_words[-1]["end"]
            text = _karaoke_line(line_words)
            events.append(_ass_line(text, t0, t1, style, "none"))
    elif anim == "word_pop":
        for line_words in _group_words(rel_words, per_line):
            t0 = line_words[0]["start"]
            t1 = line_words[-1]["end"]
            text = _word_pop_line(line_words, merged)
            events.append(_ass_line(text, t0, t1, style, "none"))
    else:
        for line_words in _group_words(rel_words, per_line):
            t0 = line_words[0]["start"]
            t1 = line_words[-1]["end"]
            text = " ".join(w["word"] for w in line_words)
            events.append(_ass_line(text, t0, t1, style, anim))

    # espaÃ§a linhas que se sobrepÃµem
    events = _fix_overlaps(events)

    content = header + "\n".join(events) + "\n"
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path


def _fix_overlaps(events: list[str]) -> list[str]:
    """Empurra legendas sobrepostas para nÃ£o exibirem ao mesmo tempo."""
    parsed: list[list] = []
    for e in events:
        m = re.match(r"Dialogue: \d+,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),(Main|Secondary),(.*)", e, re.DOTALL)
        parsed.append([e, m.group(1) if m else "", m.group(2) if m else "", m.group(3) if m else "", m.group(4) if m else ""])
    for i in range(1, len(parsed)):
        prev_end = parsed[i - 1][2]
        cur_start = parsed[i][1]
        if cur_start < prev_end:
            parsed[i][1] = prev_end
            parsed[i][0] = re.sub(
                r"Dialogue: \d+,\d+:\d+:\d+\.\d+",
                "Dialogue: 0," + prev_end,
                parsed[i][0],
            )
    return [p[0] for p in parsed]


def _rel_words(words: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    """Palavras do trecho com tempos relativos ao inÃ­cio do corte."""
    out = []
    for w in words:
        ws = w["start"] - clip_start
        we = w["end"] - clip_start
        if we >= 0 and ws <= clip_end - clip_start:
            out.append(
                {"word": w["word"].strip(), "start": max(ws, 0.0), "end": min(we, clip_end - clip_start)}
            )
    return [w for w in out if w["end"] > w["start"] and w["word"]]


def _phrase_groups(words: list[dict], per_line: int = 6) -> list[list[dict]]:
    """Agrupa palavras em linhas de legenda por frase (pontuaÃ§Ã£o) ou limite."""
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        cur.append(w)
        if (w["word"].rstrip(".,!?â€¦") != w["word"] and len(cur) >= 2) or len(cur) >= per_line:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_srt(words: list[dict], clip_start: float, clip_end: float, out_path: str, per_line: int = 6) -> str:
    """Gera .srt simples a partir das palavras (agrupadas por frases)."""
    import srt

    rel_words = _rel_words(words, clip_start, clip_end)
    subs = []
    for i, g in enumerate(_phrase_groups(rel_words, per_line)):
        subs.append(
            srt.Subtitle(
                index=i + 1,
                start=__import__("datetime").timedelta(seconds=g[0]["start"]),
                end=__import__("datetime").timedelta(seconds=g[-1]["end"]),
                content=" ".join(w["word"] for w in g),
            )
        )
    Path(out_path).write_text(srt.compose(subs), encoding="utf-8")
    return out_path


def build_vtt(words: list[dict], clip_start: float, clip_end: float, out_path: str, per_line: int = 6) -> str:
    """Gera .vtt (WebVTT) a partir das palavras."""
    rel_words = _rel_words(words, clip_start, clip_end)
    lines = ["WEBVTT", ""]
    for i, g in enumerate(_phrase_groups(rel_words, per_line)):
        t0 = _vtt_time(g[0]["start"])
        t1 = _vtt_time(g[-1]["end"])
        lines.append(f"{t0} --> {t1}")
        lines.append(" ".join(w["word"] for w in g))
        lines.append("")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _vtt_time(seconds: float) -> str:
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def build_txt(sentences: list[dict], out_path: str) -> str:
    """Gera transcriÃ§Ã£o em texto puro com marcaÃ§Ãµes de tempo."""
    lines = []
    for s in sentences:
        t = f"{int(s['start']) // 60:02d}:{int(s['start']) % 60:02d}"
        lines.append(f"[{t}] {s['text']}")
    Path(out_path).write_text("\n\n".join(lines), encoding="utf-8")
    return out_path


def generate_full(project_id: str, sentences: list[dict], settings=None) -> dict[str, str]:
    """Gera legendas do vÃ­deo inteiro (srt/vtt/txt) em subtitles/."""
    from app.services.pipeline.export import all_words
    from app.services.project import ProjectStore

    duration = max((s["end"] for s in sentences), default=0.0)
    words = all_words(sentences)
    sub_dir = ProjectStore.path(project_id, "subtitles")
    sub_dir.mkdir(parents=True, exist_ok=True)
    per_line = 6
    if settings is not None:
        try:
            per_line = max(1, int(settings.subtitle_style.get("words_per_line", 5)))
        except (AttributeError, TypeError, ValueError):
            pass
    paths = {
        "srt": str(sub_dir / "transcricao.srt"),
        "vtt": str(sub_dir / "transcricao.vtt"),
        "txt": str(sub_dir / "transcricao.txt"),
    }
    build_srt(words, 0.0, duration, paths["srt"], per_line=per_line)
    build_vtt(words, 0.0, duration, paths["vtt"], per_line=per_line)
    build_txt(sentences, paths["txt"])
    return paths
