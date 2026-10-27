"""Правила классификации жестов: чистые функции, без камеры и MediaPipe."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gestures import classify, extended_fingers  # noqa: E402

# Точки большого пальца (1, 2, 3, 4) для разных положений.
THUMB_POINTS = {
    "folded": ((20, -10), (30, -20), (40, -30), (35, -10)),
    "up": ((20, -10), (15, -30), (10, -50), (5, -70)),
    "right": ((20, -10), (30, -20), (45, -30), (60, -40)),
    "left": ((20, -10), (10, -5), (-15, 7), (-40, 20)),
}


def make_hand(extended: set[str], thumb: str = "folded") -> list[tuple[float, float, float]]:
    """Синтетическая кисть: 21 точка, где нужно — пальцы выпрямлены."""
    points = [(0.0, 0.0, 0.0)] * 21

    for index, (x, y) in enumerate(THUMB_POINTS[thumb], start=1):
        points[index] = (x, y, 0)

    starts = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}
    for offset, (name, mcp) in enumerate(starts.items()):
        x = -10 + offset * 10
        points[mcp] = (x, -60, 0)
        points[mcp + 1] = (x, -90, 0)
        points[mcp + 2] = (x, -105, 0)
        points[mcp + 3] = (x, -120, 0) if name in extended else (x, -70, 0)

    return points


class ClassifyTests(unittest.TestCase):
    def test_point_is_index_only(self) -> None:
        self.assertEqual(classify(make_hand({"index"})), "point")

    def test_open_palm_is_all_four(self) -> None:
        self.assertEqual(classify(make_hand({"index", "middle", "ring", "pinky"})), "open_palm")

    def test_closed_fist_is_none_extended(self) -> None:
        self.assertEqual(classify(make_hand(set())), "closed_fist")

    def test_victory_is_index_and_middle(self) -> None:
        self.assertEqual(classify(make_hand({"index", "middle"})), "victory")

    def test_other_combinations_are_unknown(self) -> None:
        self.assertEqual(classify(make_hand({"index", "ring"})), "unknown")

    def test_no_hand(self) -> None:
        self.assertEqual(classify(None), "none")
        self.assertEqual(classify([]), "none")

    def test_extended_fingers_flags(self) -> None:
        flags = extended_fingers(make_hand({"index"}))
        self.assertEqual(flags, {"index": True, "middle": False, "ring": False, "pinky": False})


class ThumbDirectionTests(unittest.TestCase):
    def test_thumb_up_has_no_direction(self) -> None:
        self.assertEqual(classify(make_hand(set(), thumb="up")), "thumb")

    def test_thumb_right(self) -> None:
        self.assertEqual(classify(make_hand(set(), thumb="right")), "thumb_right")

    def test_thumb_left(self) -> None:
        self.assertEqual(classify(make_hand(set(), thumb="left")), "thumb_left")

    def test_thumb_direction_ignored_when_fist(self) -> None:
        self.assertEqual(classify(make_hand(set(), thumb="folded")), "closed_fist")


if __name__ == "__main__":
    unittest.main()
