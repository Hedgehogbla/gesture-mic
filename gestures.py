"""21 точка кисти → имя жеста.

MediaPipe нумерует точки так:

    0      запястье
    1–4    большой палец  (CMC, MCP, IP, TIP)
    5–8    указательный   (MCP, PIP, DIP, TIP)
    9–12   средний
    13–16  безымянный
    17–20  мизинец

У каждого пальца берём три точки: основание (MCP), средний сустав (PIP)
и кончик (TIP). Если угол в среднем суставе близок к 180°, палец выпрямлен.

Точки приходят уже в пикселях — (x*w, y*h, z*w). Считать углы в
нормализованных координатах нельзя: у кадра разные масштабы по x и y,
и прямой палец «искривится» в математике.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

import numpy as np

# Палец: (MCP, PIP, TIP). Большой палец устроен иначе, поэтому его
# проверяем отдельно и только чтобы отличить кулак от "thumbs up".
FINGERS: Mapping[str, tuple[int, int, int]] = {
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}
THUMB = (1, 2, 4)

DEFAULT_ANGLE = 150.0


def angle(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    """Угол ABC в градусах — угол между векторами BA и BC."""
    first = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    second = np.asarray(c, dtype=float) - np.asarray(b, dtype=float)
    length = float(np.linalg.norm(first) * np.linalg.norm(second))
    if length < 1e-6:
        return 0.0
    cosine = float(np.dot(first, second) / length)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def is_extended(points: Sequence[Sequence[float]], joints: tuple[int, int, int], threshold: float) -> bool:
    mcp, pip, tip = joints
    return angle(points[mcp], points[pip], points[tip]) > threshold


def extended_fingers(points: Sequence[Sequence[float]], threshold: float = DEFAULT_ANGLE) -> dict[str, bool]:
    """Какие из четырёх пальцев выпрямлены."""
    return {name: is_extended(points, joints, threshold) for name, joints in FINGERS.items()}


def classify(points: Optional[Sequence[Sequence[float]]], threshold: float = DEFAULT_ANGLE) -> str:
    """Возвращает имя жеста: point, open_palm, closed_fist, victory, thumb, unknown, none."""
    if points is None or len(points) < 21:
        return "none"

    fingers = extended_fingers(points, threshold)
    count = sum(fingers.values())

    if count == 4:
        return "open_palm"
    if count == 0:
        return "thumb" if is_extended(points, THUMB, threshold) else "closed_fist"
    if fingers["index"] and fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
        return "victory"
    if fingers["index"] and not (fingers["middle"] or fingers["ring"] or fingers["pinky"]):
        return "point"
    return "unknown"
