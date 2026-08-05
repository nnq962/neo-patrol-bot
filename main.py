"""Chạy thử nghiệm camera PTZ bám theo bounding box khuôn mặt."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.camera_control import (
    CameraConfig,
    CameraConfigError,
    CameraConnectionError,
    CameraControlError,
    OnvifCamera,
)
from src.media_sources import MediaSourceError, MediaSources
from src.tracking import (
    BoundingBox,
    FaceDetector,
    PControllerConfig,
    PTrackingController,
    PanTiltCommand,
)
from utils import LOGGER

WINDOW_NAME = "Neo Patrol Bot - Face Tracking"
CONTROL_INTERVAL_SECONDS = 0.10
TARGET_LOST_TIMEOUT_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class PTZWorkerConfig:
    """Cấu hình luồng gửi lệnh PTZ."""

    minimum_send_interval_seconds: float = 0.12
    command_change_threshold: float = 0.02
    refresh_interval_seconds: float = 0.50


class PTZCommandWorker:
    """Gửi lệnh PTZ ở thread riêng và chỉ xử lý command mới nhất."""

    def __init__(
        self,
        camera: OnvifCamera,
        config: PTZWorkerConfig | None = None,
    ) -> None:
        self._ptz = camera.ptz
        self._config = config or PTZWorkerConfig()
        self._condition = threading.Condition()
        self._latest_command: PanTiltCommand | None = None
        self._command_version = 0
        self._running = False
        self._thread: threading.Thread | None = None

    # ─────────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Khởi động worker nếu chưa chạy."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="ptz-command-worker",
            daemon=True,
        )
        self._thread.start()

    # ─────────────────────────────────────────────────────────────────────────

    def submit(self, command: PanTiltCommand | None) -> None:
        """Cập nhật command mới nhất mà không chặn main thread."""
        with self._condition:
            self._latest_command = command
            self._command_version += 1
            self._condition.notify()

    # ─────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Dừng worker và gửi Stop cuối cùng tới camera."""
        with self._condition:
            self._running = False
            self._condition.notify_all()

        if self._thread is not None:
            self._thread.join(timeout=2.0)

        try:
            self._ptz.stop()
        except CameraControlError as exc:
            LOGGER.error("Không thể dừng camera khi đóng PTZ worker: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        """Vòng lặp gửi lệnh ONVIF trong worker thread."""
        processed_version = -1
        last_sent_command: PanTiltCommand | None = None
        last_send_time = 0.0
        motion_active = False

        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: (
                        not self._running
                        or self._command_version != processed_version
                    ),
                    timeout=self._config.refresh_interval_seconds,
                )

                if not self._running:
                    break

                command = self._latest_command
                processed_version = self._command_version

            elapsed = time.monotonic() - last_send_time
            remaining = self._config.minimum_send_interval_seconds - elapsed
            if remaining > 0.0:
                time.sleep(remaining)

            if command is None or not command.should_move:
                if motion_active:
                    try:
                        self._ptz.stop()
                        motion_active = False
                        last_sent_command = None
                        last_send_time = time.monotonic()
                    except CameraControlError as exc:
                        LOGGER.error("Gửi lệnh PTZ Stop thất bại: %s", exc)
                continue

            elapsed = time.monotonic() - last_send_time
            if not self._should_send(command, last_sent_command, elapsed):
                continue

            try:
                self._ptz.move_continuous(
                    pan_velocity=command.pan_velocity,
                    tilt_velocity=command.tilt_velocity,
                )
                motion_active = True
                last_sent_command = command
                last_send_time = time.monotonic()
            except CameraControlError as exc:
                LOGGER.error("Gửi lệnh PTZ ContinuousMove thất bại: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────

    def _should_send(
        self,
        command: PanTiltCommand,
        previous: PanTiltCommand | None,
        elapsed_seconds: float,
    ) -> bool:
        """Kiểm tra command có đủ khác để cần gửi lại hay không."""
        if previous is None:
            return True

        pan_changed = (
            abs(command.pan_velocity - previous.pan_velocity)
            >= self._config.command_change_threshold
        )
        tilt_changed = (
            abs(command.tilt_velocity - previous.tilt_velocity)
            >= self._config.command_change_threshold
        )
        refresh_due = elapsed_seconds >= self._config.refresh_interval_seconds

        return pan_changed or tilt_changed or refresh_due


# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Kết nối camera và chạy vòng lặp phát hiện, bám theo khuôn mặt."""
    try:
        config = CameraConfig.from_env()
        camera = _connect_camera(config)
        _run_face_tracking(camera, config)
    except KeyboardInterrupt:
        LOGGER.info("Đã dừng face tracking bằng bàn phím")
        return 0
    except (
        CameraConfigError,
        CameraConnectionError,
        CameraControlError,
        MediaSourceError,
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        LOGGER.error("Face tracking thất bại: %s", exc)
        return 1

    return 0


# ─────────────────────────────────────────────────────────────────────────────


def _connect_camera(config: CameraConfig) -> OnvifCamera:
    """Kết nối ONVIF và ghi thông tin nhận dạng camera."""
    LOGGER.info("Đang kết nối ONVIF tới %s:%d", config.host, config.onvif_port)
    camera = OnvifCamera(config)
    device_info = camera.connect()
    LOGGER.info(
        "Đã kết nối camera | hãng=%s | model=%s | firmware=%s",
        device_info.manufacturer or "không rõ",
        device_info.model or "không rõ",
        device_info.firmware_version or "không rõ",
    )
    return camera


# ─────────────────────────────────────────────────────────────────────────────


def _run_face_tracking(camera: OnvifCamera, config: CameraConfig) -> None:
    """Đọc RTSP, phát hiện khuôn mặt và cập nhật command cho PTZ worker."""
    controller_config = PControllerConfig()
    controller = PTrackingController(controller_config)
    ptz_worker = PTZCommandWorker(camera)
    ptz_worker.start()

    face_was_detected = False
    stop_command_submitted = False
    last_control_time = 0.0
    last_detection_time: float | None = None

    LOGGER.info("Bắt đầu face tracking; nhấn Q hoặc ESC để dừng")

    try:
        with FaceDetector() as detector, MediaSources(config.rtsp_url) as media:
            for frames, _ in media:
                frame = frames[0]
                bbox = detector.detect(frame)
                command = _calculate_command(controller, bbox, frame)
                now = time.monotonic()

                if bbox is not None:
                    last_detection_time = now
                    stop_command_submitted = False

                    if not face_was_detected:
                        LOGGER.info("Đã phát hiện khuôn mặt")
                    face_was_detected = True

                    if now - last_control_time >= CONTROL_INTERVAL_SECONDS:
                        ptz_worker.submit(command)
                        last_control_time = now
                else:
                    target_is_lost = (
                        last_detection_time is None
                        or now - last_detection_time >= TARGET_LOST_TIMEOUT_SECONDS
                    )

                    if target_is_lost:
                        if face_was_detected:
                            LOGGER.info("Mất dấu khuôn mặt; dừng Pan/Tilt")
                        face_was_detected = False

                        if not stop_command_submitted:
                            ptz_worker.submit(None)
                            stop_command_submitted = True

                _draw_overlay(frame, bbox, command, controller_config)
                cv2.imshow(WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    LOGGER.info("Nhận yêu cầu dừng từ cửa sổ preview")
                    break
    finally:
        ptz_worker.close()
        cv2.destroyAllWindows()


# ─────────────────────────────────────────────────────────────────────────────


def _calculate_command(
    controller: PTrackingController,
    bbox: BoundingBox | None,
    frame: np.ndarray,
) -> PanTiltCommand | None:
    """Tính command P từ bbox nếu phát hiện được khuôn mặt."""
    if bbox is None:
        return None

    frame_height, frame_width = frame.shape[:2]
    return controller.calculate_command(bbox, frame_width, frame_height)


# ─────────────────────────────────────────────────────────────────────────────


def _draw_overlay(
    frame: np.ndarray,
    bbox: BoundingBox | None,
    command: PanTiltCommand | None,
    config: PControllerConfig,
) -> None:
    """Vẽ bbox, tâm ảnh, dead zone và vận tốc lên frame preview."""
    frame_height, frame_width = frame.shape[:2]
    center_x = frame_width // 2
    center_y = frame_height // 2
    dead_zone_half_width = int(frame_width * config.pan_dead_zone / 2.0)
    dead_zone_half_height = int(frame_height * config.tilt_dead_zone / 2.0)

    cv2.rectangle(
        frame,
        (center_x - dead_zone_half_width, center_y - dead_zone_half_height),
        (center_x + dead_zone_half_width, center_y + dead_zone_half_height),
        (255, 180, 0),
        2,
    )
    cv2.drawMarker(
        frame,
        (center_x, center_y),
        (255, 180, 0),
        cv2.MARKER_CROSS,
        20,
        2,
    )

    if bbox is None or command is None:
        cv2.putText(
            frame,
            "FACE: LOST",
            (20, frame_height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )
        return

    left = int(bbox.x)
    top = int(bbox.y)
    right = int(bbox.x + bbox.width)
    bottom = int(bbox.y + bbox.height)

    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
    cv2.circle(
        frame,
        (int(bbox.center_x), int(bbox.center_y)),
        5,
        (0, 255, 0),
        -1,
    )
    cv2.putText(
        frame,
        f"pan={command.pan_velocity:+.3f} tilt={command.tilt_velocity:+.3f}",
        (20, frame_height - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
    )


# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    raise SystemExit(main())