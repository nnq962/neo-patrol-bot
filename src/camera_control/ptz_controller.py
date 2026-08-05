"""Gửi các lệnh di chuyển Pan/Tilt liên tục qua ONVIF."""

import math
from datetime import timedelta
import time
from typing import Optional

from onvif import ONVIFClient

from src.camera_control.exceptions import CameraControlError
from src.camera_control.models import PtzStatus, PtzStatus

MIN_VELOCITY = -1.0
MAX_VELOCITY = 1.0
DEFAULT_MOVE_TIMEOUT_SECONDS = 1
POSITION_DELTA_THRESHOLD = 0.001 # Ngưỡng biến thiên tối thiểu để tính là đang di chuyển
MIN_PAN_RAW = -1.0
MAX_PAN_RAW = 1.0
MIN_TILT_RAW = 0.333
MAX_TILT_RAW = 1.0
MIN_ZOOM_RAW = 0.0
MAX_ZOOM_RAW = 16384.0


class OnvifPtzController:
    """Điều khiển Pan/Tilt bằng media profile có PTZ của camera."""

    def __init__(
        self,
        client: ONVIFClient,
        move_timeout_seconds: int = DEFAULT_MOVE_TIMEOUT_SECONDS,
    ) -> None:
        """Khởi tạo bộ điều khiển PTZ và trì hoãn truy vấn profile.

        Args:
            client: ONVIF client đã kết nối với camera.
            move_timeout_seconds: Thời gian camera duy trì mỗi lệnh di chuyển.

        Raises:
            ValueError: Khi thời gian duy trì không lớn hơn không.
        """
        if move_timeout_seconds <= 0:
            raise ValueError("move_timeout_seconds phải lớn hơn 0")

        self._client = client
        self._move_timeout = timedelta(seconds=move_timeout_seconds)
        self._profile_token: str | None = None
        # Lưu vết tọa độ và thời gian của lần đọc status liền trước
        self._last_pan: Optional[float] = None
        self._last_tilt: Optional[float] = None
        self._last_zoom: Optional[float] = None
        self._last_status_time: float = 0.0

    # ─────────────────────────────────────────────────────────────────────────

    def move_continuous(
        self,
        pan_velocity: float = 0.0,
        tilt_velocity: float = 0.0,
        zoom_velocity: float = 0.0,
    ) -> None:
        """Di chuyển Pan/Tilt/Zoom với vận tốc chuẩn hóa trong khoảng ``[-1, 1]``.

        Args:
            pan_velocity: Vận tốc quay ngang, âm sang trái và dương sang phải.
            tilt_velocity: Vận tốc quay dọc, âm đi xuống và dương đi lên.
            zoom_velocity: Vận tốc phóng to/thu nhỏ, âm zoom out và dương zoom in. Mặc định là 0.0.

        Returns:
            Không trả về giá trị.

        Raises:
            ValueError: Khi vận tốc không hữu hạn hoặc nằm ngoài giới hạn.
            CameraControlError: Khi camera từ chối hoặc không thực hiện được lệnh.
        """
        self._validate_velocity("pan_velocity", pan_velocity)
        self._validate_velocity("tilt_velocity", tilt_velocity)
        self._validate_velocity("zoom_velocity", zoom_velocity)

        # Nếu cả 3 vận tốc bằng 0 thì gửi lệnh stop
        if pan_velocity == 0.0 and tilt_velocity == 0.0 and zoom_velocity == 0.0:
            self.stop()
            return

        try:
            self._client.ptz().ContinuousMove(
                ProfileToken=self._get_profile_token(),
                Velocity={
                    "PanTilt": {
                        "x": pan_velocity,
                        "y": tilt_velocity,
                    },
                    "Zoom": {
                        "x": zoom_velocity,
                    },
                },
                Timeout=self._move_timeout,
            )
        except Exception as exc:
            raise CameraControlError(f"Không thể di chuyển PTZ: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        """Dừng chuyển động của các trục PTZ (Pan/Tilt/Zoom).

        Args:
            pan_tilt: Có dừng chuyển động Pan/Tilt hay không. Mặc định là True.
            zoom: Có dừng chuyển động Zoom hay không. Mặc định là True.

        Returns:
            Không trả về giá trị.

        Raises:
            CameraControlError: Khi camera không thực hiện được lệnh dừng.
        """
        # Nếu cả 2 đều False thì không cần gửi lệnh dừng lên camera
        if not pan_tilt and not zoom:
            return

        try:
            self._client.ptz().Stop(
                ProfileToken=self._get_profile_token(),
                PanTilt=pan_tilt,
                Zoom=zoom,
            )
        except Exception as exc:
            raise CameraControlError(f"Không thể dừng chuyển động PTZ: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> PtzStatus:
        """Đọc đầy đủ trạng thái PTZ (Pan/Tilt/Zoom và trạng thái di chuyển) hiện tại từ camera.

        Returns:
            Đối tượng PtzStatus chứa các thông số Pan, Tilt, Zoom và MoveStatus.

        Raises:
            CameraControlError: Khi camera không trả về được trạng thái PTZ.
        """
        try:
            # 1. Gọi lệnh ONVIF lấy raw status từ camera
            raw_status = self._client.ptz().GetStatus(
                ProfileToken=self._get_profile_token()
            )
            
            current_time = time.time()
            
            # Extracted coordinates
            pan = float(raw_status.Position.PanTilt.x) if raw_status.Position and raw_status.Position.PanTilt else 0.0
            tilt = float(raw_status.Position.PanTilt.y) if raw_status.Position and raw_status.Position.PanTilt else 0.0
            zoom = float(raw_status.Position.Zoom.x) if raw_status.Position and raw_status.Position.Zoom else 0.0

            # 2. Logic tự xác định Pan/Tilt Moving
            is_pan_tilt_moving = False
            if self._last_pan is not None and self._last_tilt is not None:
                delta_pan = abs(pan - self._last_pan)
                delta_tilt = abs(tilt - self._last_tilt)
                
                if delta_pan > POSITION_DELTA_THRESHOLD or delta_tilt > POSITION_DELTA_THRESHOLD:
                    is_pan_tilt_moving = True

            # 3. Logic tự xác định Zoom Moving
            is_zoom_moving = False
            if self._last_zoom is not None:
                delta_zoom = abs(zoom - self._last_zoom)
                if delta_zoom > POSITION_DELTA_THRESHOLD:
                    is_zoom_moving = True

            # 4. Cập nhật cache cho lần gọi kế tiếp
            self._last_pan = pan
            self._last_tilt = tilt
            self._last_zoom = zoom
            self._last_status_time = current_time

            # 5. Trả về PtzStatus dataclass
            return PtzStatus(
                pan=pan,
                tilt=tilt,
                zoom=zoom,
                is_pan_tilt_moving=is_pan_tilt_moving,
                is_zoom_moving=is_zoom_moving,
            )

        except CameraControlError:
            raise
        except Exception as exc:
            raise CameraControlError(
                f"Không thể đọc trạng thái PTZ: {exc}"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────────

    def _get_profile_token(self) -> str:
        """Tìm và lưu media profile đầu tiên có cấu hình PTZ.

        Returns:
            Token của media profile dùng để gửi lệnh PTZ.

        Raises:
            CameraControlError: Khi camera không công bố profile hỗ trợ PTZ.
        """
        if self._profile_token is not None:
            return self._profile_token

        try:
            profiles = self._client.media().GetProfiles()
        except Exception as exc:
            raise CameraControlError(f"Không thể đọc media profile: {exc}") from exc

        for profile in profiles:
            if getattr(profile, "PTZConfiguration", None) is None:
                continue

            token = getattr(profile, "token", None)
            if token:
                self._profile_token = str(token)
                return self._profile_token

        raise CameraControlError("Camera không có media profile hỗ trợ PTZ")

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_velocity(name: str, velocity: float) -> None:
        """Kiểm tra một thành phần vận tốc trước khi gửi tới camera.

        Args:
            name: Tên thành phần dùng trong thông báo lỗi.
            velocity: Giá trị vận tốc cần kiểm tra.

        Returns:
            Không trả về giá trị.

        Raises:
            ValueError: Khi vận tốc không hữu hạn hoặc nằm ngoài ``[-1, 1]``.
        """
        if not math.isfinite(velocity):
            raise ValueError(f"{name} phải là số hữu hạn")
        if not MIN_VELOCITY <= velocity <= MAX_VELOCITY:
            raise ValueError(f"{name} phải nằm trong khoảng [-1, 1]")
