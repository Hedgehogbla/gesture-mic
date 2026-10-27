"""Фильтр дребезга: жест должен удержаться и срабатывает один раз.

Зачем это нужно: распознавание — вероятностное. В одном кадре рука
похожа на жест, в следующем — нет. Без фильтра микрофон будет
переключаться по десять раз в секунду.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Decision:
    gesture: Optional[str]
    fired: bool
    progress: float


class GestureStabilizer:
    def __init__(self, hold_ms: float, cooldown_ms: float) -> None:
        self._hold = max(0.0, float(hold_ms)) / 1000.0
        self._cooldown = max(0.0, float(cooldown_ms)) / 1000.0
        self._candidate: Optional[str] = None
        self._since = 0.0
        self._last_fire = float("-inf")
        self._fired = False

    def update(self, gesture: Optional[str], now: float) -> Decision:
        # Жест сменился — начинаем отсчёт заново.
        if gesture != self._candidate:
            self._candidate = gesture
            self._since = now
            self._fired = False

        if not gesture:
            return Decision(None, False, 0.0)

        elapsed = now - self._since
        progress = 1.0 if self._hold <= 0 else min(1.0, elapsed / self._hold)

        fired = False
        if not self._fired and elapsed >= self._hold and (now - self._last_fire) >= self._cooldown:
            self._fired = True
            self._last_fire = now
            fired = True

        return Decision(gesture, fired, progress)
