"""Cung cấp facade đồng bộ để kết nối tới một camera ONVIF."""

import socket
from typing import Any

from onvif import CacheMode, ONVIFClient

from src.camera_control.config import CameraConfig
from src.camera_control.exceptions import CameraConnectionError
from src.camera_control.models import CameraDeviceInfo
from src.camera_control.ptz_controller import OnvifPtzController


class OnvifCamera:
    """Quản lý vòng đời kết nối của một camera ONVIF."""

    def __init__(self, config: CameraConfig) -> None:
        """Khởi tạo camera nhưng chưa mở kết nối mạng.

        Args:
            config: Cấu hình truy cập ONVIF của camera.
        """
        self._config = config
        self._client: ONVIFClient | None = None
        self._device_info: CameraDeviceInfo | None = None
        self._ptz_controller: OnvifPtzController | None = None

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Cho biết camera đã phản hồi một lệnh ONVIF hợp lệ hay chưa.

        Returns:
            ``True`` nếu kết nối đã được xác nhận, ngược lại là ``False``.
        """
        return self._client is not None and self._device_info is not None

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def device_info(self) -> CameraDeviceInfo:
        """Trả về thông tin thiết bị đã lấy trong lần kết nối gần nhất.

        Returns:
            Thông tin nhận dạng của camera.

        Raises:
            CameraConnectionError: Khi camera chưa được kết nối.
        """
        if self._device_info is None:
            raise CameraConnectionError("Camera chưa được kết nối")
        return self._device_info

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def ptz(self) -> OnvifPtzController:
        """Trả về bộ điều khiển PTZ sau khi camera đã kết nối.

        Returns:
            Bộ điều khiển Continuous Pan/Tilt của camera.

        Raises:
            CameraConnectionError: Khi camera chưa được kết nối.
        """
        if self._ptz_controller is None:
            raise CameraConnectionError("Camera chưa được kết nối")
        return self._ptz_controller

    # ─────────────────────────────────────────────────────────────────────────

    def connect(self) -> CameraDeviceInfo:
        """Kết nối ONVIF và gọi Device Service để xác nhận camera hoạt động.

        Returns:
            Thông tin nhận dạng camera khi kết nối thành công.

        Raises:
            CameraConnectionError: Khi camera không phản hồi hoặc xác thực thất bại.
        """
        try:
            self._check_tcp_port()
            client = ONVIFClient(
                host=self._config.host,
                port=self._config.onvif_port,
                username=self._config.username,
                password=self._config.password,
                timeout=self._config.timeout_seconds,
                cache=CacheMode.MEM,
            )
            response = client.devicemgmt().GetDeviceInformation()
            device_info = self._map_device_info(response)
        except TimeoutError as exc:
            self.disconnect()
            raise CameraConnectionError(
                "Hết thời gian kết nối tới "
                f"{self._config.host}:{self._config.onvif_port}; "
                "hãy kiểm tra camera đang bật, địa chỉ IP, cổng ONVIF và kết nối mạng"
            ) from exc
        except OSError as exc:
            self.disconnect()
            raise CameraConnectionError(
                "Không thể mở kết nối tới "
                f"{self._config.host}:{self._config.onvif_port}: {exc}"
            ) from exc
        except Exception as exc:
            self.disconnect()
            raise CameraConnectionError(
                "Không thể kết nối ONVIF tới "
                f"{self._config.host}:{self._config.onvif_port}: {exc}"
            ) from exc

        self._client = client
        self._device_info = device_info
        self._ptz_controller = OnvifPtzController(client)
        return device_info

    # ─────────────────────────────────────────────────────────────────────────

    def _check_tcp_port(self) -> None:
        """Kiểm tra cổng ONVIF có nhận kết nối TCP trước khi gọi SOAP.

        Returns:
            Không trả về giá trị.

        Raises:
            OSError: Khi host không thể truy cập hoặc cổng ONVIF không mở.
        """
        with socket.create_connection(
            (self._config.host, self._config.onvif_port),
            timeout=self._config.timeout_seconds,
        ):
            return

    # ─────────────────────────────────────────────────────────────────────────

    def disconnect(self) -> None:
        """Xóa trạng thái client vì ONVIF sử dụng các request HTTP độc lập.

        Returns:
            Không trả về giá trị.
        """
        self._client = None
        self._device_info = None
        self._ptz_controller = None

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _map_device_info(response: Any) -> CameraDeviceInfo:
        """Chuyển response động của Zeep thành model nội bộ ổn định.

        Args:
            response: Kết quả từ lệnh ONVIF ``GetDeviceInformation``.

        Returns:
            Thông tin thiết bị không phụ thuộc kiểu dữ liệu của Zeep.
        """
        return CameraDeviceInfo(
            manufacturer=str(getattr(response, "Manufacturer", "")),
            model=str(getattr(response, "Model", "")),
            firmware_version=str(getattr(response, "FirmwareVersion", "")),
            serial_number=str(getattr(response, "SerialNumber", "")),
            hardware_id=str(getattr(response, "HardwareId", "")),
        )
