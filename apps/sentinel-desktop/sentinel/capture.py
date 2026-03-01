from __future__ import annotations

import mss
import mss.tools
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QGuiApplication

from .types import CaptureRegion, MonitorSnapshot


def _find_scale_for_point(x: int, y: int) -> float:
    screen = QGuiApplication.screenAt(QPoint(x, y))
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return 1.0
    return float(screen.devicePixelRatio())


def _pick_monitor(monitors: list[dict], px: int, py: int) -> dict:
    for monitor in monitors[1:]:
        left = monitor["left"]
        top = monitor["top"]
        width = monitor["width"]
        height = monitor["height"]
        if left <= px < left + width and top <= py < top + height:
            return monitor
    return monitors[1] if len(monitors) > 1 else monitors[0]


def capture_region(region: CaptureRegion) -> tuple[bytes, MonitorSnapshot]:
    scale = _find_scale_for_point(region.x + 1, region.y + 1)
    scaled_x = int(region.x * scale)
    scaled_y = int(region.y * scale)
    scaled_w = int(region.width * scale)
    scaled_h = int(region.height * scale)

    with mss.mss() as sct:
        monitor = _pick_monitor(sct.monitors, scaled_x + (scaled_w // 2), scaled_y + (scaled_h // 2))

        shot = sct.grab(
            {
                "left": scaled_x,
                "top": scaled_y,
                "width": max(1, scaled_w),
                "height": max(1, scaled_h),
            }
        )
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)

    monitor_snapshot = MonitorSnapshot(
        left=int(monitor["left"]),
        top=int(monitor["top"]),
        width=int(monitor["width"]),
        height=int(monitor["height"]),
        scale=scale,
    )
    return png_bytes, monitor_snapshot
