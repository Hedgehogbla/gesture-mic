"""Gesture Mic: управление микрофоном жестами руки.

Запуск:  python main.py
Выход:   Q / Esc в окне превью или Ctrl+C в консоли.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
import winsound
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp

from actions import ActionRunner, VALID_ACTIONS
from gestures import classify
from mute import MuteBackend, MuteError, create_backend
from overlay import draw_hud, draw_landmarks
from stabilizer import GestureStabilizer

ROOT = Path(__file__).resolve().parent
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
WINDOW = "Gesture Mic"

# Значения по умолчанию: config.json может переопределить любое из них.
DEFAULTS = {
    "camera": {"index": 0, "width": 640, "height": 480, "mirror": True},
    "hand_landmarker": {
        "model_path": "models/hand_landmarker.task",
        "num_hands": 1,
        "min_detection_confidence": 0.6,
        "min_presence_confidence": 0.6,
        "min_tracking_confidence": 0.6,
    },
    "gesture": {"hold_ms": 500, "cooldown_ms": 1500, "extended_angle": 150.0},
    "mute": {"backend": "discord_hotkey", "hotkey": "ctrl+shift+m"},
    "actions": {"point": "toggle"},
    "feedback": {"show_preview": True, "beep": True},
}


def load_config(path: Path) -> dict:
    """Читает config.json и дополняет его значениями по умолчанию."""
    config = json.loads(json.dumps(DEFAULTS))  # глубокая копия
    if not path.exists():
        return config
    raw = json.loads(path.read_text(encoding="utf-8"))
    for section, values in raw.items():
        if isinstance(values, dict) and isinstance(config.get(section), dict):
            config[section].update(values)
        else:
            config[section] = values
    return config


def ensure_model(path: Path) -> None:
    """Скачивает модель, если её нет рядом с проектом."""
    if path.exists() and path.stat().st_size > 1_000_000:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading hand landmark model -> {path}")
    urllib.request.urlretrieve(MODEL_URL, path)


def ascii_model_path(path: Path) -> Path:
    """MediaPipe на Windows не открывает пути с кириллицей.

    Если путь не-ASCII, копируем модель в ASCII-каталог и работаем с копией.
    """
    if str(path).isascii():
        return path

    candidates = []
    public = os.environ.get("PUBLIC")
    if public:
        candidates.append(Path(public) / "GestureMic" / "models")
    candidates.append(Path(r"C:\ProgramData") / "GestureMic" / "models")

    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / path.name
            if not target.exists() or target.stat().st_size != path.stat().st_size:
                shutil.copy2(path, target)
            return target
        except OSError:
            continue

    print("[warn] не удалось скопировать модель в ASCII-путь; MediaPipe может её не открыть")
    return path


def open_camera(index: int, width: int, height: int):
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
    capture = cv2.VideoCapture(index, backend)
    if not capture.isOpened():
        capture.release()
        return None
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return capture


def beep_async(muted: bool) -> None:
    def play() -> None:
        try:
            winsound.Beep(440 if muted else 880, 90)
        except Exception:
            pass

    threading.Thread(target=play, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Управление микрофоном жестами руки")
    parser.add_argument("--config", type=Path, default=None, help="путь к config.json")
    parser.add_argument("--camera", type=int, default=None, help="индекс камеры")
    parser.add_argument("--no-window", action="store_true", help="без окна превью")
    parser.add_argument("--duration", type=float, default=0.0, help="остановиться через N секунд (0 = бесконечно)")
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config or (ROOT / "config.json"))

    model_path = Path(config["hand_landmarker"]["model_path"])
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    try:
        ensure_model(model_path)
    except Exception as exc:
        print(f"[error] не удалось получить файл модели: {exc}")
        return 1
    model_path = ascii_model_path(model_path)

    mute_config = config["mute"]
    try:
        backend: Optional[MuteBackend] = create_backend(mute_config["backend"], mute_config["hotkey"])
        state = "MUTED" if backend.muted else "ON"
        print(f"Мут: {backend.name} [{state}]")
        if mute_config["backend"] == "discord_hotkey":
            print(f"Хоткей Discord: {mute_config['hotkey']} (Settings -> Keybinds -> Toggle Mute)")
    except (MuteError, ValueError) as exc:
        backend = None
        print(f"[warn] управление микрофоном отключено: {exc}")

    actions = {name: action for name, action in config["actions"].items() if action in VALID_ACTIONS}
    if not actions:
        print("[warn] в config.json не задано ни одного действия")
    runner = ActionRunner(backend)

    camera = config["camera"]
    camera_index = args.camera if args.camera is not None else int(camera["index"])
    capture = open_camera(camera_index, int(camera["width"]), int(camera["height"]))
    if capture is None:
        print(f"[error] не удалось открыть камеру {camera_index}")
        return 1

    landmarker_config = config["hand_landmarker"]
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=int(landmarker_config["num_hands"]),
        min_hand_detection_confidence=float(landmarker_config["min_detection_confidence"]),
        min_hand_presence_confidence=float(landmarker_config["min_presence_confidence"]),
        min_tracking_confidence=float(landmarker_config["min_tracking_confidence"]),
    )
    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

    stabilizer = GestureStabilizer(config["gesture"]["hold_ms"], config["gesture"]["cooldown_ms"])
    angle_threshold = float(config["gesture"]["extended_angle"])
    show_window = bool(config["feedback"]["show_preview"]) and not args.no_window
    beep = bool(config["feedback"]["beep"])

    print("Камера готова. Q или Esc — выход.")

    started_at = time.monotonic()
    last_timestamp = -1
    action_text = ""
    action_at = 0.0
    fps = 0.0
    fps_at = started_at
    fps_frames = 0
    muted_state = backend.muted if backend else None

    try:
        while True:
            if args.duration > 0 and time.monotonic() - started_at >= args.duration:
                break

            ok, frame = capture.read()
            if not ok:
                print("[error] не удалось прочитать кадр с камеры")
                break

            if camera["mirror"]:
                frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp = int((time.monotonic() - started_at) * 1000)
            if timestamp <= last_timestamp:
                timestamp = last_timestamp + 1
            last_timestamp = timestamp
            result = landmarker.detect_for_video(mp_image, timestamp)

            points = None
            gesture = "none"
            if result.hand_landmarks:
                landmarks = result.hand_landmarks[0]
                points = [(point.x * width, point.y * height, point.z * width) for point in landmarks]
                gesture = classify(points, angle_threshold)

            tracked = gesture if gesture in actions else None
            decision = stabilizer.update(tracked, time.monotonic())

            if decision.fired:
                text, new_state = runner.run(actions[decision.gesture])
                action_text = text
                action_at = time.monotonic()
                if new_state is not None:
                    muted_state = new_state
                    if beep:
                        beep_async(bool(new_state))

            fps_frames += 1
            now = time.monotonic()
            if now - fps_at >= 0.5:
                fps = fps_frames / (now - fps_at)
                fps_frames = 0
                fps_at = now

            if show_window:
                if points is not None:
                    draw_landmarks(frame, points)
                draw_hud(
                    frame,
                    gesture=gesture,
                    progress=decision.progress,
                    muted=muted_state,
                    action_text=action_text if now - action_at < 1.2 else "",
                    fps=fps,
                    backend=backend.name if backend else "media keys only",
                )
                cv2.imshow(WINDOW, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        landmarker.close()
        if show_window:
            cv2.destroyAllWindows()

    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
