# Quy ước Phát triển Dự án (Neo Patrol Bot)

## 1. Môi trường & Quản lý Package

- **Python Version:** 3.10
- **Package Manager:** Dự án sử dụng `uv` để quản lý môi trường ảo và dependencies.
- **Thêm package:** Luôn dùng `uv add <package-name>` (ví dụ: `uv add onvif-zeep`), **không** cài đặt trực tiếp bằng `pip`.

## 2. Quy ước Code Formatting & Phân tách

Dùng đường kẻ phân tách để code dễ đọc và nhất quán:

- **Phân tách các method trong cùng một Class:**

  ```
  ─────────────────────────────────────────────────────────────────────────
  ```

- **Phân tách các hàm top-level (không thuộc class nào):**

  ```
  ─────────────────────────────────────────────────────────────────────────────
  ```

### Naming Conventions

| Đối tượng | Quy ước | Ví dụ |
|---|---|---|
| File / Folder | `snake_case` | `camera_controller.py`, `camera-control/` |
| Class | `PascalCase` | `OnvifCamera` |
| Hàm / Biến | `snake_case` | `get_stream_url`, `is_connected` |
| Hằng số (Constants) | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT`, `LINE_CHAR` |

## 3. Type Hinting & Docstrings

- Tất cả hàm/method phải khai báo **Type Hints** đầy đủ cho cả tham số đầu vào và giá trị trả về.

  ```python
  def connect_camera(ip: str, port: int = 80) -> bool:
      ...
  ```

- Tất cả hàm/method phải có **Docstring bằng tiếng Việt** giải thích ngắn gọn mục đích, tham số và kết quả trả về.

## 4. Logging & Debugging

- **KHÔNG** sử dụng `print()` để log hoặc debug code.
- Sử dụng logger nội bộ đã được cấu hình sẵn trong gói `utils`:

  ```python
  from utils import LOGGER

  LOGGER.info("Đã kết nối thành công tới camera ONVIF")
  LOGGER.error("Lỗi mất kết nối luồng RTSP")
  ```