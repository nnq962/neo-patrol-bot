"""Phát hiện khuôn mặt bằng YOLOv12s-face từ ultralytics."""

from pathlib import Path
from types import TracebackType

import cv2
import numpy as np
from ultralytics import YOLO

from src.tracking.controller import BoundingBox
from utils import LOGGER

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[2] / "models" / "yolov12s-face.pt"
)


class FaceDetector:
    """Bọc YOLO model từ ultralytics để phát hiện khuôn mặt."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        conf_threshold: float = 0.5,
    ) -> None:
        """Khởi tạo FaceDetector với model YOLO.

        Args:
            model_path: Đường dẫn tới file weight YOLO (ví dụ yolov12s-face.pt).
            conf_threshold: Ngưỡng độ tin cậy tối thiểu khi phát hiện mặt.

        Raises:
            FileNotFoundError: Khi không tìm thấy file weight model.
            ValueError: Khi conf_threshold nằm ngoài khoảng [0, 1].
        """
        if not model_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy model YOLO: {model_path}")
        if not 0.0 <= conf_threshold <= 1.0:
            raise ValueError("conf_threshold phải nằm trong [0, 1]")

        self._model_path = model_path
        self._conf_threshold = conf_threshold
        LOGGER.info("Đang tải model YOLO phát hiện khuôn mặt từ %s...", model_path)
        self._model = YOLO(str(model_path))

    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> BoundingBox | None:
        """Phát hiện khuôn mặt có độ tin cậy lớn nhất trong frame.

        Args:
            frame: Frame BGR ba channel từ OpenCV.

        Returns:
            Bounding box khuôn mặt hoặc ``None`` khi không phát hiện được mặt nào.

        Raises:
            ValueError: Khi frame không có định dạng BGR hợp lệ.
        """
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("FaceDetector yêu cầu frame BGR ba channel")

        results = self._model(frame, conf=self._conf_threshold, verbose=False)
        if not results or len(results[0].boxes) == 0:
            return None

        boxes = results[0].boxes
        best_box = boxes[0]
        x1, y1, x2, y2 = best_box.xyxy[0].tolist()

        return BoundingBox(
            x=float(x1),
            y=float(y1),
            width=float(x2 - x1),
            height=float(y2 - y1),
        )

    # ─────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Giải phóng tài nguyên nếu cần.

        Returns:
            Không trả về giá trị.
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────

    def __enter__(self) -> "FaceDetector":
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
