"""Cung cấp detector và bộ điều khiển bám theo đối tượng từ frame."""

from src.tracking.controller import (
    BoundingBox,
    PControllerConfig,
    PTrackingController,
    PanTiltCommand,
)
from src.tracking.hand_detector import HandDetector

__all__ = [
    "BoundingBox",
    "HandDetector",
    "PControllerConfig",
    "PTrackingController",
    "PanTiltCommand",
]
