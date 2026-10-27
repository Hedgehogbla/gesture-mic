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

import ctypes
import time
from ctypes import wintypes
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


# --- Discord: эмуляция горячей клавиши через Win32 SendInput ---------------

VK_CODES: dict[str, int] = {
    "ctrl": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "space": 0x20,
    "tab": 0x09,
}
for _letter in "abcdefghijklmnopqrstuvwxyz":
    VK_CODES[_letter] = ord(_letter.upper())
for _digit in "0123456789":
    VK_CODES[_digit] = ord(_digit)
del _letter, _digit

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _INPUT(ctypes.Structure):
    # SendInput принимает массив INPUT, где лежит union клавиатуры и мыши.
    # Без мышиной части размер структуры не совпадёт с ожидаемым Windows.
    class _UNION(ctypes.Union):
        _fields_ = (("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT))

    _anonymous_ = ("u",)
    _fields_ = (("type", wintypes.DWORD), ("u", _UNION))


def parse_hotkey(text: str) -> list[int]:
    """'ctrl+shift+m' -> [0x11, 0x10, 0x4D]."""
    codes = []
    for part in text.lower().split("+"):
        part = part.strip()
        if part not in VK_CODES:
            raise ValueError(f"неизвестная клавиша {part!r} в hotkey {text!r}")
        codes.append(VK_CODES[part])
    if not codes:
        raise ValueError("hotkey пустой")
    return codes


def _key_event(code: int, *, up: bool) -> _INPUT:
    event = _INPUT()
    event.type = INPUT_KEYBOARD
    event.ki = _KEYBDINPUT(
        wVk=code,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if up else 0,
        time=0,
        dwExtraInfo=None,
    )
    return event


def _send(events: list[_INPUT]) -> None:
    array = (_INPUT * len(events))(*events)
    sent = ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))
    if sent != len(events):
        raise OSError(f"SendInput отправил {sent} из {len(events)} событий")


def send_hotkey(codes: list[int], hold_s: float = 0.03) -> None:
    """Нажимает и отпускает комбинацию клавиш."""
    _send([_key_event(code, up=False) for code in codes])
    time.sleep(hold_s)
    _send([_key_event(code, up=True) for code in reversed(codes)])


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


# --- Windows: системный микрофон через Core Audio --------------------------

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
