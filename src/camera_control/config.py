"""Đọc và kiểm tra cấu hình kết nối camera từ biến môi trường."""

import os
from dataclasses import dataclass
from urllib.parse import quote

from dotenv import load_dotenv

from src.camera_control.exceptions import CameraConfigError


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Lưu cấu hình cần thiết để kết nối tới ONVIF Device Service."""

    host: str
    username: str
    password: str
    onvif_port: int = 80
    timeout_seconds: int = 10
    rtsp_port: int = 554
    rtsp_path: str = "/11"

    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "CameraConfig":
        """Đọc cấu hình camera từ file môi trường và trả về cấu hình hợp lệ.

        Args:
            env_file: Đường dẫn tới file chứa các biến môi trường.

        Returns:
            Cấu hình camera đã được kiểm tra.

        Raises:
            CameraConfigError: Khi thiếu biến bắt buộc hoặc giá trị số không hợp lệ.
        """
        load_dotenv(dotenv_path=env_file)

        host = cls._required_env("CAMERA_HOST")
        username = cls._required_env("CAMERA_USERNAME")
        password = cls._required_env("CAMERA_PASSWORD")
        onvif_port = cls._integer_env("CAMERA_ONVIF_PORT", default=80)
        timeout_seconds = cls._integer_env("CAMERA_ONVIF_TIMEOUT", default=10)
        rtsp_port = cls._integer_env("CAMERA_RTSP_PORT", default=554)
        rtsp_path = os.getenv("CAMERA_RTSP_PATH", "/11").strip()

        if not 1 <= onvif_port <= 65535:
            raise CameraConfigError("CAMERA_ONVIF_PORT phải nằm trong khoảng 1-65535")
        if timeout_seconds <= 0:
            raise CameraConfigError("CAMERA_ONVIF_TIMEOUT phải lớn hơn 0")
        if not 1 <= rtsp_port <= 65535:
            raise CameraConfigError("CAMERA_RTSP_PORT phải nằm trong khoảng 1-65535")
        if not rtsp_path:
            raise CameraConfigError("CAMERA_RTSP_PATH không được để trống")

        return cls(
            host=host,
            username=username,
            password=password,
            onvif_port=onvif_port,
            timeout_seconds=timeout_seconds,
            rtsp_port=rtsp_port,
            rtsp_path=rtsp_path,
        )

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def rtsp_url(self) -> str:
        """Tạo RTSP URL và mã hóa credential để đọc frame từ camera.

        Returns:
            RTSP URL hoàn chỉnh có host, port, credential và stream path.
        """
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        path = self.rtsp_path if self.rtsp_path.startswith("/") else f"/{self.rtsp_path}"
        return (
            f"rtsp://{username}:{password}@{self.host}:{self.rtsp_port}{path}"
        )

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _required_env(name: str) -> str:
        """Lấy một biến môi trường bắt buộc và loại bỏ khoảng trắng.

        Args:
            name: Tên biến môi trường cần đọc.

        Returns:
            Giá trị biến môi trường không rỗng.

        Raises:
            CameraConfigError: Khi biến chưa được khai báo hoặc để trống.
        """
        value = os.getenv(name, "").strip()
        if not value or value == "change-me":
            raise CameraConfigError(f"Thiếu cấu hình bắt buộc: {name}")
        return value

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _integer_env(name: str, default: int) -> int:
        """Đọc một biến môi trường kiểu số nguyên.

        Args:
            name: Tên biến môi trường cần đọc.
            default: Giá trị dùng khi biến chưa được khai báo.

        Returns:
            Giá trị số nguyên đã đọc.

        Raises:
            CameraConfigError: Khi giá trị không thể chuyển thành số nguyên.
        """
        raw_value = os.getenv(name, str(default)).strip()
        try:
            return int(raw_value)
        except ValueError as exc:
            raise CameraConfigError(f"{name} phải là một số nguyên") from exc
