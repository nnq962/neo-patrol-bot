"""Gửi các lệnh di chuyển Pan/Tilt liên tục qua ONVIF."""

import math
from datetime import timedelta

from onvif import ONVIFClient

from src.camera_control.exceptions import CameraControlError
from src.camera_control.models import PtzPosition

MIN_VELOCITY = -1.0
MAX_VELOCITY = 1.0
DEFAULT_MOVE_TIMEOUT_SECONDS = 1


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

    # ─────────────────────────────────────────────────────────────────────────

    def move_continuous(self, pan_velocity: float, tilt_velocity: float) -> None:
        """Di chuyển Pan/Tilt với vận tốc chuẩn hóa trong khoảng ``[-1, 1]``.

        Args:
            pan_velocity: Vận tốc quay ngang, âm sang trái và dương sang phải.
            tilt_velocity: Vận tốc quay dọc, âm đi xuống và dương đi lên.

        Returns:
            Không trả về giá trị.

        Raises:
            ValueError: Khi vận tốc không hữu hạn hoặc nằm ngoài giới hạn.
            CameraControlError: Khi camera từ chối hoặc không thực hiện được lệnh.
        """
        self._validate_velocity("pan_velocity", pan_velocity)
        self._validate_velocity("tilt_velocity", tilt_velocity)

        if pan_velocity == 0.0 and tilt_velocity == 0.0:
            self.stop()
            return

        try:
            self._client.ptz().ContinuousMove(
                ProfileToken=self._get_profile_token(),
                Velocity={
                    "PanTilt": {
                        "x": pan_velocity,
                        "y": tilt_velocity,
                    }
                },
                Timeout=self._move_timeout,
            )
        except Exception as exc:
            raise CameraControlError(f"Không thể di chuyển Pan/Tilt: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Dừng hai trục Pan/Tilt mà không thay đổi trạng thái Zoom.

        Returns:
            Không trả về giá trị.

        Raises:
            CameraControlError: Khi camera không thực hiện được lệnh dừng.
        """
        try:
            self._client.ptz().Stop(
                ProfileToken=self._get_profile_token(),
                PanTilt=True,
                Zoom=False,
            )
        except Exception as exc:
            raise CameraControlError(f"Không thể dừng Pan/Tilt: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────

    def get_position(self) -> PtzPosition:
        """Đọc vị trí Pan/Tilt hiện tại từ PTZ status của camera.

        Returns:
            Vị trí Pan/Tilt trong coordinate space do camera cung cấp.

        Raises:
            CameraControlError: Khi camera không trả về được vị trí Pan/Tilt.
        """
        try:
            status = self._client.ptz().GetStatus(
                ProfileToken=self._get_profile_token()
            )
            position = getattr(status, "Position", None)
            pan_tilt = getattr(position, "PanTilt", None)
            if pan_tilt is None:
                raise CameraControlError("Camera không trả về vị trí Pan/Tilt")

            return PtzPosition(
                pan=float(getattr(pan_tilt, "x")),
                tilt=float(getattr(pan_tilt, "y")),
            )
        except CameraControlError:
            raise
        except Exception as exc:
            raise CameraControlError(
                f"Không thể đọc vị trí Pan/Tilt: {exc}"
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
