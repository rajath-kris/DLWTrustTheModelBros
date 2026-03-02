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
from .window_effects import apply_blur_behind_for_widget


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
        self._input_required = input_required
        self._font_family = (font_family or "").strip()
        self._fade_in_ms = max(1, int(fade_in_ms))
        self._fade_text_stagger_ms = max(0, int(fade_text_stagger_ms))
        self._fade_enabled = self._fade_in_ms > 1
        self._screen_margin = 12

        self._state: OverlayState = OverlayState.HIDDEN
        self._anchor_region: CaptureRegion | None = None
        self._input_mode_enabled = False
        self._last_submitted_text = ""
        self._thread_id = ""
        self._turn_index = 0
        self._current_topic = "Inference pending"
        self._submit_default_intent = "Continue with the next Socratic step."
        self._telemetry_callback: Callable[[str, dict[str, Any]], None] | None = None
        self._native_blur_attempted = False
        self._native_blur_enabled = False
        self._pending_hide_previous_state = OverlayState.HIDDEN.value
        self._pending_hide_reason = "manual"
        self._animation_mode: str | None = None
        self._pending_animation_state: OverlayState = OverlayState.HIDDEN
        self._placement_anchor_key: tuple[int, int, int, int] | None = None
        self._placement_side: str = "right"
        self._placement_point: QPoint | None = None

        self._loading_frames = ["-", "--", "---", "----", "---", "--"]
        self._loading_index = 0
        self._thinking_frames = ["Thinking.", "Thinking..", "Thinking..."]
        self._thinking_index = 0

        self.setObjectName("OverlayRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._card = QFrame(self)
        self._card.setObjectName("ResponseCard")

        self._top_highlight = QFrame(self._card)
        self._top_highlight.setObjectName("TopHighlight")
        self._top_highlight.setFixedHeight(2)

        self._message_label = QLabel("", self._card)
        self._message_label.setObjectName("MessageLabel")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._loading_label = QLabel("", self._card)
        self._loading_label.setObjectName("LoadingLabel")
        self._loading_label.hide()

        self._prompt_divider = QFrame(self._card)
        self._prompt_divider.setObjectName("PromptDivider")
        self._prompt_divider.setFixedHeight(1)

        self._composer = QFrame(self._card)
        self._composer.setObjectName("ComposerPanel")

        self._input_edit = ComposerLineEdit(self._composer)
        self._input_edit.setObjectName("InputEdit")
        self._input_edit.setPlaceholderText("Type your response...")
        self._input_edit.setMaxLength(self._input_max_chars)
        self._input_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._input_edit.submit_pressed.connect(self._on_submit_clicked)
        self._input_edit.focus_intent.connect(self._on_input_focus_intent)
        self._input_edit.escape_pressed.connect(self._on_dismiss_clicked)

        input_palette = self._input_edit.palette()
        input_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(210, 220, 231, 140))
        self._input_edit.setPalette(input_palette)

        composer_layout = QHBoxLayout()
        composer_layout.setContentsMargins(10, 6, 10, 6)
        composer_layout.setSpacing(8)
        composer_layout.addWidget(self._input_edit, stretch=1)
        self._composer.setLayout(composer_layout)

        self._actions_row = QFrame(self._card)
        self._actions_row.setObjectName("ActionsRow")

        self._retry_button = QPushButton("↻", self._actions_row)
        self._retry_button.setObjectName("RetryButton")
        self._retry_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._retry_button.clicked.connect(self._on_retry_clicked)
        self._retry_button.setToolTip("Retry request")
        self._retry_button.setAccessibleName("Retry")

        self._dismiss_button = QPushButton("×", self._actions_row)
        self._dismiss_button.setObjectName("DismissButton")
        self._dismiss_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)
        self._dismiss_button.setToolTip("Dismiss (Esc)")
        self._dismiss_button.setAccessibleName("Dismiss")

        self._submit_button = QPushButton("→", self._actions_row)
        self._submit_button.setObjectName("SubmitButton")
        self._submit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._submit_button.clicked.connect(self._on_submit_clicked)
        self._submit_button.setToolTip("Submit (Enter)")
        self._submit_button.setAccessibleName("Submit")

        for button in (self._retry_button, self._dismiss_button, self._submit_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(28)
            button.setMinimumWidth(32)
            button.setMaximumWidth(34)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        actions_layout.addWidget(self._retry_button, stretch=0)
        actions_layout.addWidget(self._dismiss_button, stretch=0)
        actions_layout.addWidget(self._submit_button, stretch=0)
        actions_layout.addStretch(1)
        self._actions_row.setLayout(actions_layout)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(8)
        card_layout.addWidget(self._top_highlight)
        card_layout.addWidget(self._message_label)
        card_layout.addWidget(self._loading_label)
        card_layout.addWidget(self._prompt_divider)
        card_layout.addWidget(self._composer)
        card_layout.addWidget(self._actions_row)
        self._card.setLayout(card_layout)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._card)
        self.setLayout(root_layout)

        self._apply_stylesheet()

        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(self._loading_dot_interval_ms)
        self._loading_timer.timeout.connect(self._advance_loading_frame)

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)

        self._opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._opacity_animation.finished.connect(self._on_opacity_animation_finished)

        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        self._loading_label.hide()
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

    # Compatibility no-op: manual drag positioning was removed from the core overlay.
    def reset_manual_position(self) -> None:
        self._placement_anchor_key = None
        self._placement_side = "right"
        self._placement_point = None

    # Compatibility no-op in UI: topic header was removed, topic remains telemetry-only.
    def reset_topic(self) -> None:
        self._current_topic = "Inference pending"

    def show_analyzing_state(
        self,
        region: CaptureRegion,
        status_text: str = "Analyzing capture",
        message: str = "Preparing your next Socratic prompt...",
        topic_label: str | None = None,
    ) -> None:
        self._state = OverlayState.ANALYZING
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        self._message_label.setText(f"{status_text.strip() or 'Analyzing'}\n{message.strip() or ''}".strip())
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._loading_index = 0
        self._loading_label.setText(self._loading_frames[self._loading_index])
        self._loading_label.show()
        self._loading_timer.start()
        self._auto_hide_timer.stop()
        self.set_retry_enabled(False)
        self._render_and_show(region)
        self._emit(
            "overlay_state_analyzing",
            state=self._state.value,
            region=self._region_payload(region),
            topic_label=self._current_topic,
        )

    def show_thinking_state(
        self,
        region: CaptureRegion,
        text: str = "Thinking...",
        topic_label: str | None = None,
    ) -> None:
        self._state = OverlayState.THINKING
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        base = text.strip().rstrip(".") or "Thinking"
        self._thinking_frames = [f"{base}.", f"{base}..", f"{base}..."]
        self._thinking_index = len(self._thinking_frames) - 1
        self._message_label.setText(self._thinking_frames[self._thinking_index])
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setText("Processing")
        self._loading_label.show()
        self._loading_timer.start()
        self._auto_hide_timer.stop()
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
            topic_label=self._current_topic,
        )

    def show_prompt_input_state(
        self,
        prompt: str,
        region: CaptureRegion,
        thread_id: str,
        turn_index: int,
        ttl_ms: int = 20000,
        retry_enabled: bool = True,
        topic_label: str | None = None,
    ) -> None:
        self._state = OverlayState.PROMPT
        self._anchor_region = region
        self._thread_id = thread_id.strip()
        self._turn_index = max(0, int(turn_index))
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_error_mode_visible(False)
        self._set_prompt_mode_visible(True)
        self._clear_input()
        self._message_label.setText(prompt.strip())
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._loading_timer.stop()
        self._loading_label.hide()
        self.set_retry_enabled(retry_enabled)
        self._render_and_show(region)

        if self._input_required:
            self._auto_hide_timer.stop()
        else:
            self._auto_hide_timer.start(max(0, int(ttl_ms)))

        payload_region = self._region_payload(region)
        self._emit(
            "overlay_state_prompt",
            state=self._state.value,
            region=payload_region,
            ttl_ms=max(0, int(ttl_ms)),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
            topic_label=self._current_topic,
        )
        self._emit(
            "turn_prompt_rendered",
            state=self._state.value,
            region=payload_region,
            thread_id=self._thread_id,
            turn_index=self._turn_index,
            topic_label=self._current_topic,
        )

    def show_error_state(
        self,
        message: str,
        hint: str,
        region: CaptureRegion,
        retry_enabled: bool = False,
        topic_label: str | None = None,
    ) -> None:
        self._state = OverlayState.ERROR
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(True)
        details = message.strip()
        if hint.strip():
            details = f"{details}\n{hint.strip()}".strip()
        self._message_label.setText(details or "Could not analyze this capture.")
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
            topic_label=self._current_topic,
        )

    def hide_prompt(self, reason: str = "manual") -> None:
        previous_state = self._state.value
        self._state = OverlayState.HIDDEN
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        self._set_input_mode(False)

        if not self.isVisible():
            self._complete_hide(previous_state=previous_state, reason=reason)
            return

        if reason == "escape":
            if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
                self._opacity_animation.stop()
            self._complete_hide(previous_state=previous_state, reason=reason)
            return

        if self._fade_enabled:
            self._play_hide_animation(previous_state=previous_state, reason=reason)
            return

        self._complete_hide(previous_state=previous_state, reason=reason)

    def _set_prompt_mode_visible(self, visible: bool) -> None:
        self._composer.setVisible(visible)
        self._prompt_divider.setVisible(visible)
        self._submit_button.setVisible(visible)
        self._submit_button.setEnabled(visible)
        self._dismiss_button.setVisible(visible)
        self._dismiss_button.setEnabled(visible)
        self._retry_button.setVisible(False)
        self._actions_row.setVisible(visible)
        self._input_edit.setEnabled(visible)

    def _set_error_mode_visible(self, visible: bool) -> None:
        self._composer.setVisible(False)
        self._prompt_divider.setVisible(False)
        self._submit_button.setVisible(False)
        self._retry_button.setVisible(visible)
        self._retry_button.setEnabled(visible and self._retry_button.isEnabled())
        self._dismiss_button.setVisible(visible)
        self._dismiss_button.setEnabled(visible)
        self._actions_row.setVisible(visible)
        self._input_edit.setEnabled(False)

    def _render_and_show(
        self,
        region: CaptureRegion,
        effective_min_width: int | None = None,
        effective_max_width: int | None = None,
    ) -> None:
        min_width = self._min_width if effective_min_width is None else max(160, int(effective_min_width))
        max_width_default = self._max_width if effective_max_width is None else max(160, int(effective_max_width))
        max_width = max(min_width, max_width_default)

        screen = self._resolve_active_screen(region)
        available_height: int | None = None
        if screen is not None:
            geometry = screen.availableGeometry()
            available_width = max(160, geometry.width() - (self._screen_margin * 2))
            available_height = max(120, geometry.height() - (self._screen_margin * 2))
            min_width = min(min_width, available_width)
            max_width = min(max_width, available_width)

        self._card.setMinimumWidth(min_width)
        self._card.setMaximumWidth(max_width)
        self.adjustSize()

        natural_width = max(1, self.sizeHint().width())
        width = min(max_width, max(min_width, natural_width))
        natural_height = max(self.sizeHint().height(), self.minimumSizeHint().height(), 1)
        height = natural_height if available_height is None else min(natural_height, available_height)

        anchor_key = self._region_anchor_key(region)
        if anchor_key != self._placement_anchor_key:
            self._placement_anchor_key = anchor_key
            self._placement_side = self._preferred_side_for_region(region)
            self._placement_point = None

        if self._placement_point is not None:
            x, y = self._clamp_to_screen(
                self._placement_point.x(),
                self._placement_point.y(),
                region,
                bubble_width=width,
                bubble_height=height,
            )
        else:
            x, y = self._resolve_position(
                region,
                bubble_width=width,
                bubble_height=height,
                preferred_side=self._placement_side,
            )

        self._placement_point = QPoint(x, y)
        self._apply_window_geometry(x=x, y=y, width=width, height=height)

        first_show = not self.isVisible()
        self.show()
        self.raise_()
        self._apply_native_blur_if_needed()
        self._play_show_animation(self._state, first_show=first_show)

    def _resolve_position(
        self,
        region: CaptureRegion,
        bubble_width: int | None = None,
        bubble_height: int | None = None,
        preferred_side: str | None = None,
    ) -> tuple[int, int]:
        margin = self._screen_margin
        bubble_width = max(1, self.width() if bubble_width is None else bubble_width)
        bubble_height = max(1, self.height() if bubble_height is None else bubble_height)

        screen = self._resolve_active_screen(region)
        if screen is None:
            return region.x + region.width + margin, region.y

        geometry = screen.availableGeometry()
        min_x = geometry.left() + margin
        max_x = geometry.left() + geometry.width() - bubble_width - margin
        min_y = geometry.top() + margin
        max_y = geometry.top() + geometry.height() - bubble_height - margin

        anchor_y = self._clamp(region.y, min_y, max_y)
        right_candidate_x = region.x + region.width + margin
        left_candidate_x = region.x - bubble_width - margin
        side = preferred_side if preferred_side in {"left", "right"} else "right"

        if side == "left":
            if left_candidate_x >= min_x:
                return left_candidate_x, anchor_y
            if right_candidate_x <= max_x:
                return right_candidate_x, anchor_y
        else:
            if right_candidate_x <= max_x:
                return right_candidate_x, anchor_y
            if left_candidate_x >= min_x:
                return left_candidate_x, anchor_y

        right_overflow = max(0, right_candidate_x - max_x)
        left_overflow = max(0, min_x - left_candidate_x)
        side_x = self._clamp(right_candidate_x, min_x, max_x)
        if left_overflow < right_overflow:
            side_x = self._clamp(left_candidate_x, min_x, max_x)

        below_y = region.y + region.height + margin
        if min_y <= below_y <= max_y:
            return side_x, below_y
        above_y = region.y - bubble_height - margin
        if min_y <= above_y <= max_y:
            return side_x, above_y
        return side_x, anchor_y

    def _clamp_to_screen(
        self,
        x: int,
        y: int,
        region: CaptureRegion,
        bubble_width: int | None = None,
        bubble_height: int | None = None,
    ) -> tuple[int, int]:
        margin = self._screen_margin
        bubble_width = max(1, self.width() if bubble_width is None else bubble_width)
        bubble_height = max(1, self.height() if bubble_height is None else bubble_height)
        screen = self._resolve_active_screen(region)
        if screen is None:
            return x, y
        geometry = screen.availableGeometry()
        min_x = geometry.left() + margin
        max_x = geometry.left() + geometry.width() - bubble_width - margin
        min_y = geometry.top() + margin
        max_y = geometry.top() + geometry.height() - bubble_height - margin
        return self._clamp(x, min_x, max_x), self._clamp(y, min_y, max_y)

    def _preferred_side_for_region(self, region: CaptureRegion) -> str:
        screen = self._resolve_active_screen(region)
        if screen is None:
            return "right"
        geometry = screen.availableGeometry()
        margin = self._screen_margin
        right_space = (geometry.left() + geometry.width()) - (region.x + region.width + margin)
        left_space = (region.x - margin) - geometry.left()
        return "right" if right_space >= left_space else "left"

    @staticmethod
    def _region_anchor_key(region: CaptureRegion) -> tuple[int, int, int, int]:
        return (region.x, region.y, region.width, region.height)

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
        if self._state == OverlayState.ANALYZING:
            self._loading_index = (self._loading_index + 1) % len(self._loading_frames)
            self._loading_label.setText(self._loading_frames[self._loading_index])
            return

        if self._state == OverlayState.THINKING:
            self._thinking_index = (self._thinking_index + 1) % len(self._thinking_frames)
            self._message_label.setText(self._thinking_frames[self._thinking_index])
            return

        self._loading_timer.stop()
        self._loading_label.hide()

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

    def _on_submit_clicked(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        raw_text = self._input_edit.text().strip()
        payload_text = raw_text or self._submit_default_intent
        self._emit_submission(payload_text, used_default=not bool(raw_text))

    def _on_input_focus_intent(self) -> None:
        if self._state != OverlayState.PROMPT or self._input_mode_enabled:
            return
        self._set_input_mode(True)
        self._emit(
            "input_mode_entered",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
        )

    def _set_input_mode(self, enabled: bool) -> None:
        if self._input_mode_enabled == enabled:
            return
        self._input_mode_enabled = enabled
        self._apply_focus_mode(enabled)
        if enabled:
            self._input_edit.setFocus(Qt.FocusReason.MouseFocusReason)
        else:
            self._input_edit.clearFocus()

    def _apply_focus_mode(self, enabled: bool) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not enabled)
        if enabled and self.isVisible():
            self.activateWindow()

    def _emit_submission(self, payload_text: str, used_default: bool) -> None:
        self._last_submitted_text = payload_text
        self._set_input_mode(False)
        payload_region = self._region_payload(self._anchor_region)
        self._emit(
            "overlay_submit_clicked",
            state=self._state.value,
            region=payload_region,
            char_count=len(payload_text),
            used_default=used_default,
            preview=self._preview_text(payload_text, max_len=56),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
        )
        # Preserve legacy event consumed by journey log queries.
        self._emit(
            "overlay_send_clicked",
            state=self._state.value,
            region=payload_region,
            char_count=len(payload_text),
            preview=self._preview_text(payload_text, max_len=56),
            thread_id=self._thread_id,
            turn_index=self._turn_index,
            source="submit",
            used_default=used_default,
        )
        self.user_input_submitted.emit(payload_text)

    def _clear_input(self) -> None:
        self._input_edit.clear()

    def _preview_text(self, text: str, max_len: int = 72) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_len:
            return compact
        return f"{compact[: max_len - 3]}..."

    def _resolve_topic(self, topic_label: str | None) -> None:
        candidate = ""
        if topic_label is not None:
            cleaned = " ".join(topic_label.strip().split())
            if cleaned.lower().startswith("topic:"):
                cleaned = cleaned[6:].strip()
            candidate = cleaned
        if candidate:
            self._current_topic = candidate

    def _play_show_animation(self, mode: OverlayState, first_show: bool) -> None:
        if not self._fade_enabled:
            self.setWindowOpacity(1.0)
            return

        if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
            self._opacity_animation.stop()

        refresh = not first_show
        current_opacity = float(self.windowOpacity())
        if first_show or current_opacity <= 0.08:
            start_opacity = 0.0
            duration = self._clamp(self._fade_in_ms, 160, 190)
            refresh = False
        else:
            start_opacity = max(0.88, current_opacity)
            duration = self._clamp(int(self._fade_in_ms * 0.72), 120, 150)

        self._animation_mode = "show"
        self._pending_animation_state = mode
        self.setWindowOpacity(start_opacity)
        self._opacity_animation.setStartValue(start_opacity)
        self._opacity_animation.setEndValue(1.0)
        self._opacity_animation.setDuration(duration)
        self._opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._emit(
            "overlay_fade_in_started",
            state=mode.value,
            region=self._region_payload(self._anchor_region),
            duration_ms=duration,
            text_stagger_ms=self._fade_text_stagger_ms,
            refresh=refresh,
        )
        self._opacity_animation.start()

    def _play_hide_animation(self, previous_state: str, reason: str) -> None:
        if not self._fade_enabled:
            self._complete_hide(previous_state=previous_state, reason=reason)
            return

        if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
            self._opacity_animation.stop()

        start_opacity = float(self.windowOpacity())
        if start_opacity <= 0.0:
            start_opacity = 1.0
        duration = self._clamp(int(self._fade_in_ms * 0.7), 110, 140)

        self._animation_mode = "hide"
        self._pending_hide_previous_state = previous_state
        self._pending_hide_reason = reason
        self._opacity_animation.setStartValue(start_opacity)
        self._opacity_animation.setEndValue(0.0)
        self._opacity_animation.setDuration(duration)
        self._opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._emit(
            "overlay_fade_out_started",
            state=previous_state,
            region=self._region_payload(self._anchor_region),
            duration_ms=duration,
            reason=reason,
        )
        self._opacity_animation.start()

    def _on_opacity_animation_finished(self) -> None:
        if self._animation_mode == "hide":
            self._complete_hide(
                previous_state=self._pending_hide_previous_state,
                reason=self._pending_hide_reason,
            )
            return

        if self._animation_mode == "show":
            self.setWindowOpacity(1.0)
            self._emit(
                "overlay_fade_in_completed",
                state=self._pending_animation_state.value,
                region=self._region_payload(self._anchor_region),
            )
        self._animation_mode = None

    def _complete_hide(self, previous_state: str, reason: str) -> None:
        self._animation_mode = None
        self.setWindowOpacity(1.0)
        self.hide()
        self._emit(
            "overlay_hidden",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )

    def _apply_native_blur_if_needed(self) -> None:
        if self._native_blur_attempted:
            return
        if not self.isVisible() or self.width() <= 1 or self.height() <= 1:
            return
        self._native_blur_attempted = True
        if self.windowHandle() is None:
            self.winId()
        self._native_blur_enabled = apply_blur_behind_for_widget(self, blur_strength=14)
        self._emit(
            "overlay_native_blur_result",
            state=self._state.value,
            enabled=self._native_blur_enabled,
        )

    def _apply_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        target_width = max(1, int(width))
        target_height = max(1, int(height))
        target_x = int(x)
        target_y = int(y)
        if self.width() != target_width or self.height() != target_height:
            self.resize(target_width, target_height)
        if self.x() != target_x or self.y() != target_y:
            self.move(target_x, target_y)

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

    def _apply_stylesheet(self) -> None:
        font_stack = qss_font_family_stack(self._font_family)
        stylesheet = """
            QWidget#OverlayRoot {
                background: transparent;
            }

            QFrame#ResponseCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(54, 74, 98, 112),
                    stop: 0.40 rgba(34, 46, 64, 96),
                    stop: 1 rgba(18, 25, 38, 82)
                );
                border: 1px solid rgba(242, 248, 255, 72);
                border-radius: 16px;
            }

            QFrame#TopHighlight {
                border: none;
                border-radius: 1px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(186, 212, 242, 28),
                    stop: 0.5 rgba(214, 234, 255, 146),
                    stop: 1 rgba(186, 212, 242, 28)
                );
            }

            QLabel#MessageLabel {
                background: transparent;
                border: none;
                color: rgba(239, 245, 252, 226);
                font-family: __FONT_STACK__;
                font-size: 14px;
                font-weight: 500;
                selection-background-color: rgba(116, 154, 194, 120);
                selection-color: rgba(247, 251, 255, 250);
            }

            QLabel#LoadingLabel {
                background: transparent;
                border: none;
                color: rgba(196, 208, 223, 178);
                font-family: __FONT_STACK__;
                font-size: 11px;
                font-weight: 450;
                letter-spacing: 0.3px;
            }

            QFrame#PromptDivider {
                border: none;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(248, 252, 255, 14),
                    stop: 0.5 rgba(248, 252, 255, 64),
                    stop: 1 rgba(248, 252, 255, 14)
                );
                min-height: 1px;
                max-height: 1px;
            }

            QFrame#ComposerPanel {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(14, 22, 34, 118),
                    stop: 1 rgba(10, 16, 26, 104)
                );
                border: 1px solid rgba(244, 248, 255, 60);
                border-radius: 11px;
            }

            QLineEdit#InputEdit {
                background: transparent;
                border: none;
                color: rgba(244, 248, 255, 234);
                font-family: __FONT_STACK__;
                font-size: 13px;
                font-weight: 450;
                padding: 4px 2px;
                selection-background-color: rgba(120, 160, 200, 122);
                selection-color: rgba(248, 251, 255, 250);
            }

            QLineEdit#InputEdit:focus {
                border: none;
            }

            QFrame#ActionsRow {
                background: transparent;
                border: none;
            }

            QPushButton#SubmitButton,
            QPushButton#DismissButton,
            QPushButton#RetryButton {
                border-radius: 9px;
                padding: 0px;
                font-family: __FONT_STACK__;
                font-size: 12px;
                font-weight: 600;
                min-height: 28px;
                max-height: 28px;
                min-width: 32px;
                max-width: 34px;
            }

            QPushButton#SubmitButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(112, 172, 224, 150),
                    stop: 1 rgba(95, 159, 216, 134)
                );
                color: rgba(244, 249, 255, 238);
                border: 1px solid rgba(206, 230, 255, 88);
            }

            QPushButton#SubmitButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(112, 172, 224, 160),
                    stop: 1 rgba(95, 159, 216, 144)
                );
            }

            QPushButton#SubmitButton:pressed {
                background: rgba(95, 159, 216, 158);
            }

            QPushButton#DismissButton,
            QPushButton#RetryButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(248, 251, 255, 56),
                    stop: 1 rgba(232, 240, 250, 36)
                );
                color: rgba(234, 241, 250, 232);
                border: 1px solid rgba(246, 249, 253, 62);
            }

            QPushButton#DismissButton:hover,
            QPushButton#RetryButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(248, 251, 255, 64),
                    stop: 1 rgba(232, 240, 250, 42)
                );
            }

            QPushButton#DismissButton:pressed,
            QPushButton#RetryButton:pressed {
                background: rgba(232, 240, 250, 38);
            }

            QPushButton#SubmitButton:disabled,
            QPushButton#DismissButton:disabled,
            QPushButton#RetryButton:disabled {
                color: rgba(176, 188, 202, 140);
                background-color: rgba(246, 249, 253, 14);
                border-color: rgba(246, 249, 253, 18);
            }
        """.replace("__FONT_STACK__", font_stack)
        self.setStyleSheet(stylesheet)
