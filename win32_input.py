"""Низкоуровневый ввод Windows: SendInput.

Один модуль на всё, что «нажимает клавиши»: горячие клавиши Discord и
медиа-клавиши. Остальной код не должен знать про ctypes и структуры Win32.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

# Virtual-Key codes: https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes
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

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

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


def tap_key(code: int) -> None:
    """Короткое нажатие одной клавиши (медиа-клавиши, F-клавиши и т.п.)."""
    send_hotkey([code])
