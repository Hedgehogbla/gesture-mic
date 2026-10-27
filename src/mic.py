"""Управление системным микрофоном через Windows Core Audio (pycaw)."""
from __future__ import annotations

import os


class MicError(RuntimeError):
    """Не удалось получить доступ к микрофону."""


def _raw_device(device):
    """pycaw в разных версиях возвращает либо IMMDevice, либо AudioDevice."""
    return getattr(device, "_dev", device)


class MicController:
    def __init__(self) -> None:
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise MicError(f"pycaw/comtypes недоступны: {exc}") from exc

        try:
            device = AudioUtilities.GetMicrophone()
            if device is None:
                raise MicError("микрофон по умолчанию не найден")
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._volume = interface.QueryInterface(IAudioEndpointVolume)
        except MicError:
            raise
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise MicError(f"нет доступа к микрофону: {exc}") from exc

        self._device = device

    @property
    def name(self) -> str:
        try:
            from pycaw.pycaw import AudioUtilities

            friendly = AudioUtilities.CreateDevice(_raw_device(self._device)).FriendlyName
            return friendly or "микрофон по умолчанию"
        except Exception:
            return "микрофон по умолчанию"

    def is_muted(self) -> bool:
        return bool(self._volume.GetMute())

    def set_muted(self, muted: bool) -> None:
        self._volume.SetMute(1 if muted else 0, None)

    def toggle(self) -> bool:
        """Переключает mute и возвращает новое состояние."""
        muted = not self.is_muted()
        self.set_muted(muted)
        return muted

    def in_use_by_other_app(self) -> bool:
        """True, если другое приложение прямо сейчас пишет с этого микрофона.

        Проверяются аудиосессии устройства захвата: активная сессия с чужим
        PID означает идущую запись (звонок, голосовое, диктофон).
        """
        try:
            from pycaw.constants import AudioSessionState, EDataFlow
            from pycaw.pycaw import AudioUtilities
        except Exception:
            return False

        try:
            device_id = _raw_device(self._device).GetId()
            own_pid = os.getpid()
            for device in AudioUtilities.GetAllDevices(data_flow=EDataFlow.eCapture.value):
                if device.id != device_id:
                    continue
                sessions = device.AudioSessionManager.GetSessionEnumerator()
                for index in range(sessions.GetCount()):
                    control = sessions.GetSession(index)
                    if control is None:
                        continue
                    if control.GetProcessId() in (0, own_pid):
                        continue
                    if control.GetState() == AudioSessionState.Active:
                        return True
                return False
        except Exception:
            return False

        return False
