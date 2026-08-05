"""Định nghĩa các lỗi thuộc miền camera để che giấu lỗi thư viện bên dưới."""


class CameraError(Exception):
    """Lỗi cơ sở cho mọi thao tác camera."""


class CameraConfigError(CameraError):
    """Lỗi khi cấu hình camera bị thiếu hoặc không hợp lệ."""


class CameraConnectionError(CameraError):
    """Lỗi khi không thể giao tiếp với ONVIF Device Service."""


class CameraControlError(CameraError):
    """Lỗi khi camera không thể thực hiện một lệnh điều khiển PTZ."""
