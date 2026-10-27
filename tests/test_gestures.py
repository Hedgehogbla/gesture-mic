"""Правила классификации жестов: чистые функции, без камеры и MediaPipe."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gestures import classify, extended_fingers  # noqa: E402


def make_hand(extended: set[str], thumb_extended: bool = False) -> list[tuple[float, float, float]]:
    """Синтетическая кисть: 21 точка, где нужно — пальцы выпрямлены."""
    points = [(0.0, 0.0, 0.0)] * 21

    points[1] = (20, -10, 0)
    points[2] = (30, -20, 0)
    points[3] = (40, -30, 0)
    points[4] = (55, -45, 0) if thumb_extended else (35, -10, 0)

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

    def test_thumb_is_fist_with_thumb_out(self) -> None:
        self.assertEqual(classify(make_hand(set(), thumb_extended=True)), "thumb")

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


if __name__ == "__main__":
    unittest.main()
