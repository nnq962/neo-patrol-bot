"""Kiểm thử trạng thái kết nối ONVIF mà không cần camera thật."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.camera_control.camera import OnvifCamera
from src.camera_control.config import CameraConfig
from src.camera_control.exceptions import CameraConnectionError


class OnvifCameraTestCase(unittest.TestCase):
    """Kiểm tra facade camera với ONVIF client giả lập."""

    def setUp(self) -> None:
        """Tạo cấu hình camera dùng chung trước mỗi kiểm thử."""
        self.config = CameraConfig(
            host="192.0.2.1",
            username="admin",
            password="secret",
        )

    # ─────────────────────────────────────────────────────────────────────────

    @patch("src.camera_control.camera.ONVIFClient")
    def test_connect_maps_device_info(self, client_class: MagicMock) -> None:
        """Xác nhận response ONVIF được chuyển thành model nội bộ."""
        response = SimpleNamespace(
            Manufacturer="Neo",
            Model="PTZ-01",
            FirmwareVersion="1.0",
            SerialNumber="123",
            HardwareId="A1",
        )
        client_class.return_value.devicemgmt.return_value.GetDeviceInformation.return_value = (
            response
        )
        camera = OnvifCamera(self.config)

        with patch("src.camera_control.camera.socket.create_connection"):
            device_info = camera.connect()

        self.assertTrue(camera.is_connected)
        self.assertEqual(device_info.manufacturer, "Neo")
        self.assertEqual(camera.device_info.model, "PTZ-01")

    # ─────────────────────────────────────────────────────────────────────────

    @patch("src.camera_control.camera.ONVIFClient")
    def test_connect_clears_state_when_request_fails(
        self,
        client_class: MagicMock,
    ) -> None:
        """Xác nhận lỗi ONVIF được chuyển đổi và không giữ client hỏng."""
        client_class.side_effect = TimeoutError("hết thời gian")
        camera = OnvifCamera(self.config)

        with patch("src.camera_control.camera.socket.create_connection"):
            with self.assertRaises(CameraConnectionError):
                camera.connect()

        self.assertFalse(camera.is_connected)

    # ─────────────────────────────────────────────────────────────────────────

    def test_connect_reports_tcp_timeout(self) -> None:
        """Xác nhận timeout TCP trả về hướng dẫn kiểm tra mạng rõ ràng."""
        camera = OnvifCamera(self.config)

        with patch(
            "src.camera_control.camera.socket.create_connection",
            side_effect=TimeoutError("hết thời gian"),
        ):
            with self.assertRaisesRegex(
                CameraConnectionError,
                "hãy kiểm tra camera đang bật",
            ):
                camera.connect()

        self.assertFalse(camera.is_connected)


if __name__ == "__main__":
    unittest.main()
