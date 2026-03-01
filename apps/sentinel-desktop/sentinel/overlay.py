from __future__ import annotations

from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .types import CaptureRegion


class OverlayBubble(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel("", self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout()
        layout.addWidget(self._label)
        layout.setContentsMargins(16, 14, 16, 14)
        self.setLayout(layout)

        self.setStyleSheet(
            """
            QWidget {
                background-color: rgba(14, 22, 30, 230);
                border: 1px solid rgba(68, 214, 162, 180);
                border-radius: 14px;
            }
            QLabel {
                color: #e9f6ff;
                font-size: 14px;
                line-height: 1.35;
            }
            """
        )

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide)

    def show_prompt(self, prompt: str, region: CaptureRegion, ttl_ms: int = 20000) -> None:
        self._label.setText(prompt)
        self.adjustSize()

        width = min(420, max(280, self.width()))
        self.resize(width, self.height())

        x = region.x + region.width + 12
        y = region.y

        screen = QGuiApplication.screenAt(QPoint(region.x, region.y)) or QGuiApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            if x + self.width() > geometry.right():
                x = max(geometry.left() + 12, region.x - self.width() - 12)
            if y + self.height() > geometry.bottom():
                y = max(geometry.top() + 12, geometry.bottom() - self.height() - 12)

        self.move(x, y)
        self.show()
        self.raise_()
        self._auto_hide_timer.start(ttl_ms)

    def hide_prompt(self) -> None:
        self._auto_hide_timer.stop()
        self.hide()
