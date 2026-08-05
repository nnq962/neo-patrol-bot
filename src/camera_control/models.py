"""Khai báo các model dữ liệu độc lập với thư viện ONVIF."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraDeviceInfo:
    """Mô tả thông tin nhận dạng cơ bản do camera ONVIF trả về."""

    manufacturer: str
    model: str
    firmware_version: str
    serial_number: str
    hardware_id: str


@dataclass(frozen=True, slots=True)
class PtzPosition:
    """Mô tả vị trí Pan/Tilt hiện tại do camera ONVIF trả về."""

    pan: float
    tilt: float
