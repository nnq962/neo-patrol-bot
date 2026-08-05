"""Phát hiện một bàn tay và chuyển các landmark thành bounding box pixel."""

import time
from pathlib import Path
from types import TracebackType
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from src.tracking.controller import BoundingBox

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"
)


class HandDetector:
    """Bọc MediaPipe Hand Landmarker ở chế độ video cho một bàn tay."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        bbox_padding: float = 0.03,
    ) -> None:
        """Khởi tạo Hand Landmarker từ model cục bộ.

        Args:
            model_path: Đường dẫn tới model ``hand_landmarker.task``.
            min_detection_confidence: Ngưỡng tin cậy tối thiểu khi phát hiện tay.
            min_tracking_confidence: Ngưỡng tin cậy tối thiểu khi tracking landmark.
            bbox_padding: Khoảng đệm bbox theo tỷ lệ kích thước frame.

        Raises:
            FileNotFoundError: Khi model asset chưa tồn tại.
            ValueError: Khi các tham số tỷ lệ nằm ngoài khoảng hợp lệ.
        """
        if not model_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy model MediaPipe: {model_path}")
        if not 0.0 <= min_detection_confidence <= 1.0:
            raise ValueError("min_detection_confidence phải nằm trong [0, 1]")
        if not 0.0 <= min_tracking_confidence <= 1.0:
            raise ValueError("min_tracking_confidence phải nằm trong [0, 1]")
        if not 0.0 <= bbox_padding < 0.5:
            raise ValueError("bbox_padding phải nằm trong [0, 0.5)")

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._bbox_padding = bbox_padding
        self._last_timestamp_ms = -1

    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> BoundingBox | None:
        """Phát hiện bàn tay đầu tiên và trả về bbox theo tọa độ pixel.

        Args:
            frame: Frame BGR ba channel từ OpenCV.

        Returns:
            Bounding box bàn tay hoặc ``None`` khi không phát hiện được tay.

        Raises:
            ValueError: Khi frame không có định dạng BGR hợp lệ.
        """
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("HandDetector yêu cầu frame BGR ba channel")

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        media_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb_frame),
        )
        timestamp_ms = max(time.monotonic_ns() // 1_000_000, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self._landmarker.detect_for_video(media_image, timestamp_ms)

        if not result.hand_landmarks:
            return None

        frame_height, frame_width = frame.shape[:2]
        return self._landmarks_to_bbox(
            landmarks=result.hand_landmarks[0],
            frame_width=frame_width,
            frame_height=frame_height,
            padding=self._bbox_padding,
        )

    # ─────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Giải phóng tài nguyên native của MediaPipe.

        Returns:
            Không trả về giá trị.
        """
        self._landmarker.close()

    # ─────────────────────────────────────────────────────────────────────────

    def __enter__(self) -> "HandDetector":
        """Trả về detector để sử dụng trong context manager.

        Returns:
            Chính detector hiện tại.
        """
        return self

    # ─────────────────────────────────────────────────────────────────────────

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Đóng detector khi thoát context manager.

        Args:
            exc_type: Kiểu exception khiến context kết thúc nếu có.
            exc_value: Exception khiến context kết thúc nếu có.
            traceback: Traceback tương ứng nếu có.

        Returns:
            Không trả về giá trị.
        """
        self.close()

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _landmarks_to_bbox(
        landmarks: list[Any],
        frame_width: int,
        frame_height: int,
        padding: float,
    ) -> BoundingBox:
        """Chuyển danh sách landmark chuẩn hóa thành bbox pixel có padding.

        Args:
            landmarks: Các landmark có thuộc tính ``x`` và ``y`` chuẩn hóa.
            frame_width: Chiều rộng frame theo pixel.
            frame_height: Chiều cao frame theo pixel.
            padding: Khoảng đệm bbox theo tỷ lệ frame.

        Returns:
            Bounding box đã được giới hạn bên trong frame.
        """
        min_x = max(0.0, min(float(point.x) for point in landmarks) - padding)
        min_y = max(0.0, min(float(point.y) for point in landmarks) - padding)
        max_x = min(1.0, max(float(point.x) for point in landmarks) + padding)
        max_y = min(1.0, max(float(point.y) for point in landmarks) + padding)

        return BoundingBox(
            x=min_x * frame_width,
            y=min_y * frame_height,
            width=(max_x - min_x) * frame_width,
            height=(max_y - min_y) * frame_height,
        )
