"""Переключение микрофона по умолчанию Windows на наушники.

Telegram Desktop, Discord и большинство приложений пишут с микрофона по
умолчанию, поэтому отдельная настройка в Telegram не нужна — достаточно
переключить устройство ввода в Windows.

Запуск:
    .venv\\Scripts\\python tools\\use_headset_mic.py
    .venv\\Scripts\\python tools\\use_headset_mic.py --list
"""
from __future__ import annotations

import argparse
import sys

from pycaw.constants import EDataFlow, ERole
from pycaw.pycaw import AudioUtilities

ROLES = (ERole.eConsole, ERole.eMultimedia, ERole.eCommunications)

HEADSET_HINTS = (
    "hands-free",
    "headset",
    "headphone",
    "головной телефон",
    "наушник",
    "гарнитур",
    "airdots",
    "freebuds",
    "redmi",
    "huawei",
)


def active_capture_devices() -> list:
    return [
        device
        for device in AudioUtilities.GetAllDevices(data_flow=EDataFlow.eCapture.value)
        if device.state.name == "Active"
    ]


def current_default_id() -> str:
    enum = AudioUtilities.GetDeviceEnumerator()
    device = enum.GetDefaultAudioEndpoint(EDataFlow.eCapture.value, ERole.eMultimedia.value)
    return device.GetId()


def is_headset(device) -> bool:
    name = device.FriendlyName.lower()
    return any(hint in name for hint in HEADSET_HINTS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Сделать микрофон наушников устройством ввода по умолчанию")
    parser.add_argument("--list", action="store_true", help="показать активные микрофоны и выйти")
    parser.add_argument("--name", default=None, help="часть имени устройства вместо автоопределения")
    args = parser.parse_args()

    devices = active_capture_devices()
    if args.list:
        default_id = current_default_id()
        print("Активные микрофоны:")
        for device in devices:
            mark = "  <== по умолчанию" if device.id == default_id else ""
            print(f"  - {device.FriendlyName}{mark}")
        return 0

    if args.name:
        matches = [device for device in devices if args.name.lower() in device.FriendlyName.lower()]
    else:
        matches = [device for device in devices if is_headset(device)]

    if not matches:
        print("Наушники с микрофоном не найдены.")
        print("Подключите их в Windows (Настройки → Bluetooth и устройства) и запустите снова.")
        print("Сейчас активны:")
        for device in devices:
            print(f"  - {device.FriendlyName}")
        return 1

    target = matches[0]
    AudioUtilities.SetDefaultDevice(target.id, roles=ROLES)
    print(f"Микрофон по умолчанию: {target.FriendlyName}")
    print("Telegram подхватит смену сам; если нет — перезапустите его.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
