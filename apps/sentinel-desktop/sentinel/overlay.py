from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .types import CaptureRegion


class OverlayState(str, Enum):
    HIDDEN = "hidden"
    ANALYZING = "analyzing"
    PROMPT = "prompt"
    ERROR = "error"


class OverlayBubble(QWidget):
    retry_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()

    def __init__(
        self,
        min_width: int = 320,
        max_width: int = 520,
        loading_dot_interval_ms: int = 350,
    ) -> None:
        super().__init__()
        self._min_width = max(220, min_width)
        self._max_width = max(self._min_width, max_width)
        self._loading_dot_interval_ms = max(120, loading_dot_interval_ms)
        self._state: OverlayState = OverlayState.HIDDEN
        self._loading_frames = ["-", "--", "---", "----", "---", "--"]
        self._loading_index = 0
        self._anchor_region: CaptureRegion | None = None
        self._telemetry_callback: Callable[[str, dict[str, Any]], None] | None = None

        self.setObjectName("OverlayRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._status_label = QLabel("Sentinel", self)
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setWordWrap(False)

        self._message_label = QLabel("", self)
        self._message_label.setObjectName("MessageLabel")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._loading_label = QLabel("", self)
        self._loading_label.setObjectName("LoadingLabel")
        self._loading_label.setWordWrap(False)
        self._loading_label.hide()

        self._retry_button = QPushButton("Retry", self)
        self._retry_button.setObjectName("RetryButton")
        self._retry_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._retry_button.clicked.connect(self._on_retry_clicked)

        self._dismiss_button = QPushButton("Dismiss", self)
        self._dismiss_button.setObjectName("DismissButton")
        self._dismiss_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self._retry_button)
        actions_layout.addWidget(self._dismiss_button)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(7)
        root_layout.addWidget(self._status_label)
        root_layout.addWidget(self._message_label)
        root_layout.addWidget(self._loading_label)
        root_layout.addLayout(actions_layout)
        self.setLayout(root_layout)

        self.setStyleSheet(
            """
            #OverlayRoot {
                background-color: rgba(8, 9, 12, 242);
                border: 1px solid rgba(236, 240, 245, 42);
                border-radius: 22px;
            }

            QLabel {
                color: #f5f7fa;
                font-size: 14px;
                line-height: 1.28;
            }

            #StatusLabel {
                color: #d7dde6;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }

            #MessageLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }

            #LoadingLabel {
                color: #8d95a3;
                font-size: 12px;
                font-weight: 500;
            }

            QPushButton {
                background-color: rgba(17, 18, 21, 255);
                color: #eef2f6;
                border: 1px solid rgba(236, 240, 245, 35);
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                border-color: rgba(236, 240, 245, 68);
            }

            QPushButton:pressed {
                background-color: rgba(26, 28, 34, 255);
            }

            QPushButton:disabled {
                color: rgba(220, 228, 238, 120);
                border-color: rgba(236, 240, 245, 18);
                background-color: rgba(13, 15, 18, 220);
            }
            """
        )

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)

        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(False)
        self._loading_timer.setInterval(self._loading_dot_interval_ms)
        self._loading_timer.timeout.connect(self._advance_loading_frame)

        self.set_retry_enabled(False)
        self.hide()

    @property
    def state(self) -> OverlayState:
        return self._state

    def set_retry_enabled(self, enabled: bool) -> None:
        self._retry_button.setEnabled(enabled)

    def set_telemetry_callback(self, callback: Callable[[str, dict[str, Any]], None] | None) -> None:
        self._telemetry_callback = callback

    def show_analyzing(self, region: CaptureRegion) -> None:
        self._state = OverlayState.ANALYZING
        self._anchor_region = region
        self._status_label.setText("Analyzing capture")
        self._message_label.setText("Preparing your next Socratic prompt...")
        self._loading_label.setText(self._loading_frames[0])
        self._loading_label.show()
        self.set_retry_enabled(False)
        self._auto_hide_timer.stop()
        self._loading_index = 0
        self._loading_timer.start()
        self._render_and_show(region)
        self._emit(
            "overlay_state_analyzing",
            state=self._state.value,
            region=self._region_payload(region),
        )

    def show_prompt_state(
        self,
        prompt: str,
        region: CaptureRegion,
        ttl_ms: int = 20000,
        retry_enabled: bool = True,
    ) -> None:
        self._state = OverlayState.PROMPT
        self._anchor_region = region
        self._status_label.setText("Socratic prompt")
        self._message_label.setText(prompt)
        self._loading_timer.stop()
        self._loading_label.hide()
        self.set_retry_enabled(retry_enabled)
        self._render_and_show(region)
        self._auto_hide_timer.start(max(0, ttl_ms))
        self._emit(
            "overlay_state_prompt",
            state=self._state.value,
            region=self._region_payload(region),
            ttl_ms=max(0, ttl_ms),
        )

    def show_error_state(
        self,
        message: str,
        hint: str,
        region: CaptureRegion,
        retry_enabled: bool = False,
    ) -> None:
        self._state = OverlayState.ERROR
        self._anchor_region = region
        self._status_label.setText("Could not analyze")
        details = message.strip()
        if hint.strip():
            details = f"{details}\n{hint.strip()}"
        self._message_label.setText(details)
        self._loading_timer.stop()
        self._loading_label.hide()
        self.set_retry_enabled(retry_enabled)
        self._auto_hide_timer.stop()
        self._render_and_show(region)
        self._emit(
            "overlay_state_error",
            state=self._state.value,
            region=self._region_payload(region),
            error_message=message.strip(),
            error_hint=hint.strip(),
        )

    def hide_prompt(self, reason: str = "manual") -> None:
        previous_state = self._state.value
        self._state = OverlayState.HIDDEN
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        self.hide()
        self._emit(
            "overlay_hidden",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )

    def _render_and_show(self, region: CaptureRegion) -> None:
        self.adjustSize()
        width = min(self._max_width, max(self._min_width, self.width()))
        self.resize(width, self.height())
        self.move(*self._resolve_position(region))
        self.show()
        self.raise_()

    def _resolve_position(self, region: CaptureRegion) -> tuple[int, int]:
        x = region.x + region.width + 12
        y = region.y

        screen = QGuiApplication.screenAt(QPoint(region.x, region.y)) or QGuiApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            if x + self.width() > geometry.right():
                x = max(geometry.left() + 12, region.x - self.width() - 12)
            if y + self.height() > geometry.bottom():
                y = max(geometry.top() + 12, geometry.bottom() - self.height() - 12)
        return x, y

    def _advance_loading_frame(self) -> None:
        if self._state != OverlayState.ANALYZING:
            self._loading_timer.stop()
            self._loading_label.hide()
            return
        self._loading_index = (self._loading_index + 1) % len(self._loading_frames)
        self._loading_label.setText(self._loading_frames[self._loading_index])

    def _on_auto_hide_timeout(self) -> None:
        self._emit(
            "overlay_auto_hide",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
        )
        self.hide_prompt(reason="auto_hide")

    def _on_retry_clicked(self) -> None:
        self._emit(
            "overlay_retry_clicked",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
        )
        self.retry_requested.emit()

    def _on_dismiss_clicked(self) -> None:
        self._emit(
            "overlay_dismiss_clicked",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
        )
        self.dismiss_requested.emit()

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
