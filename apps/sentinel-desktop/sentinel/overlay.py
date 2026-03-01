from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from PyQt6.QtCore import QEasingCurve, QPoint, QRect, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .types import CaptureRegion
from .ui_theme import qss_font_family_stack


class OverlayState(str, Enum):
    HIDDEN = "hidden"
    ANALYZING = "analyzing"
    THINKING = "thinking"
    PROMPT = "prompt"
    ERROR = "error"


class ComposerLineEdit(QLineEdit):
    focus_intent = pyqtSignal()
    submit_pressed = pyqtSignal()
    escape_pressed = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.focus_intent.emit()
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        self.focus_intent.emit()
        super().focusInEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submit_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class OverlayBubble(QWidget):
    retry_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()
    user_input_submitted = pyqtSignal(str)

    def __init__(
        self,
        min_width: int = 320,
        max_width: int = 520,
        loading_dot_interval_ms: int = 350,
        input_max_chars: int = 280,
        show_input_confirmation: bool = True,
        input_required: bool = True,
        font_family: str | None = None,
        fade_in_ms: int = 220,
        fade_text_stagger_ms: int = 60,
        thinking_min_width: int = 220,
        thinking_max_width: int = 280,
    ) -> None:
        super().__init__()
        self._min_width = max(220, min_width)
        self._max_width = max(self._min_width, max_width)
        self._thinking_min_width = max(160, thinking_min_width)
        self._thinking_max_width = max(self._thinking_min_width, thinking_max_width)
        self._loading_dot_interval_ms = max(120, loading_dot_interval_ms)
        self._input_max_chars = max(40, input_max_chars)
        self._show_input_confirmation = show_input_confirmation
        self._input_required = input_required
        self._font_family = (font_family or "").strip()
        self._fade_in_ms = max(0, int(fade_in_ms))
        self._fade_text_stagger_ms = max(0, int(fade_text_stagger_ms))
        self._fade_enabled = self._fade_in_ms > 1
        self._state: OverlayState = OverlayState.HIDDEN
        self._loading_frames = ["-", "--", "---", "----", "---", "--"]
        self._loading_index = 0
        self._thinking_frames = ["Thinking.", "Thinking..", "Thinking..."]
        self._thinking_index = 0
        self._anchor_region: CaptureRegion | None = None
        self._last_submitted_text = ""
        self._input_mode_enabled = False
        self._thread_id = ""
        self._turn_index = 0
        self._telemetry_callback: Callable[[str, dict[str, Any]], None] | None = None

        self.setObjectName("OverlayRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._apply_focus_mode(False)

        self._card = QFrame(self)
        self._card.setObjectName("ResponseCard")

        self._status_label = QLabel("Sentinel", self._card)
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setWordWrap(False)

        self._message_label = QLabel("", self._card)
        self._message_label.setObjectName("MessageLabel")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._loading_label = QLabel("", self._card)
        self._loading_label.setObjectName("LoadingLabel")
        self._loading_label.setWordWrap(False)
        self._loading_label.hide()

        self._composer = QFrame(self._card)
        self._composer.setObjectName("ComposerPanel")

        self._input_edit = ComposerLineEdit(self._composer)
        self._input_edit.setObjectName("InputEdit")
        self._input_edit.setPlaceholderText("Click here and type your reply...")
        self._input_edit.setMaxLength(self._input_max_chars)
        self._input_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._input_edit.submit_pressed.connect(self._on_send_clicked)
        self._input_edit.focus_intent.connect(self._on_input_focus_intent)
        self._input_edit.escape_pressed.connect(self._on_dismiss_clicked)

        input_palette = self._input_edit.palette()
        input_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(180, 190, 206, 196))
        self._input_edit.setPalette(input_palette)

        composer_layout = QHBoxLayout()
        composer_layout.setContentsMargins(12, 8, 12, 8)
        composer_layout.setSpacing(8)
        composer_layout.addWidget(self._input_edit, stretch=1)
        self._composer.setLayout(composer_layout)

        self._input_feedback_label = QLabel("", self._card)
        self._input_feedback_label.setObjectName("InputFeedbackLabel")
        self._input_feedback_label.setWordWrap(True)
        self._input_feedback_label.hide()

        self._retry_button = QPushButton("Retry", self._card)
        self._retry_button.setObjectName("RetryButton")
        self._retry_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._retry_button.clicked.connect(self._on_retry_clicked)

        self._dismiss_button = QPushButton("Dismiss", self._card)
        self._dismiss_button.setObjectName("DismissButton")
        self._dismiss_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self._retry_button)
        actions_layout.addWidget(self._dismiss_button)

        self._actions_container = QFrame(self._card)
        self._actions_container.setObjectName("ActionsContainer")
        self._actions_container.setLayout(actions_layout)

        self._card_layout = QVBoxLayout()
        self._card_density_default_margins = (16, 14, 16, 14)
        self._card_density_default_spacing = 10
        self._card_density_thinking_margins = (12, 8, 12, 8)
        self._card_density_thinking_spacing = 5
        self._card_layout.setContentsMargins(*self._card_density_default_margins)
        self._card_layout.setSpacing(self._card_density_default_spacing)
        self._card_layout.addWidget(self._status_label)
        self._card_layout.addWidget(self._message_label)
        self._card_layout.addWidget(self._loading_label)
        self._card_layout.addWidget(self._composer)
        self._card_layout.addWidget(self._input_feedback_label)
        self._card_layout.addWidget(self._actions_container)
        self._card.setLayout(self._card_layout)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._card)
        self.setLayout(root_layout)

        font_stack = qss_font_family_stack(self._font_family)
        self.setStyleSheet(
            """
            #OverlayRoot {
                background-color: transparent;
            }

            #ResponseCard {
                background-color: rgba(18, 22, 30, 209);
                border: 1px solid rgba(255, 255, 255, 41);
                border-radius: 22px;
            }

            QLabel {
                color: #eef3fa;
                font-family: __FONT_STACK__;
                font-size: 12px;
                line-height: 1.35;
            }

            #StatusLabel {
                color: rgba(228, 236, 247, 230);
                font-family: __FONT_STACK__;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }

            #MessageLabel {
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }

            #LoadingLabel {
                color: rgba(188, 199, 214, 230);
                font-size: 10px;
                font-weight: 500;
            }

            #ComposerPanel {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 51);
                border-radius: 16px;
            }

            #InputEdit {
                border: none;
                background: transparent;
                color: #f4f8ff;
                font-family: __FONT_STACK__;
                font-size: 12px;
                font-weight: 500;
                padding: 2px 4px;
            }

            #InputEdit:disabled {
                color: rgba(208, 218, 232, 168);
            }

            #InputFeedbackLabel {
                color: rgba(168, 221, 198, 235);
                font-size: 10px;
                font-weight: 500;
            }

            #InputFeedbackLabel[variant="warning"] {
                color: rgba(250, 205, 145, 240);
            }

            QPushButton {
                background-color: rgba(17, 20, 28, 240);
                color: #eef2f6;
                border: 1px solid rgba(255, 255, 255, 46);
                border-radius: 14px;
                padding: 6px 12px;
                font-family: __FONT_STACK__;
                font-size: 10px;
                font-weight: 600;
                min-width: 82px;
            }

            QPushButton:hover {
                border-color: rgba(255, 255, 255, 86);
            }

            QPushButton:pressed {
                background-color: rgba(33, 38, 51, 255);
            }

            QPushButton:disabled {
                color: rgba(220, 228, 238, 132);
                border-color: rgba(255, 255, 255, 24);
                background-color: rgba(12, 15, 20, 204);
            }

            """
            .replace("__FONT_STACK__", font_stack)
        )

        self.setWindowOpacity(1.0)
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.finished.connect(self._on_fade_in_finished)

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)

        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(False)
        self._loading_timer.setInterval(self._loading_dot_interval_ms)
        self._loading_timer.timeout.connect(self._advance_loading_frame)

        self._composer.hide()
        self.set_retry_enabled(False)
        self.hide()

    @property
    def state(self) -> OverlayState:
        return self._state

    @property
    def last_submitted_text(self) -> str:
        return self._last_submitted_text

    def set_retry_enabled(self, enabled: bool) -> None:
        self._retry_button.setEnabled(enabled)

    def set_telemetry_callback(self, callback: Callable[[str, dict[str, Any]], None] | None) -> None:
        self._telemetry_callback = callback

    def show_analyzing_state(
        self,
        region: CaptureRegion,
        status_text: str = "Analyzing capture",
        message: str = "Preparing your next Socratic prompt...",
    ) -> None:
        self._state = OverlayState.ANALYZING
        self._anchor_region = region
        self._set_input_mode(False)
        self._apply_card_density(self._state)
        self._set_status_visible(True)
        self._set_actions_visible(True)
        self._set_composer_visible(False)
        self._clear_feedback()
        self._status_label.setText(status_text)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._message_label.setText(message)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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

    def show_thinking_state(self, region: CaptureRegion, text: str = "Thinking...") -> None:
        self._state = OverlayState.THINKING
        self._anchor_region = region
        self._set_input_mode(False)
        self._apply_card_density(self._state)
        self._set_status_visible(False)
        self._set_actions_visible(False)
        self._set_composer_visible(False)
        self._clear_feedback()
        self._loading_label.hide()
        base = text.strip().rstrip(".") or "Thinking"
        self._thinking_frames = [f"{base}.", f"{base}..", f"{base}..."]
        self._thinking_index = len(self._thinking_frames) - 1
        self._message_label.setText(self._thinking_frames[self._thinking_index])
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._auto_hide_timer.stop()
        self._loading_timer.start()
        self._render_and_show(
            region,
            effective_min_width=self._thinking_min_width,
            effective_max_width=self._thinking_max_width,
        )
        self._emit(
            "overlay_state_thinking",
            state=self._state.value,
            region=self._region_payload(region),
            message=self._thinking_frames[self._thinking_index],
        )

    def show_prompt_input_state(
        self,
        prompt: str,
        region: CaptureRegion,
        thread_id: str,
        turn_index: int,
        ttl_ms: int = 20000,
        retry_enabled: bool = True,
    ) -> None:
        self._state = OverlayState.PROMPT
        self._anchor_region = region
        self._thread_id = thread_id.strip()
        self._turn_index = max(0, int(turn_index))
        self._set_input_mode(False)
        self._apply_card_density(self._state)
        self._set_status_visible(True)
        self._set_actions_visible(True)
        self._set_composer_visible(True)
        self._clear_input()
        self._clear_feedback()
        turn_label = self._turn_index + 1
        self._status_label.setText(f"Socratic prompt  Turn {turn_label}")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._message_label.setText(prompt)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._loading_timer.stop()
        self._loading_label.hide()
        self.set_retry_enabled(retry_enabled)
        self._render_and_show(region)
        if self._input_required:
            self._auto_hide_timer.stop()
        else:
            self._auto_hide_timer.start(max(0, ttl_ms))
        self._emit(
            "overlay_state_prompt",
            state=self._state.value,
            region=self._region_payload(region),
            ttl_ms=max(0, ttl_ms),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
        )
        self._emit(
            "turn_prompt_rendered",
            state=self._state.value,
            region=self._region_payload(region),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
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
        self._set_input_mode(False)
        self._apply_card_density(self._state)
        self._set_status_visible(True)
        self._set_actions_visible(True)
        self._set_composer_visible(False)
        self._clear_feedback()
        self._status_label.setText("Could not analyze")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        details = message.strip()
        if hint.strip():
            details = f"{details}\n{hint.strip()}"
        self._message_label.setText(details)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
        self._stop_fade_animation()
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        self._set_input_mode(False)
        self.setWindowOpacity(1.0)
        self.hide()
        self._emit(
            "overlay_hidden",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )

    def _render_and_show(
        self,
        region: CaptureRegion,
        effective_min_width: int | None = None,
        effective_max_width: int | None = None,
    ) -> None:
        min_width = self._min_width if effective_min_width is None else max(160, int(effective_min_width))
        max_width_default = self._max_width if effective_max_width is None else max(160, int(effective_max_width))
        max_width = max(min_width, max_width_default)
        self.adjustSize()
        width = min(max_width, max(min_width, self.width()))
        height = max(self.height(), self.minimumSizeHint().height())
        self.resize(width, height)
        self.move(*self._resolve_position(region))
        self.show()
        self.raise_()
        self._play_fade_in_animation(self._state)

    def _resolve_position(self, region: CaptureRegion) -> tuple[int, int]:
        margin = 12
        bubble_width = max(1, self.width())
        bubble_height = max(1, self.height())

        screen = self._resolve_active_screen(region)
        if screen is None:
            return region.x + region.width + margin, region.y

        geometry = screen.availableGeometry()
        min_x = geometry.left() + margin
        max_x = geometry.left() + geometry.width() - bubble_width - margin
        min_y = geometry.top() + margin
        max_y = geometry.top() + geometry.height() - bubble_height - margin

        right_candidate_x = region.x + region.width + margin
        left_candidate_x = region.x - bubble_width - margin

        if right_candidate_x <= max_x:
            x = right_candidate_x
        elif left_candidate_x >= min_x:
            x = left_candidate_x
        else:
            x = self._clamp(right_candidate_x, min_x, max_x)

        y = self._clamp(region.y, min_y, max_y)
        return x, y

    def _resolve_active_screen(self, region: CaptureRegion):
        screens = list(QGuiApplication.screens())
        if not screens:
            return QGuiApplication.primaryScreen()

        region_rect = QRect(region.x, region.y, max(1, region.width), max(1, region.height))
        best_screen = None
        best_overlap_area = -1

        for screen in screens:
            intersection = region_rect.intersected(screen.availableGeometry())
            overlap_area = max(0, intersection.width()) * max(0, intersection.height())
            if overlap_area > best_overlap_area:
                best_overlap_area = overlap_area
                best_screen = screen

        if best_screen is not None and best_overlap_area > 0:
            return best_screen

        center = QPoint(
            region.x + max(0, region.width // 2),
            region.y + max(0, region.height // 2),
        )
        return (
            QGuiApplication.screenAt(center)
            or QGuiApplication.screenAt(QPoint(region.x, region.y))
            or QGuiApplication.primaryScreen()
        )

    @staticmethod
    def _clamp(value: int, minimum: int, maximum: int) -> int:
        if maximum < minimum:
            return minimum
        return max(minimum, min(value, maximum))

    def _advance_loading_frame(self) -> None:
        if self._state not in (OverlayState.ANALYZING, OverlayState.THINKING):
            self._loading_timer.stop()
            self._loading_label.hide()
            return
        if self._state == OverlayState.ANALYZING:
            self._loading_index = (self._loading_index + 1) % len(self._loading_frames)
            self._loading_label.setText(self._loading_frames[self._loading_index])
            return
        self._thinking_index = (self._thinking_index + 1) % len(self._thinking_frames)
        self._message_label.setText(self._thinking_frames[self._thinking_index])

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
        self._set_input_mode(False)
        self.dismiss_requested.emit()

    def _on_input_focus_intent(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        if self._input_mode_enabled:
            return
        self._set_input_mode(True)
        self._emit(
            "input_mode_entered",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
        )

    def _on_send_clicked(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        text = self._input_edit.text().strip()
        if self._input_required and not text:
            self._set_feedback(
                "Type a short response before sending.",
                variant="warning",
            )
            self._emit(
                "overlay_input_blocked",
                state=self._state.value,
                region=self._region_payload(self._anchor_region),
                reason="empty_input",
            )
            return

        self._last_submitted_text = text
        if self._show_input_confirmation:
            preview = self._preview_text(text)
            self._set_feedback(
                f"Captured response ({len(text)} chars): {preview}",
                variant="confirmation",
            )
        self._set_input_mode(False)
        self._emit(
            "overlay_send_clicked",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
            char_count=len(text),
            preview=self._preview_text(text, max_len=56),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
        )
        self.user_input_submitted.emit(text)

    def _set_composer_visible(self, visible: bool) -> None:
        self._composer.setVisible(visible)
        self._input_edit.setEnabled(visible)

    def _set_actions_visible(self, visible: bool) -> None:
        self._actions_container.setVisible(visible)

    def _set_status_visible(self, visible: bool) -> None:
        self._status_label.setVisible(visible)

    def _apply_card_density(self, state: OverlayState) -> None:
        if state == OverlayState.THINKING:
            margins = self._card_density_thinking_margins
            spacing = self._card_density_thinking_spacing
        else:
            margins = self._card_density_default_margins
            spacing = self._card_density_default_spacing
        self._card_layout.setContentsMargins(*margins)
        self._card_layout.setSpacing(spacing)

    def _set_input_mode(self, enabled: bool) -> None:
        if self._input_mode_enabled == enabled:
            return
        self._input_mode_enabled = enabled
        self._stop_fade_animation()
        self.setWindowOpacity(1.0)
        self._apply_focus_mode(enabled)
        if enabled:
            self._input_edit.setFocus(Qt.FocusReason.MouseFocusReason)
        else:
            self._input_edit.clearFocus()

    def _apply_focus_mode(self, enabled: bool) -> None:
        # Keep a stable top-level window configuration to avoid hide/show churn.
        # Toggling focus intent only via ShowWithoutActivating + activateWindow is
        # smoother and prevents flicker when the user clicks into the input.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not enabled)
        if enabled and self.isVisible():
            self.activateWindow()

    def _set_feedback(self, message: str, variant: str = "confirmation") -> None:
        self._input_feedback_label.setProperty("variant", variant)
        self._input_feedback_label.setText(message.strip())
        self._input_feedback_label.setVisible(bool(message.strip()))
        self._refresh_styles()

    def _clear_feedback(self) -> None:
        self._input_feedback_label.setProperty("variant", "")
        self._input_feedback_label.clear()
        self._input_feedback_label.hide()
        self._refresh_styles()

    def _clear_input(self) -> None:
        self._input_edit.clear()

    def _preview_text(self, text: str, max_len: int = 72) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_len:
            return compact
        return f"{compact[: max_len - 3]}..."

    def _refresh_styles(self) -> None:
        self.style().unpolish(self._input_feedback_label)
        self.style().polish(self._input_feedback_label)

    def _stop_fade_animation(self) -> None:
        if self._fade_animation.state() != QPropertyAnimation.State.Stopped:
            self._fade_animation.stop()

    def _play_fade_in_animation(self, mode: OverlayState) -> None:
        if not self._fade_enabled:
            self.setWindowOpacity(1.0)
            return
        self._stop_fade_animation()
        self.setWindowOpacity(0.0)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        # Keep the visual rhythm of text staggering by extending total fade time.
        total_duration = self._fade_in_ms + max(0, self._fade_text_stagger_ms)
        self._fade_animation.setDuration(max(1, total_duration))
        self._pending_fade_mode = mode
        self._emit(
            "overlay_fade_in_started",
            state=mode.value,
            region=self._region_payload(self._anchor_region),
            duration_ms=total_duration,
            text_stagger_ms=self._fade_text_stagger_ms,
        )
        self._fade_animation.start()

    def _on_fade_in_finished(self) -> None:
        self.setWindowOpacity(1.0)
        mode = getattr(self, "_pending_fade_mode", self._state)
        self._emit(
            "overlay_fade_in_completed",
            state=mode.value,
            region=self._region_payload(self._anchor_region),
        )

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
