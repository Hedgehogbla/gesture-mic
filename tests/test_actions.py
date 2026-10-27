"""Диспетчер действий: медиа-клавиши и мут, без реального ввода."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32_input  # noqa: E402
from actions import ActionRunner  # noqa: E402


class FakeMute:
    name = "fake"

    def __init__(self) -> None:
        self._muted = False

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    def toggle(self) -> None:
        self._muted = not self._muted


class MediaActionTests(unittest.TestCase):
    def test_play_pause(self) -> None:
        runner = ActionRunner(None)
        with patch("media.tap_key") as tap:
            text, state = runner.run("play_pause")
        tap.assert_called_once_with(win32_input.VK_MEDIA_PLAY_PAUSE)
        self.assertEqual(text, "PLAY PAUSE")
        self.assertIsNone(state)

    def test_next_track(self) -> None:
        runner = ActionRunner(None)
        with patch("media.tap_key") as tap:
            text, _ = runner.run("next_track")
        tap.assert_called_once_with(win32_input.VK_MEDIA_NEXT_TRACK)
        self.assertEqual(text, "NEXT TRACK")

    def test_prev_track(self) -> None:
        runner = ActionRunner(None)
        with patch("media.tap_key") as tap:
            text, _ = runner.run("prev_track")
        tap.assert_called_once_with(win32_input.VK_MEDIA_PREV_TRACK)
        self.assertEqual(text, "PREV TRACK")


class MuteActionTests(unittest.TestCase):
    def test_toggle_returns_new_state(self) -> None:
        runner = ActionRunner(FakeMute())
        text, state = runner.run("toggle")
        self.assertTrue(state)
        self.assertEqual(text, "TOGGLE -> MUTED")

    def test_mute_and_unmute(self) -> None:
        mute = FakeMute()
        runner = ActionRunner(mute)
        runner.run("mute")
        self.assertTrue(mute.muted)
        runner.run("unmute")
        self.assertFalse(mute.muted)

    def test_without_backend(self) -> None:
        runner = ActionRunner(None)
        text, state = runner.run("toggle")
        self.assertEqual(text, "NO MUTE BACKEND")
        self.assertIsNone(state)


if __name__ == "__main__":
    unittest.main()
