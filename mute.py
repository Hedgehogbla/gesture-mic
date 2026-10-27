"""Где именно происходит выключение микрофона.

Модуль спрятан за маленьким интерфейсом MuteBackend: остальной код не
знает, каким способом глушится звук. Два варианта:

* DiscordHotkey — нажимает глобальную горячую клавишу Discord.
* WindowsMic   — глушит системный микрофон Windows (pycaw).

Почему для Discord нужен хоткей, а не API: у Discord нет публичного
способа выключить микрофон *своего* клиента. Bot API умеет только
серверный мут участника (нужен бот на сервере), а локальный RPC для
управления голосом устарел и не гарантируется. Горячая клавиша —
официальный механизм Discord, поэтому используем его.
"""
from __future__ import annotations

from typing import Optional, Protocol

from win32_input import parse_hotkey, send_hotkey


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


class DiscordHotkey:
    """Нажимает глобальный хоткей Discord (Settings → Keybinds → Toggle Mute).

    Состояние микрофона Discord наружу не отдаёт, поэтому muted — это наша
    собственная память о том, что мы переключили. Если нажать мут в самом
    Discord, состояние в превью разъедется.
    """

    name = "Discord hotkey"

    def __init__(self, hotkey: str = "ctrl+shift+m") -> None:
        self._keys = parse_hotkey(hotkey)
        self._muted = False

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        if bool(muted) != self._muted:
            self.toggle()

    def toggle(self) -> None:
        send_hotkey(self._keys)
        self._muted = not self._muted


class WindowsMic:
    """Системный микрофон по умолчанию (pycaw)."""

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


def create_backend(name: str, hotkey: str = "ctrl+shift+m") -> MuteBackend:
    """Собирает backend по имени из config.json."""
    if name == "discord_hotkey":
        return DiscordHotkey(hotkey)
    if name == "windows_mic":
        return WindowsMic()
    raise ValueError(f"неизвестный backend {name!r}: ожидается discord_hotkey или windows_mic")
