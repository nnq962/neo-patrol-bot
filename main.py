"""Chạy thử nghiệm camera PTZ bám theo bounding box bàn tay."""

import time

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
    HandDetector,
    PControllerConfig,
    PTrackingController,
    PanTiltCommand,
)
from utils import LOGGER

WINDOW_NAME = "Neo Patrol Bot - Hand Tracking"
CONTROL_INTERVAL_SECONDS = 0.1


def main() -> int:
    """Kết nối camera và chạy vòng lặp phát hiện, bám theo bàn tay.

    Returns:
        Mã thoát ``0`` khi dừng bình thường, ngược lại là ``1``.
    """
    try:
        config = CameraConfig.from_env()
        camera = _connect_camera(config)
        _run_hand_tracking(camera, config)
    except KeyboardInterrupt:
        LOGGER.info("Đã dừng hand tracking bằng bàn phím")
        return 0
    except (
        CameraConfigError,
        CameraConnectionError,
        CameraControlError,
        MediaSourceError,
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        LOGGER.error("Hand tracking thất bại: %s", exc)
        return 1

    return 0


# ─────────────────────────────────────────────────────────────────────────────


def _connect_camera(config: CameraConfig) -> OnvifCamera:
    """Kết nối ONVIF và ghi thông tin nhận dạng camera.

    Args:
        config: Cấu hình ONVIF và RTSP của camera.

    Returns:
        Camera đã kết nối thành công.
    """
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


def _run_hand_tracking(camera: OnvifCamera, config: CameraConfig) -> None:
    """Đọc RTSP, phát hiện tay và gửi command Pan/Tilt theo chu kỳ.

    Args:
        camera: Camera ONVIF đã kết nối.
        config: Cấu hình chứa RTSP URL của camera.

    Returns:
        Không trả về giá trị.
    """
    controller_config = PControllerConfig()
    controller = PTrackingController(controller_config)
    is_moving = False
    hand_was_detected = False
    last_control_time = 0.0

    LOGGER.info("Bắt đầu hand tracking; nhấn Q hoặc ESC để dừng")
    try:
        with HandDetector() as detector, MediaSources(config.rtsp_url) as media:
            for frames, _ in media:
                frame = frames[0]
                bbox = detector.detect(frame)
                command = _calculate_command(controller, bbox, frame)
                now = time.monotonic()

                if bbox is None:
                    if hand_was_detected:
                        LOGGER.info("Mất dấu bàn tay; dừng Pan/Tilt")
                    hand_was_detected = False
                    if is_moving:
                        camera.ptz.stop()
                        is_moving = False
                else:
                    if not hand_was_detected:
                        LOGGER.info("Đã phát hiện bàn tay")
                    hand_was_detected = True
                    if now - last_control_time >= CONTROL_INTERVAL_SECONDS:
                        is_moving = _send_command(camera, command, is_moving)
                        last_control_time = now

                _draw_overlay(frame, bbox, command, controller_config)
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    LOGGER.info("Nhận yêu cầu dừng từ cửa sổ preview")
                    break
    finally:
        if is_moving:
            try:
                camera.ptz.stop()
            except CameraControlError as exc:
                LOGGER.error("Không thể dừng camera khi thoát: %s", exc)
        cv2.destroyAllWindows()


# ─────────────────────────────────────────────────────────────────────────────


def _calculate_command(
    controller: PTrackingController,
    bbox: BoundingBox | None,
    frame: np.ndarray,
) -> PanTiltCommand | None:
    """Tính command P từ bbox nếu phát hiện được bàn tay.

    Args:
        controller: Bộ điều khiển P Pan/Tilt.
        bbox: Bounding box bàn tay hoặc ``None``.
        frame: Frame dùng để lấy kích thước ảnh.

    Returns:
        Command Pan/Tilt hoặc ``None`` khi không có bàn tay.
    """
    if bbox is None:
        return None

    frame_height, frame_width = frame.shape[:2]
    return controller.calculate_command(bbox, frame_width, frame_height)


# ─────────────────────────────────────────────────────────────────────────────


def _send_command(
    camera: OnvifCamera,
    command: PanTiltCommand | None,
    is_moving: bool,
) -> bool:
    """Gửi command Pan/Tilt và trả về trạng thái chuyển động mới.

    Args:
        camera: Camera ONVIF đã kết nối.
        command: Command do P controller tạo ra.
        is_moving: Trạng thái chuyển động trước khi gửi command.

    Returns:
        ``True`` nếu camera đang được yêu cầu di chuyển.
    """
    if command is not None and command.should_move:
        camera.ptz.move_continuous(
            pan_velocity=command.pan_velocity,
            tilt_velocity=command.tilt_velocity,
        )
        return True

    if is_moving:
        camera.ptz.stop()
    return False


# ─────────────────────────────────────────────────────────────────────────────


def _draw_overlay(
    frame: np.ndarray,
    bbox: BoundingBox | None,
    command: PanTiltCommand | None,
    config: PControllerConfig,
) -> None:
    """Vẽ bbox, tâm ảnh, dead zone và vận tốc lên frame preview.

    Args:
        frame: Frame BGR sẽ được vẽ trực tiếp.
        bbox: Bounding box bàn tay nếu có.
        command: Command tracking tương ứng nếu có.
        config: Cấu hình dùng để biểu diễn dead zone.

    Returns:
        Không trả về giá trị.
    """
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
            "HAND: LOST - PTZ STOP",
            (20, 35),
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
    cv2.circle(frame, (int(bbox.center_x), int(bbox.center_y)), 5, (0, 255, 0), -1)
    cv2.putText(
        frame,
        f"pan={command.pan_velocity:+.3f} tilt={command.tilt_velocity:+.3f}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
