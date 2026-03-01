from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaptureRegion:
    x: int
    y: int
    width: int
    height: int


@dataclass
class MonitorSnapshot:
    left: int
    top: int
    width: int
    height: int
    scale: float


@dataclass
class WindowMetadata:
    app_name: str
    window_title: str
