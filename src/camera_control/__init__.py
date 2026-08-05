"""Cung cấp API kết nối và điều khiển camera ONVIF."""

from src.camera_control.camera import OnvifCamera
from src.camera_control.config import CameraConfig
from src.camera_control.exceptions import (
    CameraConfigError,
    CameraConnectionError,
    CameraControlError,
)
from src.camera_control.models import CameraDeviceInfo, PtzStatus
from src.camera_control.ptz_controller import OnvifPtzController

__all__ = [
    "CameraConfig",
    "CameraConfigError",
    "CameraConnectionError",
    "CameraControlError",
    "CameraDeviceInfo",
    "OnvifCamera",
    "OnvifPtzController",
    "PtzStatus",
]
