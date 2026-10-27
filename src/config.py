"""Загрузка и слияние конфигурации."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "camera": {
        "index": 0,
        "width": 640,
        "height": 480,
        "mirror": True,
    },
    "hand_landmarker": {
        "model_path": "models/hand_landmarker.task",
        "num_hands": 1,
        "min_detection_confidence": 0.6,
        "min_presence_confidence": 0.6,
        "min_tracking_confidence": 0.6,
    },
    "gesture": {
        "hold_ms": 500,
        "cooldown_ms": 1500,
        "extended_angle": 150.0,
        "curled_angle": 100.0,
    },
    "actions": {
        "closed_fist": "mute",
        "open_palm": "unmute",
        "victory": "toggle",
    },
    "safety": {
        "skip_mute_while_recording": True,
        "restore_mic_on_exit": True,
    },
    "feedback": {
        "beep": True,
        "show_preview": True,
    },
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> Dict[str, Any]:
    """Читает config.json и дополняет его значениями по умолчанию."""
    if not path.exists():
        return deepcopy(DEFAULTS)
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _merge(DEFAULTS, data)
