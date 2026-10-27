"""Gesture Mic: управление микрофоном жестами руки.

Запуск:  python src/main.py  (или run.bat)
Выход:   Q / Esc в окне превью, либо Ctrl+C в консоли.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import threading
import time
import urllib.request
import winsound
from pathlib import Path

import cv2
import mediapipe as mp

from config import load_config
from gestures import classify, hand_in_frame
from mic import MicController, MicError
from overlay import draw_hud, draw_landmarks
from stabilizer import GestureStabilizer

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
WINDOW = "Gesture Mic"
VALID_ACTIONS = ("mute", "unmute", "toggle")


def ensure_model(path: Path) -> None:
    """Скачивает модель, если её нет рядом с проектом."""
    if path.exists() and path.stat().st_size > 1_000_000:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading hand landmark model -> {path}")
    urllib.request.urlretrieve(MODEL_URL, path)


def ascii_model_path(path: Path) -> Path:
    """MediaPipe не открывает пути с кириллицей на Windows.

    Если путь содержит не-ASCII символы, копируем модель в ASCII-каталог
    и возвращаем путь к копии.
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
    parser.add_argument("--unmute", action="store_true", help="включить микрофон и выйти")
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parent.parent
    config_path = args.config or (root / "config.json")
    config = load_config(config_path)

    model_path = Path(config["hand_landmarker"]["model_path"])
    if not model_path.is_absolute():
        model_path = root / model_path
    try:
        ensure_model(model_path)
    except Exception as exc:
        print(f"[error] не удалось получить файл модели: {exc}")
        return 1
    model_path = ascii_model_path(model_path)

    try:
        mic = MicController()
        mic_available = True
    except MicError as exc:
        mic = None
        mic_available = False
        print(f"[warn] управление микрофоном отключено: {exc}")

    actions = {name: action for name, action in config["actions"].items() if action in VALID_ACTIONS}
    if not actions:
        print("[warn] в config.json не задано ни одного действия")

    safety = config["safety"]
    skip_mute_while_recording = bool(safety["skip_mute_while_recording"])
    restore_mic_on_exit = bool(safety["restore_mic_on_exit"])

    camera_config = config["camera"]
    camera_index = args.camera if args.camera is not None else int(camera_config["index"])
    capture = open_camera(camera_index, int(camera_config["width"]), int(camera_config["height"]))
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

    stabilizer = GestureStabilizer(
        config["gesture"]["hold_ms"],
        config["gesture"]["cooldown_ms"],
    )
    angle_threshold = float(config["gesture"]["extended_angle"])
    curled_threshold = float(config["gesture"]["curled_angle"])

    show_window = bool(config["feedback"]["show_preview"]) and not args.no_window
    beep = bool(config["feedback"]["beep"])

    if mic_available:
        initial_muted = mic.is_muted()
        state = "MUTED" if initial_muted else "ON"
        print(f"Микрофон: {mic.name} [{state}]")
        if initial_muted:
            print("Микрофон сейчас выключен. Включить: src\\main.py --unmute")
    else:
        initial_muted = None
    print("Камера готова. Q или Esc — выход.")

    started_at = time.monotonic()
    last_timestamp = -1
    action_text = ""
    action_at = 0.0
    fps = 0.0
    fps_at = started_at
    fps_frames = 0
    muted_state = mic.is_muted() if mic_available else None
    state_at = started_at

    try:
        while True:
            if args.duration > 0 and time.monotonic() - started_at >= args.duration:
                break

            ok, frame = capture.read()
            if not ok:
                print("[error] не удалось прочитать кадр с камеры")
                break

            if camera_config["mirror"]:
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
                if hand_in_frame(points, width, height):
                    gesture = classify(points, angle_threshold, curled_threshold)
                else:
                    gesture = "unknown"

            tracked = gesture if gesture in actions else None
            decision = stabilizer.update(tracked, time.monotonic())

            if decision.fired and mic_available:
                action = actions[decision.gesture]
                will_mute = action == "mute" or (action == "toggle" and not mic.is_muted())
                if will_mute and skip_mute_while_recording and mic.in_use_by_other_app():
                    action_text = "RECORDING - mute skipped"
                    action_at = time.monotonic()
                    print("[info] другое приложение пишет с микрофона — выключение пропущено")
                else:
                    if action == "mute":
                        mic.set_muted(True)
                    elif action == "unmute":
                        mic.set_muted(False)
                    else:
                        mic.toggle()
                    muted_state = mic.is_muted()
                    action_text = f"{action.upper()} -> {'MUTED' if muted_state else 'ON'}"
                    action_at = time.monotonic()
                    if beep:
                        beep_async(muted_state)

            fps_frames += 1
            now = time.monotonic()
            if now - fps_at >= 0.5:
                fps = fps_frames / (now - fps_at)
                fps_frames = 0
                fps_at = now
            if mic_available and now - state_at >= 0.5:
                muted_state = mic.is_muted()
                state_at = now

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
                    mic_available=mic_available,
                )
                cv2.imshow(WINDOW, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if mic_available and restore_mic_on_exit and initial_muted is not None:
            try:
                if mic.is_muted() != initial_muted:
                    mic.set_muted(initial_muted)
                    print(f"Микрофон возвращён в исходное состояние: {'MUTED' if initial_muted else 'ON'}")
            except Exception as exc:
                print(f"[warn] не удалось вернуть состояние микрофона: {exc}")
        capture.release()
        landmarker.close()
        if show_window:
            cv2.destroyAllWindows()

    return 0


def main() -> int:
    args = parse_args()
    if args.unmute:
        try:
            mic = MicController()
        except MicError as exc:
            print(f"[error] {exc}")
            return 1
        mic.set_muted(False)
        print(f"Микрофон включён: {mic.name}")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
