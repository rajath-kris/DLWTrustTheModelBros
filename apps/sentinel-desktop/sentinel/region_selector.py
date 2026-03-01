from __future__ import annotations

import time
from typing import Any, Callable

from PyQt6.QtCore import QEasingCurve, QEventLoop, QPoint, QPropertyAnimation, QRect, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .config import settings
from .types import CaptureRegion
from .ui_theme import get_ui_font_family


TelemetryCallback = Callable[[str, dict[str, Any]], None]


class RegionSelector(QWidget):
    finished = pyqtSignal()

    def __init__(
        self,
        telemetry_callback: TelemetryCallback | None = None,
        instruction_text: str = "Select the part you're struggling with",
        hint_text: str = "Drag to capture  |  Esc to cancel",
    ) -> None:
        super().__init__()
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.selected_region: CaptureRegion | None = None
        self._telemetry_callback = telemetry_callback
        self._instruction_text = instruction_text
        self._hint_text = hint_text
        self._opened_at_monotonic: float | None = None
        self._closed_emitted = False
        self._pill_opacity = 0.0
        self._font_family = get_ui_font_family()
        self._pill_animation = QPropertyAnimation(self, b"pill_opacity", self)
        self._pill_animation.setDuration(max(120, settings.ui_fade_in_ms))
        self._pill_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        geometry = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def showEvent(self, event) -> None:
        self._opened_at_monotonic = time.monotonic()
        self._pill_animation.stop()
        self.set_pill_opacity(0.0)
        self._pill_animation.setStartValue(0.0)
        self._pill_animation.setEndValue(1.0)
        self._pill_animation.start()
        self._emit("selector_opened", region=None)
        super().showEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.globalPosition().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            self._current = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._origin and self._current:
            rect = QRect(self._origin, self._current).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.selected_region = CaptureRegion(
                    x=rect.x(),
                    y=rect.y(),
                    width=rect.width(),
                    height=rect.height(),
                )
                self._emit(
                    "selector_completed",
                    region=self._region_payload(self.selected_region),
                    duration_ms=self._duration_ms(),
                )
            else:
                self._emit(
                    "selector_cancelled",
                    reason="small_region",
                    duration_ms=self._duration_ms(),
                    region=self._region_payload(
                        CaptureRegion(x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height())
                    ),
                )
                self._closed_emitted = True
            self.finished.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.selected_region = None
            self._emit(
                "selector_cancelled",
                reason="escape",
                duration_ms=self._duration_ms(),
                region=None,
            )
            self._closed_emitted = True
            self.finished.emit()
            self.close()

    def closeEvent(self, event) -> None:
        if self.selected_region is None and not self._closed_emitted:
            self._emit(
                "selector_cancelled",
                reason="closed",
                duration_ms=self._duration_ms(),
                region=None,
            )
        super().closeEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        self._draw_instruction_pill(painter)

        if self._origin and self._current:
            rect = QRect(self._origin, self._current).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#44d6a2"), 2))
            painter.drawRect(rect)

    def _draw_instruction_pill(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        primary_font = QFont(self._font_family, 14)
        secondary_font = QFont(self._font_family, 11)

        painter.setFont(primary_font)
        primary_metrics = painter.fontMetrics()
        painter.setFont(secondary_font)
        secondary_metrics = painter.fontMetrics()

        primary_w = primary_metrics.horizontalAdvance(self._instruction_text)
        secondary_w = secondary_metrics.horizontalAdvance(self._hint_text)
        width = max(primary_w, secondary_w) + 54
        height = primary_metrics.height() + secondary_metrics.height() + 30
        width = max(360, min(width, max(420, self.width() - 40)))

        x = (self.width() - width) // 2
        y = 24
        pill_rect = QRect(x, y, width, height)
        painter.setBrush(QColor(18, 22, 30, self._alpha(220)))
        painter.drawRoundedRect(pill_rect, 22, 22)
        painter.setBrush(QColor(255, 255, 255, self._alpha(9)))
        painter.drawRoundedRect(QRect(x + 1, y + 1, width - 2, height - 2), 21, 21)

        painter.setFont(primary_font)
        painter.setPen(QColor(243, 248, 255, self._alpha(245)))
        painter.drawText(
            QRect(x + 24, y + 8, width - 48, primary_metrics.height() + 4),
            Qt.AlignmentFlag.AlignCenter,
            self._instruction_text,
        )
        painter.setFont(secondary_font)
        painter.setPen(QColor(175, 189, 210, self._alpha(230)))
        painter.drawText(
            QRect(
                x + 24,
                y + primary_metrics.height() + 9,
                width - 48,
                secondary_metrics.height() + 8,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._hint_text,
        )
        painter.restore()

    def _duration_ms(self) -> int | None:
        if self._opened_at_monotonic is None:
            return None
        return int(max(0.0, (time.monotonic() - self._opened_at_monotonic) * 1000.0))

    def get_pill_opacity(self) -> float:
        return self._pill_opacity

    def set_pill_opacity(self, value: float) -> None:
        self._pill_opacity = max(0.0, min(1.0, float(value)))
        self.update()

    pill_opacity = pyqtProperty(float, fget=get_pill_opacity, fset=set_pill_opacity)

    def _alpha(self, raw_alpha: int) -> int:
        return max(0, min(255, int(round(raw_alpha * self._pill_opacity))))

    def _region_payload(self, region: CaptureRegion | None) -> dict[str, int] | None:
        if region is None:
            return None
        return {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
        }

    def _emit(self, event: str, **fields: Any) -> None:
        if self._telemetry_callback is None:
            return
        self._telemetry_callback(event, fields)


def select_region(telemetry_callback: TelemetryCallback | None = None) -> CaptureRegion | None:
    selector = RegionSelector(telemetry_callback=telemetry_callback)
    loop = QEventLoop()
    selector.finished.connect(loop.quit)
    selector.showFullScreen()
    selector.activateWindow()
    selector.raise_()
    loop.exec()
    return selector.selected_region
