"""Khai báo các model dữ liệu độc lập với thư viện ONVIF."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraDeviceInfo:
    """Mô tả thông tin nhận dạng cơ bản do camera ONVIF trả về."""

    manufacturer    : str
    model           : str
    firmware_version: str
    serial_number   : str
    hardware_id     : str


@dataclass(frozen=True, slots=True)
class PtzStatus:
    """Mô tả chi tiết trạng thái PTZ hiện tại do camera ONVIF trả về."""

    pan               : float
    tilt              : float
    zoom              : float
    is_pan_tilt_moving: bool = False
    is_zoom_moving    : bool = False
