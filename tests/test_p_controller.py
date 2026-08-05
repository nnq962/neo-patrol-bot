"""Kiểm thử phép ánh xạ bbox sang vận tốc Pan/Tilt."""

import unittest

from src.tracking import BoundingBox, PControllerConfig, PTrackingController


class PTrackingControllerTestCase(unittest.TestCase):
    """Kiểm tra dấu, dead zone và giới hạn của bộ điều khiển P."""

    def test_centered_bbox_stops_camera(self) -> None:
        """Xác nhận bbox ở tâm tạo command đứng yên."""
        controller = PTrackingController()
        bbox = BoundingBox(x=270.0, y=190.0, width=100.0, height=100.0)

        command = controller.calculate_command(bbox, 640, 480)

        self.assertEqual(command.pan_velocity, 0.0)
        self.assertEqual(command.tilt_velocity, 0.0)
        self.assertFalse(command.should_move)

    # ─────────────────────────────────────────────────────────────────────────

    def test_bbox_right_and_below_moves_right_and_down(self) -> None:
        """Xác nhận hướng command đúng khi bbox ở dưới bên phải."""
        controller = PTrackingController(
            PControllerConfig(
                pan_gain=1.0,
                tilt_gain=1.0,
                pan_dead_zone=0.0,
                tilt_dead_zone=0.0,
                max_pan_velocity=1.0,
                max_tilt_velocity=1.0,
            )
        )
        bbox = BoundingBox(x=430.0, y=310.0, width=100.0, height=100.0)

        command = controller.calculate_command(bbox, 640, 480)

        self.assertEqual(command.pan_velocity, 0.5)
        self.assertEqual(command.tilt_velocity, -0.5)

    # ─────────────────────────────────────────────────────────────────────────

    def test_output_is_limited_by_maximum_velocity(self) -> None:
        """Xác nhận command không vượt giới hạn vận tốc cấu hình."""
        controller = PTrackingController(
            PControllerConfig(
                pan_gain=2.0,
                tilt_gain=2.0,
                max_pan_velocity=0.3,
                max_tilt_velocity=0.2,
            )
        )
        bbox = BoundingBox(x=0.0, y=0.0, width=10.0, height=10.0)

        command = controller.calculate_command(bbox, 640, 480)

        self.assertEqual(command.pan_velocity, -0.3)
        self.assertEqual(command.tilt_velocity, 0.2)

    # ─────────────────────────────────────────────────────────────────────────

    def test_bbox_inside_dead_zone_stops_camera(self) -> None:
        """Xác nhận sai số nhỏ hơn dead zone không tạo chuyển động."""
        controller = PTrackingController(
            PControllerConfig(
                pan_dead_zone=0.1,
                tilt_dead_zone=0.1,
            )
        )
        bbox = BoundingBox(x=290.0, y=210.0, width=100.0, height=100.0)

        command = controller.calculate_command(bbox, 640, 480)

        self.assertFalse(command.should_move)

    # ─────────────────────────────────────────────────────────────────────────

    def test_invalid_frame_size_is_rejected(self) -> None:
        """Xác nhận kích thước frame không hợp lệ bị từ chối."""
        controller = PTrackingController()
        bbox = BoundingBox(x=0.0, y=0.0, width=10.0, height=10.0)

        with self.assertRaises(ValueError):
            controller.calculate_command(bbox, 0, 480)


if __name__ == "__main__":
    unittest.main()
