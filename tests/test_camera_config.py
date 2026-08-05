"""Kiểm thử cấu hình media của camera."""

import unittest

from src.camera_control.config import CameraConfig
from src.media_sources.utils import redact_url_credentials


class CameraConfigTestCase(unittest.TestCase):
    """Kiểm tra URL RTSP và cơ chế che credential."""

    def test_rtsp_url_encodes_credentials_and_normalizes_path(self) -> None:
        """Xác nhận credential đặc biệt được mã hóa trong RTSP URL."""
        config = CameraConfig(
            host="192.0.2.1",
            username="admin@example.com",
            password="p@ss/word",
            rtsp_path="11",
        )

        self.assertEqual(
            config.rtsp_url,
            "rtsp://admin%40example.com:p%40ss%2Fword@192.0.2.1:554/11",
        )

    # ─────────────────────────────────────────────────────────────────────────

    def test_redact_url_credentials_hides_secret(self) -> None:
        """Xác nhận log URL không chứa username hoặc password thật."""
        safe_url = redact_url_credentials(
            "rtsp://admin:secret@192.0.2.1:554/11"
        )

        self.assertEqual(safe_url, "rtsp://***:***@192.0.2.1:554/11")


if __name__ == "__main__":
    unittest.main()
