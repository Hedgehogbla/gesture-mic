"""Глобальные медиа-клавиши Windows.

Их доставляет активная медиа-сессия: Яндекс Музыка (приложение или вкладка
браузера), Spotify, любой другой плеер. Отдельный API у Яндекс Музыки не
нужен — Windows сам решает, кто сейчас играет.
"""
from __future__ import annotations

from win32_input import (
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PLAY_PAUSE,
    VK_MEDIA_PREV_TRACK,
    tap_key,
)


class MediaKeys:
    name = "Media keys"

    def play_pause(self) -> None:
        tap_key(VK_MEDIA_PLAY_PAUSE)

    def next_track(self) -> None:
        tap_key(VK_MEDIA_NEXT_TRACK)

    def previous_track(self) -> None:
        tap_key(VK_MEDIA_PREV_TRACK)
