"""Backend Discord: разбор хоткея и учёт состояния (без реального нажатия клавиш)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mute  # noqa: E402


class HotkeyParsingTests(unittest.TestCase):
    def test_parses_modifiers_and_letter(self) -> None:
        self.assertEqual(mute.parse_hotkey("ctrl+shift+m"), [0x11, 0x10, 0x4D])

    def test_is_case_insensitive(self) -> None:
        self.assertEqual(mute.parse_hotkey("Ctrl+Shift+M"), mute.parse_hotkey("ctrl+shift+m"))

    def test_rejects_unknown_key(self) -> None:
        with self.assertRaises(ValueError):
            mute.parse_hotkey("ctrl+banana")


class DiscordHotkeyTests(unittest.TestCase):
    def test_toggle_flips_tracked_state(self) -> None:
        backend = mute.DiscordHotkey("ctrl+shift+m")
        with patch("mute.send_hotkey") as send:
            backend.toggle()
            self.assertTrue(backend.muted)
            backend.toggle()
            self.assertFalse(backend.muted)
            self.assertEqual(send.call_count, 2)

    def test_set_muted_presses_keys_only_when_state_changes(self) -> None:
        backend = mute.DiscordHotkey("ctrl+shift+m")
        with patch("mute.send_hotkey") as send:
            backend.set_muted(False)
            send.assert_not_called()
            backend.set_muted(True)
            send.assert_called_once()
            self.assertTrue(backend.muted)


if __name__ == "__main__":
    unittest.main()
