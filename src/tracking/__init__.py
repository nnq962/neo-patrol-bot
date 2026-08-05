"""Cung cấp detector và bộ điều khiển bám theo đối tượng từ frame."""

from src.tracking.controller import (
    BoundingBox,
    PControllerConfig,
    PTrackingController,
    PanTiltCommand,
)
from src.tracking.face_detector import FaceDetector
from src.tracking.hand_detector import HandDetector

__all__ = [
    "BoundingBox",
    "FaceDetector",
    "HandDetector",
    "PControllerConfig",
    "PTrackingController",
    "PanTiltCommand",
]

