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
from utils import LOGGER



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


config = CameraConfig.from_env()
print(config)
camera = _connect_camera(config)
ptz = camera.ptz

# time.sleep(30)

import time
import statistics

# from __future__ import annotations

import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt


@dataclass
class Measurement:
    direction: str
    command_velocity: float
    repeat_index: int
    start_position: float
    end_position: float
    displacement: float
    move_rtt_ms: float
    stop_rtt_ms: float


def signed_circular_delta(
    start: float,
    end: float,
    period: float = 2.0,
) -> float:
    """
    Tính độ dịch chuyển có dấu khi tọa độ pan wrap trong miền [-1, 1].

    Ví dụ:
        0.95 -> -0.95 được hiểu là dịch chuyển +0.10,
        thay vì -1.90.

    Chỉ sử dụng nếu camera thực sự wrap tọa độ pan từ 1 về -1.
    """
    delta = end - start

    if delta > period / 2:
        delta -= period
    elif delta < -period / 2:
        delta += period

    return delta


def wait_until_settled(
    ptz,
    wait_seconds: float = 1.0,
) -> float:
    """
    Chờ camera dừng và firmware cập nhật trạng thái,
    sau đó đọc vị trí pan.
    """
    time.sleep(wait_seconds)
    return ptz.get_status().pan


def measure_single_run(
    ptz,
    velocity: float,
    duration: float,
    settle_seconds: float,
    repeat_index: int,
    use_circular_position: bool = True,
) -> Measurement:
    """
    Chạy camera với một vận tốc trong một khoảng thời gian cố định
    và đo tổng quãng đường từ vị trí ban đầu đến vị trí sau khi dừng.
    """
    direction = "right" if velocity > 0 else "left"

    start_position = ptz.get_status().pan

    move_started = time.perf_counter()
    ptz.move_continuous(
        pan_velocity=velocity,
        tilt_velocity=0.0,
    )
    move_finished = time.perf_counter()

    time.sleep(duration)

    stop_started = time.perf_counter()
    ptz.stop()
    stop_finished = time.perf_counter()

    end_position = wait_until_settled(
        ptz=ptz,
        wait_seconds=settle_seconds,
    )

    if use_circular_position:
        displacement = signed_circular_delta(
            start=start_position,
            end=end_position,
        )
    else:
        displacement = end_position - start_position

    return Measurement(
        direction=direction,
        command_velocity=velocity,
        repeat_index=repeat_index,
        start_position=start_position,
        end_position=end_position,
        displacement=displacement,
        move_rtt_ms=(move_finished - move_started) * 1000,
        stop_rtt_ms=(stop_finished - stop_started) * 1000,
    )


def save_measurements_to_csv(
    measurements: list[Measurement],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "direction",
                "command_velocity",
                "repeat_index",
                "start_position",
                "end_position",
                "displacement",
                "absolute_displacement",
                "move_rtt_ms",
                "stop_rtt_ms",
            ]
        )

        for measurement in measurements:
            writer.writerow(
                [
                    measurement.direction,
                    measurement.command_velocity,
                    measurement.repeat_index,
                    measurement.start_position,
                    measurement.end_position,
                    measurement.displacement,
                    abs(measurement.displacement),
                    measurement.move_rtt_ms,
                    measurement.stop_rtt_ms,
                ]
            )


def aggregate_measurements(
    measurements: list[Measurement],
) -> dict[float, dict[str, float]]:
    """
    Gom các lần đo theo command velocity.
    """
    grouped: dict[float, list[Measurement]] = {}

    for measurement in measurements:
        grouped.setdefault(
            measurement.command_velocity,
            [],
        ).append(measurement)

    aggregated: dict[float, dict[str, float]] = {}

    for velocity, group in grouped.items():
        distances = [
            abs(measurement.displacement)
            for measurement in group
        ]

        aggregated[velocity] = {
            "mean": statistics.mean(distances),
            "median": statistics.median(distances),
            "std": (
                statistics.stdev(distances)
                if len(distances) > 1
                else 0.0
            ),
            "min": min(distances),
            "max": max(distances),
        }

    return aggregated


def plot_camera_characteristic(
    measurements: list[Measurement],
    duration: float,
    output_path: Path,
) -> None:
    aggregated = aggregate_measurements(measurements)

    velocities = sorted(aggregated.keys())
    mean_distances = [
        aggregated[velocity]["mean"]
        for velocity in velocities
    ]
    std_distances = [
        aggregated[velocity]["std"]
        for velocity in velocities
    ]

    figure, axis = plt.subplots(figsize=(10, 6))

    axis.errorbar(
        velocities,
        mean_distances,
        yerr=std_distances,
        marker="o",
        capsize=5,
    )

    axis.set_title(
        f"Đặc tính vận tốc PTZ — thời gian chạy {duration:.2f} giây"
    )
    axis.set_xlabel("Vận tốc lệnh ONVIF")
    axis.set_ylabel("Quãng đường pan trung bình |Δpan|")
    axis.grid(True)
    axis.axhline(0.0, linewidth=1)
    axis.axvline(0.0, linewidth=1)

    figure.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)

    plt.show()


def print_summary(
    measurements: list[Measurement],
    duration: float,
) -> None:
    aggregated = aggregate_measurements(measurements)

    print("\n=== KẾT QUẢ ĐẶC TÍNH HÓA CAMERA ===")
    print(
        f"{'Velocity':>10} | "
        f"{'Mean Δpan':>12} | "
        f"{'Est. speed':>12} | "
        f"{'Std':>10} | "
        f"{'Min':>10} | "
        f"{'Max':>10}"
    )
    print("-" * 78)

    for velocity in sorted(aggregated.keys()):
        result = aggregated[velocity]

        # Đây chỉ là tốc độ trung bình hiệu dụng của toàn bộ lần chạy,
        # bao gồm cả độ trễ Stop và quán tính.
        estimated_speed = result["mean"] / duration

        print(
            f"{velocity:>+10.2f} | "
            f"{result['mean']:>12.4f} | "
            f"{estimated_speed:>12.4f} | "
            f"{result['std']:>10.4f} | "
            f"{result['min']:>10.4f} | "
            f"{result['max']:>10.4f}"
        )


def characterize_camera(
    ptz,
    velocities: list[float],
    duration: float = 0.8,
    repeats: int = 3,
    settle_seconds: float = 1.0,
    between_runs_seconds: float = 0.5,
    use_circular_position: bool = True,
) -> list[Measurement]:
    measurements: list[Measurement] = []

    total_runs = len(velocities) * repeats
    current_run = 0

    try:
        for velocity in velocities:
            for repeat_index in range(1, repeats + 1):
                current_run += 1

                print(
                    f"\n[{current_run}/{total_runs}] "
                    f"velocity={velocity:+.2f}, "
                    f"lần={repeat_index}/{repeats}"
                )

                measurement = measure_single_run(
                    ptz=ptz,
                    velocity=velocity,
                    duration=duration,
                    settle_seconds=settle_seconds,
                    repeat_index=repeat_index,
                    use_circular_position=use_circular_position,
                )

                measurements.append(measurement)

                print(
                    f"  Pan: "
                    f"{measurement.start_position:+.4f} "
                    f"-> {measurement.end_position:+.4f}"
                )
                print(
                    f"  Δpan: {measurement.displacement:+.4f}"
                )
                print(
                    f"  Move RTT: {measurement.move_rtt_ms:.1f} ms"
                )
                print(
                    f"  Stop RTT: {measurement.stop_rtt_ms:.1f} ms"
                )

                time.sleep(between_runs_seconds)

    finally:
        # Bảo đảm camera được dừng nếu chương trình lỗi hoặc Ctrl+C.
        try:
            ptz.stop()
        except Exception as error:
            print(f"Không thể gửi Stop cuối cùng: {error}")

    return measurements


# ============================================================
# PHẦN CHẠY THỬ NGHIỆM
# ============================================================

config = CameraConfig.from_env()
print(config)

camera = _connect_camera(config)
ptz = camera.ptz

# Không cần sleep(30) trừ khi camera cần thời gian khởi động.
time.sleep(1)

VELOCITIES = [
    -0.8,
    -0.6,
    -0.4,
    -0.3,
    -0.2,
    -0.15,
    -0.1,
    0.1,
    0.15,
    0.2,
    0.3,
    0.4,
    0.6,
    0.8,
]

MOVE_DURATION_SECONDS = 0.8
REPEATS_PER_VELOCITY = 3

measurements = characterize_camera(
    ptz=ptz,
    velocities=VELOCITIES,
    duration=MOVE_DURATION_SECONDS,
    repeats=REPEATS_PER_VELOCITY,
    settle_seconds=1.0,
    between_runs_seconds=0.5,

    # Đặt False nếu tọa độ pan không wrap từ +1 sang -1.
    use_circular_position=True,
)

output_directory = Path("outputs/ptz_characterization")

save_measurements_to_csv(
    measurements=measurements,
    output_path=output_directory / "pan_measurements.csv",
)

print_summary(
    measurements=measurements,
    duration=MOVE_DURATION_SECONDS,
)

plot_camera_characteristic(
    measurements=measurements,
    duration=MOVE_DURATION_SECONDS,
    output_path=output_directory / "pan_characteristic.png",
)

print("\nĐã lưu:")
print(f"  CSV : {output_directory / 'pan_measurements.csv'}")
print(f"  Plot: {output_directory / 'pan_characteristic.png'}")