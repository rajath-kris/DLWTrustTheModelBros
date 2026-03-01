from __future__ import annotations

from PyQt6.QtCore import QEventLoop, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .types import CaptureRegion


class RegionSelector(QWidget):
    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.selected_region: CaptureRegion | None = None

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
            self.finished.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.selected_region = None
            self.finished.emit()
            self.close()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))

        if self._origin and self._current:
            rect = QRect(self._origin, self._current).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#44d6a2"), 2))
            painter.drawRect(rect)



def select_region() -> CaptureRegion | None:
    selector = RegionSelector()
    loop = QEventLoop()
    selector.finished.connect(loop.quit)
    selector.showFullScreen()
    selector.activateWindow()
    selector.raise_()
    loop.exec()
    return selector.selected_region
