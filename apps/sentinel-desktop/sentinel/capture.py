from __future__ import annotations

import platform

import mss
import mss.tools
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPoint
from PyQt6.QtGui import QGuiApplication

from .types import CaptureRegion, MonitorSnapshot


def _screen_for_point(x: int, y: int):
    screen = QGuiApplication.screenAt(QPoint(x, y))
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    return screen


def _find_scale_for_point(x: int, y: int) -> float:
    screen = _screen_for_point(x, y)
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


def _capture_region_macos(region: CaptureRegion) -> tuple[bytes, MonitorSnapshot]:
    center_x = region.x + max(1, region.width // 2)
    center_y = region.y + max(1, region.height // 2)
    screen = _screen_for_point(center_x, center_y)
    if screen is None:
        raise RuntimeError("No screen available for capture.")

    geometry = screen.geometry()
    local_x = region.x - geometry.x()
    local_y = region.y - geometry.y()
    width = max(1, region.width)
    height = max(1, region.height)
    pixmap = screen.grabWindow(0, local_x, local_y, width, height)
    if pixmap.isNull():
        raise RuntimeError("Qt screen capture returned an empty image.")

    image_bytes = QByteArray()
    buffer = QBuffer(image_bytes)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Failed to open Qt image buffer for capture.")
    try:
        if not pixmap.save(buffer, "PNG"):
            raise RuntimeError("Failed to encode Qt screen capture as PNG.")
    finally:
        buffer.close()

    monitor_snapshot = MonitorSnapshot(
        left=geometry.x(),
        top=geometry.y(),
        width=geometry.width(),
        height=geometry.height(),
        scale=float(screen.devicePixelRatio()),
    )
    return bytes(image_bytes), monitor_snapshot


def capture_region(region: CaptureRegion) -> tuple[bytes, MonitorSnapshot]:
    if platform.system().lower() == "darwin":
        return _capture_region_macos(region)

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
