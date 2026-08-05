"""Tính vận tốc Pan/Tilt để bám theo bounding box bằng điều khiển P."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Mô tả bounding box theo tọa độ pixel góc trên bên trái."""

    x: float
    y: float
    width: float
    height: float

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def center_x(self) -> float:
        """Tính tọa độ ngang tại tâm bounding box.

        Returns:
            Tọa độ tâm theo trục ngang, tính bằng pixel.
        """
        return self.x + self.width / 2.0

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def center_y(self) -> float:
        """Tính tọa độ dọc tại tâm bounding box.

        Returns:
            Tọa độ tâm theo trục dọc, tính bằng pixel.
        """
        return self.y + self.height / 2.0


@dataclass(frozen=True, slots=True)
class PanTiltCommand:
    """Chứa vận tốc PTZ và sai số ảnh đã chuẩn hóa của một chu kỳ điều khiển."""

    pan_velocity: float
    tilt_velocity: float
    error_x: float
    error_y: float

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def should_move(self) -> bool:
        """Cho biết command có yêu cầu camera di chuyển hay không.

        Returns:
            ``True`` nếu ít nhất một vận tốc khác không.
        """
        return self.pan_velocity != 0.0 or self.tilt_velocity != 0.0


@dataclass(frozen=True, slots=True)
class PControllerConfig:
    """Lưu hệ số và giới hạn của bộ điều khiển P hai trục."""

    pan_gain: float = 0.8
    tilt_gain: float = 0.8
    pan_dead_zone: float = 0.08
    tilt_dead_zone: float = 0.08
    max_pan_velocity: float = 0.6
    max_tilt_velocity: float = 0.5

    # ─────────────────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Kiểm tra các tham số điều khiển ngay sau khi khởi tạo.

        Returns:
            Không trả về giá trị.

        Raises:
            ValueError: Khi gain, dead zone hoặc giới hạn vận tốc không hợp lệ.
        """
        if self.pan_gain < 0.0 or self.tilt_gain < 0.0:
            raise ValueError("Gain phải lớn hơn hoặc bằng 0")
        if not 0.0 <= self.pan_dead_zone < 1.0:
            raise ValueError("pan_dead_zone phải nằm trong khoảng [0, 1)")
        if not 0.0 <= self.tilt_dead_zone < 1.0:
            raise ValueError("tilt_dead_zone phải nằm trong khoảng [0, 1)")
        if not 0.0 < self.max_pan_velocity <= 1.0:
            raise ValueError("max_pan_velocity phải nằm trong khoảng (0, 1]")
        if not 0.0 < self.max_tilt_velocity <= 1.0:
            raise ValueError("max_tilt_velocity phải nằm trong khoảng (0, 1]")


class PTrackingController:
    """Tính command Pan/Tilt từ vị trí bbox so với tâm frame."""

    def __init__(self, config: PControllerConfig | None = None) -> None:
        """Khởi tạo bộ điều khiển với cấu hình được cung cấp hoặc mặc định.

        Args:
            config: Hệ số và giới hạn điều khiển tùy chọn.
        """
        self._config = config or PControllerConfig()

    # ─────────────────────────────────────────────────────────────────────────

    def calculate_command(
        self,
        bbox: BoundingBox,
        frame_width: int,
        frame_height: int,
    ) -> PanTiltCommand:
        """Tính vận tốc Pan/Tilt để đưa tâm bbox về tâm frame.

        Args:
            bbox: Bounding box mục tiêu theo đơn vị pixel.
            frame_width: Chiều rộng frame theo pixel.
            frame_height: Chiều cao frame theo pixel.

        Returns:
            Command vận tốc và sai số ảnh đã chuẩn hóa.

        Raises:
            ValueError: Khi kích thước frame hoặc bbox không hợp lệ.
        """
        self._validate_input(bbox, frame_width, frame_height)

        frame_center_x = frame_width / 2.0
        frame_center_y = frame_height / 2.0

        error_x = (bbox.center_x - frame_center_x) / frame_center_x
        error_y = (bbox.center_y - frame_center_y) / frame_center_y

        pan_velocity = self._proportional_output(
            error=error_x,
            gain=self._config.pan_gain,
            dead_zone=self._config.pan_dead_zone,
            maximum=self._config.max_pan_velocity,
        )
        tilt_velocity = self._proportional_output(
            error=-error_y,
            gain=self._config.tilt_gain,
            dead_zone=self._config.tilt_dead_zone,
            maximum=self._config.max_tilt_velocity,
        )

        return PanTiltCommand(
            pan_velocity=pan_velocity,
            tilt_velocity=tilt_velocity,
            error_x=error_x,
            error_y=error_y,
        )

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _proportional_output(
        error: float,
        gain: float,
        dead_zone: float,
        maximum: float,
    ) -> float:
        """Áp dụng dead zone, gain và giới hạn lên một sai số.

        Args:
            error: Sai số chuẩn hóa của trục.
            gain: Hệ số tỷ lệ của trục.
            dead_zone: Vùng sai số không phát lệnh di chuyển.
            maximum: Độ lớn vận tốc tối đa.

        Returns:
            Vận tốc đã giới hạn trong khoảng cho phép.
        """
        if abs(error) <= dead_zone:
            return 0.0

        command_velocity = gain * error
        return max(-maximum, min(maximum, command_velocity))

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_input(
        bbox: BoundingBox,
        frame_width: int,
        frame_height: int,
    ) -> None:
        """Kiểm tra kích thước frame và bounding box.

        Args:
            bbox: Bounding box cần kiểm tra.
            frame_width: Chiều rộng frame theo pixel.
            frame_height: Chiều cao frame theo pixel.

        Returns:
            Không trả về giá trị.

        Raises:
            ValueError: Khi kích thước không lớn hơn không.
        """
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("Kích thước frame phải lớn hơn 0")
        if bbox.width <= 0.0 or bbox.height <= 0.0:
            raise ValueError("Kích thước bbox phải lớn hơn 0")
