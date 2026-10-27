"""Имена действий из config.json → реальные вызовы.

main.py не знает, что стоит за действием — мут Discord или медиа-клавиша.
Он просто вызывает runner.run("next_track").
"""
from __future__ import annotations

from typing import Callable, Optional

from media import MediaKeys
from mute import MuteBackend

MUTE_ACTIONS = ("mute", "unmute", "toggle")
MEDIA_ACTIONS = ("play_pause", "next_track", "prev_track")
VALID_ACTIONS = MUTE_ACTIONS + MEDIA_ACTIONS


class ActionRunner:
    def __init__(self, mute: Optional[MuteBackend]) -> None:
        self._mute = mute
        self._media = MediaKeys()

    def run(self, name: str) -> tuple[str, Optional[bool]]:
        """Выполняет действие.

        Возвращает текст для HUD и новое состояние мута (None — если действие
        не про микрофон, тогда и пищим не надо).
        """
        media: dict[str, Callable[[], None]] = {
            "play_pause": self._media.play_pause,
            "next_track": self._media.next_track,
            "prev_track": self._media.previous_track,
        }
        if name in media:
            media[name]()
            return name.replace("_", " ").upper(), None

        if self._mute is None:
            return "NO MUTE BACKEND", None

        if name == "mute":
            self._mute.set_muted(True)
        elif name == "unmute":
            self._mute.set_muted(False)
        elif name == "toggle":
            self._mute.toggle()
        else:
            return "UNKNOWN ACTION", None

        state = self._mute.muted
        label = "MUTED" if state else "ON"
        return f"{name.upper()} -> {label}", state
