"""Скелет кисти и HUD поверх кадра — чтобы видеть, что понял алгоритм."""
from __future__ import annotations

from typing import Optional, Sequence

import cv2

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

WHITE = (235, 235, 235)
GREY = (170, 170, 170)
GREEN = (90, 200, 90)
RED = (70, 70, 230)
ORANGE = (0, 190, 255)


def _xy(point: Sequence[float]) -> tuple[int, int]:
    return int(point[0]), int(point[1])


def draw_landmarks(frame, points: Sequence[Sequence[float]]) -> None:
    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, _xy(points[start]), _xy(points[end]), ORANGE, 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, _xy(point), 3, (0, 0, 255), -1, cv2.LINE_AA)


def draw_hud(
    frame,
    *,
    gesture: str,
    progress: float,
    muted: Optional[bool],
    action_text: str,
    fps: float,
    backend: str,
) -> None:
    height, width = frame.shape[:2]

    shade = frame.copy()
    cv2.rectangle(shade, (0, 0), (width, 92), (18, 18, 18), -1)
    cv2.addWeighted(shade, 0.55, frame, 0.45, 0, frame)

    if muted is None:
        state_text, state_color = "MIC ?", ORANGE
    elif muted:
        state_text, state_color = "MIC OFF", RED
    else:
        state_text, state_color = "MIC ON", GREEN
    cv2.putText(frame, state_text, (16, 40), cv2.FONT_HERSHEY_DUPLEX, 1.1, state_color, 2, cv2.LINE_AA)

    label = gesture if gesture and gesture != "none" else "-"
    cv2.putText(frame, f"gesture: {label}", (16, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 1, cv2.LINE_AA)
    cv2.putText(frame, backend, (width - 300, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.42, GREY, 1, cv2.LINE_AA)

    bar_x, bar_y, bar_w, bar_h = width - 246, 30, 220, 12
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), GREY, 1)
    filled = int(bar_w * max(0.0, min(1.0, progress)))
    if filled > 0:
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled, bar_y + bar_h), ORANGE, -1)
    cv2.putText(frame, "hold", (bar_x, bar_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREY, 1, cv2.LINE_AA)

    if action_text:
        cv2.putText(frame, action_text, (16, height - 48), cv2.FONT_HERSHEY_DUPLEX, 0.85, GREEN, 2, cv2.LINE_AA)

    cv2.putText(frame, "Q / Esc - exit", (16, height - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREY, 1, cv2.LINE_AA)
    cv2.putText(frame, f"{fps:4.1f} fps", (width - 92, height - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREY, 1, cv2.LINE_AA)
