"""Стабилизатор: удержание, сброс при смене жеста, пауза между срабатываниями."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stabilizer import GestureStabilizer  # noqa: E402


class StabilizerTests(unittest.TestCase):
    def test_fires_only_after_hold(self) -> None:
        stabilizer = GestureStabilizer(hold_ms=500, cooldown_ms=1500)

        self.assertFalse(stabilizer.update("point", 0.0).fired)
        self.assertFalse(stabilizer.update("point", 0.25).fired)
        self.assertAlmostEqual(stabilizer.update("point", 0.25).progress, 0.5)

        decision = stabilizer.update("point", 0.5)
        self.assertTrue(decision.fired)
        self.assertEqual(decision.progress, 1.0)

    def test_does_not_fire_twice_while_held(self) -> None:
        stabilizer = GestureStabilizer(hold_ms=500, cooldown_ms=1500)
        stabilizer.update("point", 0.0)
        self.assertTrue(stabilizer.update("point", 0.5).fired)
        self.assertFalse(stabilizer.update("point", 0.6).fired)
        self.assertFalse(stabilizer.update("point", 0.7).fired)

    def test_changing_gesture_restarts_the_timer(self) -> None:
        stabilizer = GestureStabilizer(hold_ms=500, cooldown_ms=0)
        stabilizer.update("point", 0.0)
        stabilizer.update("victory", 0.2)
        self.assertFalse(stabilizer.update("victory", 0.6).fired)  # прошло 0.4 с
        self.assertTrue(stabilizer.update("victory", 0.8).fired)   # прошло 0.6 с

    def test_cooldown_blocks_immediate_second_trigger(self) -> None:
        stabilizer = GestureStabilizer(hold_ms=500, cooldown_ms=1500)
        stabilizer.update("point", 0.0)
        self.assertTrue(stabilizer.update("point", 0.5).fired)

        stabilizer.update(None, 0.7)
        stabilizer.update("point", 0.8)
        self.assertFalse(stabilizer.update("point", 1.5).fired)  # cooldown ещё идёт
        self.assertTrue(stabilizer.update("point", 2.1).fired)

    def test_no_gesture_never_fires(self) -> None:
        stabilizer = GestureStabilizer(hold_ms=0, cooldown_ms=0)
        self.assertFalse(stabilizer.update(None, 1.0).fired)


if __name__ == "__main__":
    unittest.main()
