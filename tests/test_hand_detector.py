"""Kiểm thử chuyển landmark bàn tay thành bounding box pixel."""

import unittest
from types import SimpleNamespace

from src.tracking import HandDetector


class HandDetectorTestCase(unittest.TestCase):
    """Kiểm tra phép chiếu landmark chuẩn hóa sang frame."""

    def test_landmarks_are_converted_to_padded_bbox(self) -> None:
        """Xác nhận bbox được thêm padding và đổi đúng sang pixel."""
        landmarks = [
            SimpleNamespace(x=0.2, y=0.3),
            SimpleNamespace(x=0.6, y=0.8),
        ]

        bbox = HandDetector._landmarks_to_bbox(
            landmarks=landmarks,
            frame_width=1000,
            frame_height=500,
            padding=0.05,
        )

        self.assertAlmostEqual(bbox.x, 150.0)
        self.assertAlmostEqual(bbox.y, 125.0)
        self.assertAlmostEqual(bbox.width, 500.0)
        self.assertAlmostEqual(bbox.height, 300.0)


if __name__ == "__main__":
    unittest.main()
