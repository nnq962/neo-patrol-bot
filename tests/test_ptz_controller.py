"""Kiểm thử lệnh Pan/Tilt ONVIF mà không di chuyển camera thật."""

import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.camera_control.exceptions import CameraControlError
from src.camera_control.ptz_controller import OnvifPtzController


class OnvifPtzControllerTestCase(unittest.TestCase):
    """Kiểm tra request ONVIF do bộ điều khiển PTZ tạo ra."""

    def setUp(self) -> None:
        """Tạo ONVIF client giả lập có một media profile PTZ."""
        self.client = MagicMock()
        profile = SimpleNamespace(
            token="profile0_0",
            PTZConfiguration=SimpleNamespace(token="Anv_ptz_0"),
        )
        self.client.media.return_value.GetProfiles.return_value = [profile]
        self.controller = OnvifPtzController(self.client)

    # ─────────────────────────────────────────────────────────────────────────

    def test_move_sends_only_pan_tilt_velocity(self) -> None:
        """Xác nhận ContinuousMove không chứa thành phần Zoom."""
        self.controller.move_continuous(pan_velocity=0.3, tilt_velocity=-0.2)

        self.client.ptz.return_value.ContinuousMove.assert_called_once_with(
            ProfileToken="profile0_0",
            Velocity={"PanTilt": {"x": 0.3, "y": -0.2}},
            Timeout=timedelta(seconds=1),
        )

    # ─────────────────────────────────────────────────────────────────────────

    def test_zero_velocity_uses_stop(self) -> None:
        """Xác nhận command đứng yên gọi Stop thay vì ContinuousMove."""
        self.controller.move_continuous(pan_velocity=0.0, tilt_velocity=0.0)

        self.client.ptz.return_value.Stop.assert_called_once_with(
            ProfileToken="profile0_0",
            PanTilt=True,
            Zoom=False,
        )
        self.client.ptz.return_value.ContinuousMove.assert_not_called()

    # ─────────────────────────────────────────────────────────────────────────

    def test_velocity_outside_supported_range_is_rejected(self) -> None:
        """Xác nhận vận tốc ngoài ``[-1, 1]`` không được gửi tới camera."""
        with self.assertRaises(ValueError):
            self.controller.move_continuous(
                pan_velocity=1.1,
                tilt_velocity=0.0,
            )

        self.client.ptz.return_value.ContinuousMove.assert_not_called()

    # ─────────────────────────────────────────────────────────────────────────

    def test_get_position_maps_pan_and_tilt(self) -> None:
        """Xác nhận PTZ status được chuyển thành model vị trí nội bộ."""
        status = SimpleNamespace(
            Position=SimpleNamespace(
                PanTilt=SimpleNamespace(x=-0.25, y=0.4),
            )
        )
        self.client.ptz.return_value.GetStatus.return_value = status

        position = self.controller.get_position()

        self.assertEqual(position.pan, -0.25)
        self.assertEqual(position.tilt, 0.4)
        self.client.ptz.return_value.GetStatus.assert_called_once_with(
            ProfileToken="profile0_0"
        )

    # ─────────────────────────────────────────────────────────────────────────

    def test_missing_ptz_profile_is_reported(self) -> None:
        """Xác nhận camera không có PTZ profile trả về lỗi miền rõ ràng."""
        self.client.media.return_value.GetProfiles.return_value = []

        with self.assertRaises(CameraControlError):
            self.controller.move_continuous(
                pan_velocity=0.2,
                tilt_velocity=0.0,
            )


if __name__ == "__main__":
    unittest.main()
