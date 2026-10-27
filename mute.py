"""Где именно происходит выключение микрофона.

Модуль спрятан за маленьким интерфейсом MuteBackend: остальной код не
знает, каким способом глушится звук. Сегодня это системный микрофон
Windows, завтра можно добавить Discord, Zoom или что-то ещё — main.py
менять не придётся.
"""
from __future__ import annotations

from typing import Optional, Protocol


class MuteError(RuntimeError):
    """Не удалось получить доступ к микрофону."""


class MuteBackend(Protocol):
    name: str

    @property
    def muted(self) -> Optional[bool]:
        """True/False, если состояние известно; None, если нет."""
        ...

    def set_muted(self, muted: bool) -> None: ...

    def toggle(self) -> None: ...


class WindowsMic:
    """Системный микрофон по умолчанию через Windows Core Audio (pycaw)."""

    name = "Windows microphone"

    def __init__(self) -> None:
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise MuteError(f"pycaw/comtypes недоступны: {exc}") from exc

        try:
            device = AudioUtilities.GetMicrophone()
            if device is None:
                raise MuteError("микрофон по умолчанию не найден")
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._volume = interface.QueryInterface(IAudioEndpointVolume)
        except MuteError:
            raise
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise MuteError(f"нет доступа к микрофону: {exc}") from exc

    @property
    def muted(self) -> bool:
        return bool(self._volume.GetMute())

    def set_muted(self, muted: bool) -> None:
        self._volume.SetMute(1 if muted else 0, None)

    def toggle(self) -> None:
        self.set_muted(not self.muted)
