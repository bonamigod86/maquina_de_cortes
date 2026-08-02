"""Reenquadramento vertical (9:16) com detecção e suavização de rosto.

Detecção facial via modelo YOLOv8-face (ONNX) executada com onnxruntime —
funciona com OpenCV 5 (que removeu as Haar cascades).
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
_INPUT_SIZE = 640
_STRIDES = (8, 16, 32)
_SCALE_NAMES = ("8", "16", "32")

_lock = threading.Lock()
_session = None
_model_ready = False


def _model_path() -> str:
    from app.core.config import MODELS_CACHE

    MODELS_CACHE.mkdir(parents=True, exist_ok=True)
    path = MODELS_CACHE / "face_detection_yunet_2023mar.onnx"
    if not path.exists():
        import httpx

        with httpx.Client(timeout=120, follow_redirects=True) as client:
            r = client.get(MODEL_URL)
            r.raise_for_status()
            path.write_bytes(r.content)
    return str(path)


def _get_session():
    """Cria sessão onnxruntime sob demanda (thread-safe)."""
    global _session, _model_ready
    with _lock:
        if _session is None:
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            so.intra_op_num_threads = 2
            _session = ort.InferenceSession(_model_path(), so, providers=["CPUExecutionProvider"])
            _model_ready = True
        return _session


def scaled_dims(width: int, height: int, out_w: int = 1080, out_h: int = 1920) -> tuple[int, int]:
    """Dimensões após escala que cobre a área vertical."""
    s = max(out_w / width, out_h / height)
    return int(round(width * s / 2) * 2), int(round(height * s / 2) * 2)


def _letterbox(img: np.ndarray) -> tuple[np.ndarray, float, float]:
    h, w = img.shape[:2]
    scale = min(_INPUT_SIZE / w, _INPUT_SIZE / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    import cv2

    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((_INPUT_SIZE, _INPUT_SIZE, 3), 127, dtype=np.uint8)
    x0, y0 = (_INPUT_SIZE - nw) // 2, (_INPUT_SIZE - nh) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return canvas, scale, x0, y0


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _nms(boxes: list[tuple[float, float, float, float]], scores: list[float], thr: float = 0.45) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    keep: list[int] = []
    while order:
        i = order.pop(0)
        keep.append(i)
        bx1, by1, bx2, by2 = boxes[i]
        order = [
            j
            for j in order
            if not (
                min(bx2, boxes[j][2]) > max(bx1, boxes[j][0])
                and min(by2, boxes[j][3]) > max(by1, boxes[j][1])
            )
        ]
    return keep


def detect_faces(frame_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detecta rostos (YOLOv8-face); retorna lista de (x, y, w, h) no frame original."""
    try:
        session = _get_session()
    except Exception:
        return []
    import cv2

    # Este modelo espera entrada bruta [0, 255] (não normalizar por /255).
    canvas, scale, x0, y0 = _letterbox(frame_bgr)
    blob = canvas.astype(np.float32).transpose(2, 0, 1)[None, ...]
    outputs = session.run(None, {session.get_inputs()[0].name: blob})
    outs = {o.name: arr for o, arr in zip(session.get_outputs(), outputs)}

    raw_boxes: list[tuple[float, float, float, float]] = []
    raw_scores: list[float] = []
    for stride, name in zip(_STRIDES, _SCALE_NAMES):
        cls = outs.get(f"cls_{name}", np.zeros((1, 0, 1), dtype=np.float32))[0, :, 0]
        obj = outs.get(f"obj_{name}", np.zeros((1, 0, 1), dtype=np.float32))[0, :, 0]
        bbox = outs.get(f"bbox_{name}", np.zeros((1, 0, 4), dtype=np.float32))[0]
        grid_h = int(np.sqrt(len(obj)))
        grid_w = grid_h
        conf = _sigmoid(cls) * _sigmoid(obj)
        for i in range(len(conf)):
            c = float(conf[i])
            if c < 0.35:
                continue
            row, col = divmod(i, grid_w)
            cx = (col + bbox[i, 0]) * stride
            cy = (row + bbox[i, 1]) * stride
            w = bbox[i, 2] * stride
            h = bbox[i, 3] * stride
            raw_boxes.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
            raw_scores.append(c)
    if not raw_boxes:
        return []

    inv = 1.0 / scale
    picked = _nms(raw_boxes, raw_scores)
    out: list[tuple[int, int, int, int]] = []
    fw, fh = frame_bgr.shape[1], frame_bgr.shape[0]
    min_box = max(16, round(min(fw, fh) * 0.05))
    for i in picked:
        x1, y1, x2, y2 = raw_boxes[i]
        x = (x1 - x0) * inv
        y = (y1 - y0) * inv
        w = (x2 - x1) * inv
        h = (y2 - y1) * inv
        if w >= min_box and h >= min_box and 0 <= x < fw and 0 <= y < fh:
            out.append((int(x), int(y), int(w), int(h)))
    return out[:3]


def sample_faces(
    video_path: str,
    t0: float,
    t1: float,
    min_face_dur: float = 0.6,
    min_gap_dur: float = 0.5,
    on_progress=None,
    cancel_event=None,
) -> tuple[list[tuple[float, float, float]] | None, list[tuple[float, float]]]:
    """Amostra o rosto ao longo do trecho (coords normalizadas 0-1) em uma passada.

    Retorna (anchors, face_segments):
      - anchors: lista de (t, cx, cy) — cx/cy normalizados entre 0 e 1,
        suavizados com EMA. None se nenhum rosto foi encontrado (fallback).
      - face_segments: lista de (início, fim) em tempo absoluto do source em que
        o rosto está presente de forma consistente (histerese evita piscar).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    duration = max(t1 - t0, 0.1)
    cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)

    sample_interval = max(0.4, min(0.8, duration / 300))
    # limita o nº de amostras para vídeos longos: cada âncora vira um if() na
    # expressão do crop e o ffmpeg falha com expressões muito grandes (~>80).
    sample_interval = max(sample_interval, duration / 60)
    samples: list[tuple[float, bool]] = []
    raw_anchors: list[tuple[float, float, float]] = []
    t = t0
    found_any = False
    ema: tuple[float, float] | None = None

    while t < t1:
        if cancel_event is not None and cancel_event.is_set():
            cap.release()
            raise RuntimeError("Reenquadramento cancelado")
        if on_progress:
            on_progress(min((t - t0) / duration, 1.0))
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            # leitura falhou (seek em container problemático): registra fallback
            # para não deixar buracos na timeline nem deslocar as âncoras.
            if ema is None:
                ema = (0.5, 0.35)
            samples.append((t, False))
            raw_anchors.append((t, round(ema[0], 4), round(max(min(ema[1], 0.55), 0.15), 4)))
            t += sample_interval
            continue
        faces = detect_faces(frame)
        has_face = bool(faces)
        cx, cy = 0.5, 0.5
        if faces:
            best = max(faces, key=lambda f: f[2] * f[3])
            bx, by, bw, bh = best
            cx = (bx + bw / 2) / width
            cy = (by + bh / 2) / height
            found_any = True
        # suavização exponencial (evita tremida) — peso maior no dado novo p/ menos lag
        if ema is None:
            ema = (cx, cy)
        else:
            ema = (ema[0] * 0.30 + cx * 0.70, ema[1] * 0.30 + cy * 0.70)
        # suaviza y para manter a cabeça no terço superior/superior da tela
        cy_smoothed = min(ema[1], 0.55)
        samples.append((t, has_face))
        raw_anchors.append((t, round(ema[0], 4), round(max(cy_smoothed, 0.15), 4)))
        t += sample_interval

    cap.release()
    if not raw_anchors:
        return None, []
    anchors = list(raw_anchors)
    # garante ancoras nos limites exatos
    if abs(anchors[0][0] - t0) > 0.01:
        anchors.insert(0, (t0, anchors[0][1], anchors[0][2]))
    if abs(anchors[-1][0] - t1) > 0.01:
        anchors.append((t1, anchors[-1][1], anchors[-1][2]))
    if not found_any:
        return None, []
    return anchors, _face_segments(samples, min_face_dur, min_gap_dur)


def _face_segments(
    samples: list[tuple[float, bool]],
    min_face_dur: float = 0.6,
    min_gap_dur: float = 0.5,
) -> list[tuple[float, float]]:
    """Converte amostras de presença de rosto em segmentos estáveis (histerese)."""
    if not samples:
        return []
    # runs contíguos com rosto
    runs: list[tuple[float, float]] = []
    start: float | None = None
    for t, has in samples:
        if has and start is None:
            start = t
        elif not has and start is not None:
            runs.append((start, t))
            start = None
    if start is not None:
        runs.append((start, samples[-1][0]))
    # junta runs separados por buracos curtos (evita piscar)
    merged: list[list[float]] = []
    for s, e in runs:
        if merged and s - merged[-1][1] < min_gap_dur:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    # descarta trechos de rosto muito curtos
    return [(s, e) for s, e in merged if e - s >= min_face_dur]


def crop_expressions(
    anchors: list[tuple[float, float, float]],
    scaled_w: int,
    scaled_h: int,
    out_w: int = 1080,
    out_h: int = 1920,
) -> tuple[str, str]:
    """Gera expressões ffmpeg x(t)/y(t) com interpolação linear entre âncoras."""
    max_x = scaled_w - out_w
    max_y = scaled_h - out_h
    mid_x = max_x / 2
    mid_y = max_y / 2
    vals: list[tuple[float, float, float]] = []
    for t, cx, cy in anchors:
        x = max(0.0, min(cx * scaled_w - out_w / 2, max_x))
        y = max(0.0, min(cy * scaled_h - out_h / 2, max_y))
        vals.append((t, x, y))

    # colapsa âncoras redundantes (mesma posição em sequência): manter cada
    # âncora gera um `if(...)` aninhado e o ffmpeg falha em expressões gigantes
    # ("Failed to configure input pad" / -22). Trechos estáticos viram 2 âncoras.
    if len(vals) > 2:
        collapsed: list[tuple[float, float, float]] = [vals[0]]
        for i in range(1, len(vals) - 1):
            t, x, y = vals[i]
            pv, nv = collapsed[-1], vals[i + 1]
            if (
                abs(x - pv[1]) < 0.5
                and abs(y - pv[2]) < 0.5
                and abs(x - nv[1]) < 0.5
                and abs(y - nv[2]) < 0.5
            ):
                continue
            collapsed.append((t, x, y))
        collapsed.append(vals[-1])
        vals = collapsed

    # cinto de segurança: nunca passa de ~60 âncoras (limite do parser do ffmpeg)
    if len(vals) > 60:
        step = max(1, len(vals) // 60)
        vals = [vals[0]] + [vals[i] for i in range(step, len(vals) - 1, step)] + [vals[-1]]

    def build(vals: list[tuple[float, float, float]], clamp_max: int | float) -> str:
        # clamp_max pode ser 0 (já coberto); nunca negativo, senão clip() do
        # ffmpeg vira comportamento indefinido. clamp() evita extrapolação
        # fora do frame (causa do erro "Failed to configure input pad").
        c = max(float(clamp_max), 0.0)
        # último trecho: constante
        expr = f"clip({vals[-1][1]:.2f},0,{c:.2f})"
        for i in range(len(vals) - 2, -1, -1):
            t0, x0 = vals[i][0], vals[i][1]
            t1, x1 = vals[i + 1][0], vals[i + 1][1]
            span = max(t1 - t0, 1e-4)
            # if(lt(t,t1), x0+(t-t0)*(x1-x0)/span, expr)
            seg = f"clip({x0:.2f}+(t-{t0:.2f})*({(x1 - x0) / span:.4f}),0,{c:.2f})"
            expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
        return expr

    x_expr = build(vals, max_x)
    y_expr = build([(t, y) for t, _, y in vals], max_y)
    return x_expr, y_expr


def center_crop_exprs(scaled_w: int, scaled_h: int, out_w: int = 1080, out_h: int = 1920) -> tuple[str, str]:
    max_x = scaled_w - out_w
    max_y = scaled_h - out_h
    return str(max_x / 2), str(max_y / 2)
