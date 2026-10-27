"""Классификация статических жестов по 21 точке кисти MediaPipe.

Точки передаются в пиксельных координатах (x*w, y*h, z*w), чтобы углы
не искажались разным масштабом осей кадра.

Индексы MediaPipe:
    0  запястье
    1-4   большой палец (CMC, MCP, IP, TIP)
    5-8   указательный (MCP, PIP, TIP)
    9-12  средний
    13-16 безымянный
    17-20 мизинец

Между «палец разогнут» и «палец согнут» есть мёртвая зона: расслабленная
кисть с полусогнутыми пальцами не должна выглядеть как кулак. Иначе рука,
просто лежащая в кадре, выключает микрофон.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence

import numpy as np

FINGERS: Dict[str, tuple[int, int, int]] = {
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}

# Большой палец: CMC -> MCP -> TIP. Менее стабилен, используется только
# чтобы отличить кулак от "thumbs up".
THUMB = (1, 2, 4)

DEFAULT_ANGLE = 150.0
DEFAULT_CURLED_ANGLE = 100.0


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Угол ABC в градусах: при b."""
    first = a - b
    second = c - b
    norm_first = float(np.linalg.norm(first))
    norm_second = float(np.linalg.norm(second))
    if norm_first < 1e-6 or norm_second < 1e-6:
        return 0.0
    cosine = float(np.dot(first, second) / (norm_first * norm_second))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _angle_at(points: Sequence[Sequence[float]], joints: tuple[int, int, int]) -> float:
    mcp, pip, tip = joints
    a = np.asarray(points[mcp], dtype=float)
    b = np.asarray(points[pip], dtype=float)
    c = np.asarray(points[tip], dtype=float)
    return _angle(a, b, c)


def _extended(
    points: Sequence[Sequence[float]],
    joints: tuple[int, int, int],
    threshold: float,
) -> bool:
    return _angle_at(points, joints) > threshold


def _curled(
    points: Sequence[Sequence[float]],
    joints: tuple[int, int, int],
    threshold: float,
) -> bool:
    return _angle_at(points, joints) < threshold


def classify(
    points: Optional[Sequence[Sequence[float]]],
    threshold: float = DEFAULT_ANGLE,
    curled_threshold: float = DEFAULT_CURLED_ANGLE,
) -> str:
    """Возвращает имя жеста: open_palm, closed_fist, victory, point, thumb, unknown, none."""
    if points is None or len(points) < 21:
        return "none"

    extended = {name: _extended(points, joints, threshold) for name, joints in FINGERS.items()}
    curled = {name: _curled(points, joints, curled_threshold) for name, joints in FINGERS.items()}
    count = sum(extended.values())

    if count == 4:
        return "open_palm"

    # Кулак — это явно согнутые пальцы, а не «не разогнутые». Промежуточные
    # углы (100..150) дают unknown и не выключают микрофон.
    if all(curled.values()):
        return "thumb" if _extended(points, THUMB, threshold) else "closed_fist"

    if extended["index"] and extended["middle"] and curled["ring"] and curled["pinky"]:
        return "victory"

    if extended["index"] and curled["middle"] and curled["ring"] and curled["pinky"]:
        return "point"

    return "unknown"


def hand_in_frame(
    points: Optional[Sequence[Sequence[float]]],
    width: int,
    height: int,
    margin: float = 0.02,
) -> bool:
    """True, если все 21 точка кисти попали в кадр (с небольшим отступом).

    Обрезанная краем кадра кисть часто распознаётся как кулак, поэтому такие
    кадры не должны запускать действия.
    """
    if points is None or len(points) < 21 or width <= 0 or height <= 0:
        return False

    margin_x = width * margin
    margin_y = height * margin
    for point in points:
        x = float(point[0])
        y = float(point[1])
        if x < margin_x or x > width - margin_x:
            return False
        if y < margin_y or y > height - margin_y:
            return False
    return True
