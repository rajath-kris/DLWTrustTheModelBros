from __future__ import annotations

import html
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from PyQt6.QtCore import QEasingCurve, QPoint, QRect, QPropertyAnimation, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QPainterPath, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .types import CaptureRegion
from .ui_theme import qss_font_family_stack


class OverlayState(str, Enum):
    LAUNCHER = "launcher"
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


@dataclass
class InteractionPage:
    turn_index: int
    prompt_text: str
    show_capture_preview: bool
    user_response_text: str
    source_material_url: str
    source_material_label: str


class OverlayBubble(QWidget):
    launcher_requested = pyqtSignal()
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
        thinking_min_width: int = 188,
        thinking_max_width: int = 240,
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
        self._launcher_margin = 16
        self._launcher_size = 46
        self._launcher_vertical_anchor_ratio = 0.33
        self._prompt_max_height_ratio = 0.58

        self._state: OverlayState = OverlayState.LAUNCHER
        self._anchor_region: CaptureRegion | None = None
        self._input_mode_enabled = False
        self._launcher_temporarily_hidden = False
        self._last_submitted_text = ""
        self._thread_id = ""
        self._turn_index = 0
        self._current_topic = "Inference pending"
        self._submit_default_intent = "Continue with the next Socratic step."
        self._telemetry_callback: Callable[[str, dict[str, Any]], None] | None = None
        self._pending_hide_previous_state = OverlayState.HIDDEN.value
        self._pending_hide_reason = "manual"
        self._animation_mode: str | None = None
        self._pending_animation_state: OverlayState = OverlayState.HIDDEN
        self._placement_anchor_key: tuple[int, int, int, int] | None = None
        self._placement_side: str = "right"
        self._placement_point: QPoint | None = None
        self._geometry_anim_ms = 160
        self._geometry_animation_mode: str | None = None
        self._pending_collapse_reason = "manual"
        self._pending_collapse_previous_state = OverlayState.HIDDEN.value
        self._interaction_pages: list[InteractionPage] = []
        self._selected_page_index = -1
        self._visible_page_indices: list[int] = []
        self._max_visible_page_dots = 7
        self._prompt_text_max_chars = 230
        self._prompt_message_min_height = 72
        self._interaction_capture_pixmap: QPixmap | None = None
        self._capture_preview_height = 96
        self._capture_preview_radius = 11
        self._prompt_locked_height: int | None = None
        self._composer_input_height = 24
        self._composer_panel_height = 34
        self._last_unavailable_source_key: tuple[str, int] | None = None

        self._loading_frames = ["-", "--", "---", "----", "---", "--"]
        self._loading_index = 0
        self._thinking_text = "Agent is Thinking"
        self._thinking_shimmer_step = 0
        self._thinking_shimmer_width = 5
        self._thinking_shimmer_interval_ms = 45

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

        self._launcher_button = QPushButton("", self)
        self._launcher_button.setObjectName("LauncherButton")
        self._launcher_button.setToolTip("Capture (Alt+S)")
        self._launcher_button.setAccessibleName("Capture launcher")
        self._launcher_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._launcher_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launcher_button.setFixedSize(self._launcher_size, self._launcher_size)
        self._launcher_button.clicked.connect(self._on_launcher_clicked)

        self._dismiss_button = QPushButton("×", self._card)
        self._dismiss_button.setObjectName("DismissButton")
        self._dismiss_button.setToolTip("Dismiss (Esc)")
        self._dismiss_button.setAccessibleName("Dismiss")
        self._dismiss_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_button.setFixedSize(20, 20)
        self._dismiss_button.clicked.connect(self._on_dismiss_clicked)

        self._message_label = QLabel("", self._card)
        self._message_label.setObjectName("MessageLabel")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Let layout width drive wrapping so long text does not force card expansion.
        self._message_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._message_label.setMinimumWidth(0)

        self._capture_preview_label = QLabel("", self._card)
        self._capture_preview_label.setObjectName("CapturePreview")
        self._capture_preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._capture_preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._capture_preview_label.setFixedHeight(self._capture_preview_height)
        self._capture_preview_label.hide()

        self._message_content = QFrame(self._card)
        self._message_content.setObjectName("MessageContent")

        self._source_button_row = QFrame(self._message_content)
        self._source_button_row.setObjectName("SourceButtonRow")
        self._source_button_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._source_button = QPushButton("Open Material", self._source_button_row)
        self._source_button.setObjectName("SourcePill")
        self._source_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._source_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._source_button.setVisible(False)
        self._source_button.clicked.connect(self._on_source_button_clicked)

        source_row_layout = QHBoxLayout()
        source_row_layout.setContentsMargins(0, 0, 0, 0)
        source_row_layout.setSpacing(0)
        source_row_layout.addStretch(1)
        source_row_layout.addWidget(self._source_button, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)
        self._source_button_row.setLayout(source_row_layout)

        message_content_layout = QVBoxLayout()
        message_content_layout.setContentsMargins(0, 0, 0, 0)
        message_content_layout.setSpacing(5)
        message_content_layout.addWidget(self._capture_preview_label)
        message_content_layout.addWidget(self._message_label)
        message_content_layout.addWidget(self._source_button_row)
        self._message_content.setLayout(message_content_layout)

        self._message_row = QFrame(self._card)
        self._message_row.setObjectName("MessageRow")
        message_layout = QHBoxLayout()
        message_layout.setContentsMargins(0, 0, 0, 0)
        message_layout.setSpacing(8)
        message_layout.addWidget(self._dismiss_button, stretch=0, alignment=Qt.AlignmentFlag.AlignTop)
        message_layout.addWidget(self._message_content, stretch=1)
        self._message_row.setLayout(message_layout)

        self._page_rail = QFrame(self._card)
        self._page_rail.setObjectName("PageRail")
        self._page_rail.setFixedWidth(20)
        page_rail_layout = QVBoxLayout()
        page_rail_layout.setContentsMargins(0, 1, 0, 1)
        page_rail_layout.setSpacing(4)
        page_rail_layout.addStretch(1)
        self._page_rail.setLayout(page_rail_layout)

        self._message_shell = QFrame(self._card)
        self._message_shell.setObjectName("MessageShell")
        self._message_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        message_shell_layout = QHBoxLayout()
        message_shell_layout.setContentsMargins(0, 0, 0, 0)
        message_shell_layout.setSpacing(6)
        message_shell_layout.addWidget(self._message_row, stretch=1)
        message_shell_layout.addWidget(self._page_rail, stretch=0, alignment=Qt.AlignmentFlag.AlignTop)
        self._message_shell.setLayout(message_shell_layout)

        self._loading_label = QLabel("", self._card)
        self._loading_label.setObjectName("LoadingLabel")
        self._loading_label.hide()

        self._prompt_divider = QFrame(self._card)
        self._prompt_divider.setObjectName("PromptDivider")
        self._prompt_divider.setFixedHeight(1)

        self._composer = QFrame(self._card)
        self._composer.setObjectName("ComposerPanel")
        self._composer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._composer.setFixedHeight(self._composer_panel_height)

        self._input_edit = ComposerLineEdit(self._composer)
        self._input_edit.setObjectName("InputEdit")
        self._input_edit.setPlaceholderText("Type your response...")
        self._input_edit.setMaxLength(self._input_max_chars)
        self._input_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._input_edit.setMinimumWidth(0)
        self._input_edit.setFixedHeight(self._composer_input_height)
        self._input_edit.submit_pressed.connect(self._on_submit_clicked)
        self._input_edit.focus_intent.connect(self._on_input_focus_intent)
        self._input_edit.escape_pressed.connect(self._on_dismiss_clicked)

        self._submit_button = QPushButton("\u2192", self._composer)
        self._submit_button.setObjectName("SubmitButton")
        self._submit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._submit_button.clicked.connect(self._on_submit_clicked)
        self._submit_button.setToolTip("Submit (Enter)")
        self._submit_button.setAccessibleName("Submit")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_button.setFixedSize(self._composer_input_height, self._composer_input_height)

        input_palette = self._input_edit.palette()
        input_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(214, 225, 238, 170))
        self._input_edit.setPalette(input_palette)

        composer_layout = QHBoxLayout()
        composer_layout.setContentsMargins(8, 5, 8, 5)
        composer_layout.setSpacing(6)
        composer_layout.addWidget(self._input_edit, stretch=1)
        composer_layout.addWidget(self._submit_button, stretch=0)
        self._composer.setLayout(composer_layout)

        self._actions_row = QFrame(self._card)
        self._actions_row.setObjectName("ActionsRow")

        self._retry_button = QPushButton("\u21BB", self._actions_row)
        self._retry_button.setObjectName("RetryButton")
        self._retry_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._retry_button.clicked.connect(self._on_retry_clicked)
        self._retry_button.setToolTip("Retry request")
        self._retry_button.setAccessibleName("Retry")

        self._retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_button.setFixedHeight(28)
        self._retry_button.setMinimumWidth(32)
        self._retry_button.setMaximumWidth(34)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        actions_layout.addWidget(self._retry_button, stretch=0)
        actions_layout.addStretch(1)
        self._actions_row.setLayout(actions_layout)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(6)
        card_layout.addWidget(self._top_highlight)
        card_layout.addWidget(self._message_shell)
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
        self._geometry_animation = QPropertyAnimation(self, b"geometry", self)
        self._geometry_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._geometry_animation.setDuration(self._geometry_anim_ms)
        self._geometry_animation.finished.connect(self._on_geometry_animation_finished)

        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        self._loading_label.hide()
        self._refresh_page_dots()
        self._card.hide()
        self._launcher_button.show()
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

    def begin_interaction(self) -> None:
        self._interaction_pages.clear()
        self._selected_page_index = -1
        self._visible_page_indices.clear()
        self._interaction_capture_pixmap = None
        self._prompt_locked_height = None
        self._last_unavailable_source_key = None
        self._source_button.setVisible(False)
        self._source_button_row.setVisible(False)
        self._reset_capture_preview()
        self._refresh_page_dots()

    def set_interaction_capture_image(self, capture_png_bytes: bytes | None) -> None:
        pixmap: QPixmap | None = None
        if capture_png_bytes:
            loaded = QPixmap()
            if loaded.loadFromData(capture_png_bytes, "PNG") and not loaded.isNull():
                pixmap = loaded
        self._interaction_capture_pixmap = pixmap
        if self._state == OverlayState.PROMPT:
            self._render_selected_prompt_page()

    def show_launcher(self, animated: bool = False) -> None:
        previous_state = self._state.value
        self._state = OverlayState.LAUNCHER
        self._anchor_region = None
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)

        if self._launcher_temporarily_hidden:
            self.hide()
            return

        if animated and self.isVisible() and self._card.isVisible():
            self._collapse_to_launcher(reason="manual", previous_state=previous_state)
            return

        if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
            self._geometry_animation.stop()
        self._card.hide()
        self._launcher_button.show()
        launcher_rect = self._launcher_rect()
        self.setGeometry(launcher_rect)
        self.show()
        self.raise_()
        self.setWindowOpacity(1.0)
        self._emit(
            "overlay_launcher_shown",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
        )

    def set_launcher_temporarily_hidden(self, hidden: bool) -> None:
        flag = bool(hidden)
        if self._launcher_temporarily_hidden == flag:
            return
        self._launcher_temporarily_hidden = flag

        if flag:
            if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
                self._geometry_animation.stop()
            self.hide()
            self._emit("overlay_launcher_visibility", hidden=True)
            return

        self._emit("overlay_launcher_visibility", hidden=False)
        if self._state == OverlayState.LAUNCHER:
            self.show_launcher(animated=False)
        elif not self.isVisible():
            self.show()
            self.raise_()

    def show_analyzing_state(
        self,
        region: CaptureRegion,
        status_text: str = "Analyzing capture",
        message: str = "Preparing guidance...",
        topic_label: str | None = None,
    ) -> None:
        self._launcher_temporarily_hidden = False
        self._state = OverlayState.ANALYZING
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        self._message_label.setTextFormat(Qt.TextFormat.PlainText)
        self._message_label.setText(f"{status_text.strip() or 'Analyzing'}\n{message.strip() or ''}".strip())
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._loading_index = 0
        self._loading_label.setText(self._loading_frames[self._loading_index])
        self._loading_label.show()
        self._loading_timer.setInterval(self._loading_dot_interval_ms)
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
        _ = text  # Keep argument for compatibility; visual copy is fixed for thinking state.
        self._launcher_temporarily_hidden = False
        self._state = OverlayState.THINKING
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(False)
        self._thinking_shimmer_step = 0
        self._message_label.setTextFormat(Qt.TextFormat.RichText)
        self._message_label.setText(self._build_thinking_shimmer_markup(self._thinking_shimmer_step))
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.hide()
        self._loading_timer.setInterval(self._thinking_shimmer_interval_ms)
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
            message=self._thinking_text,
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
        source_material_url: str | None = None,
        source_material_label: str | None = None,
    ) -> None:
        previous_state = self._state
        self._launcher_temporarily_hidden = False
        self._state = OverlayState.PROMPT
        self._anchor_region = region
        self._thread_id = thread_id.strip()
        self._turn_index = max(0, int(turn_index))
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_error_mode_visible(False)
        self._set_prompt_mode_visible(True)
        self._clear_input()
        self._message_label.setTextFormat(Qt.TextFormat.PlainText)
        normalized_prompt = " ".join(prompt.strip().split()) or "What concept feels least clear in this capture?"
        page_idx = self._upsert_interaction_page(
            prompt_text=normalized_prompt,
            turn_index=self._turn_index,
            source_material_url=source_material_url,
            source_material_label=source_material_label,
        )
        self._selected_page_index = page_idx
        self._refresh_page_dots(selected_source="auto")

        from_thinking = (
            previous_state == OverlayState.THINKING
            and self.isVisible()
            and self._card.isVisible()
        )
        if from_thinking:
            # Use the same animated geometry transition path used for page switches.
            self._render_selected_prompt_page()
            self._sync_prompt_input_availability()
            self.set_retry_enabled(retry_enabled)
            self._loading_timer.stop()
            self._loading_label.hide()
            self._reflow_prompt_card_geometry()
        else:
            # Paint a lightweight prompt first so shimmer->prompt handoff stays responsive.
            self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._message_label.setText(self._truncate_for_page(normalized_prompt, self._prompt_text_max_chars))
            self._reset_capture_preview()
            self._sync_prompt_input_availability()
            self.set_retry_enabled(retry_enabled)
            self._render_and_show(region)
            self._loading_label.hide()
            QTimer.singleShot(0, self._render_prompt_page_and_reflow)

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
        self._launcher_temporarily_hidden = False
        self._state = OverlayState.ERROR
        self._anchor_region = region
        self._resolve_topic(topic_label)
        self._set_input_mode(False)
        self._set_prompt_mode_visible(False)
        self._set_error_mode_visible(True)
        self._message_label.setTextFormat(Qt.TextFormat.PlainText)
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
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        self._set_input_mode(False)
        if reason in {"shutdown", "teardown"}:
            self._state = OverlayState.HIDDEN
            if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
                self._geometry_animation.stop()
            if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
                self._opacity_animation.stop()
            self._card.hide()
            self._launcher_button.hide()
            self.hide()
            self._emit(
                "overlay_hidden",
                state=self._state.value,
                previous_state=previous_state,
                reason=reason,
                region=self._region_payload(self._anchor_region),
            )
            return

        self._collapse_to_launcher(reason=reason, previous_state=previous_state)

    def _set_prompt_mode_visible(self, visible: bool) -> None:
        self._composer.setVisible(visible)
        self._prompt_divider.setVisible(visible)
        self._submit_button.setVisible(visible)
        self._submit_button.setEnabled(visible)
        self._retry_button.setVisible(False)
        self._actions_row.setVisible(False)
        self._input_edit.setEnabled(visible)
        self._dismiss_button.setVisible(visible)
        self._message_label.setMinimumHeight(self._prompt_message_min_height if visible else 0)
        if visible:
            self._refresh_page_dots()
        else:
            self._reset_capture_preview()
            self._page_rail.hide()
            self._source_button.setVisible(False)
            self._source_button.setEnabled(False)
            self._source_button_row.setVisible(False)

    def _set_error_mode_visible(self, visible: bool) -> None:
        self._composer.setVisible(False)
        self._prompt_divider.setVisible(False)
        self._source_button.setVisible(False)
        self._source_button_row.setVisible(False)
        self._submit_button.setVisible(False)
        self._retry_button.setVisible(visible)
        self._retry_button.setEnabled(visible and self._retry_button.isEnabled())
        self._actions_row.setVisible(visible)
        self._input_edit.setEnabled(False)
        self._dismiss_button.setVisible(visible)
        self._reset_capture_preview()
        self._page_rail.hide()

    def _render_and_show(
        self,
        region: CaptureRegion,
        effective_min_width: int | None = None,
        effective_max_width: int | None = None,
    ) -> None:
        min_width = self._min_width if effective_min_width is None else max(160, int(effective_min_width))
        max_width_default = self._max_width if effective_max_width is None else max(160, int(effective_max_width))
        max_width = max(min_width, max_width_default)

        geometry = self._primary_available_geometry()
        available_height = max(120, geometry.height() - (self._launcher_margin * 2))
        available_width = max(160, geometry.width() - (self._launcher_margin * 2))
        min_width = min(min_width, available_width)
        max_width = min(max_width, available_width)

        self._card.setMinimumWidth(min_width)
        self._card.setMaximumWidth(max_width)
        card_layout = self._card.layout()
        if card_layout is not None:
            card_layout.activate()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.activate()

        width, height = self._measure_card_target_size(
            min_width=min_width,
            max_width=max_width,
            available_height=available_height,
        )
        if self._state == OverlayState.PROMPT:
            height = self._resolve_prompt_height(height, available_height)
        origin = self._launcher_origin(bubble_height=height)
        target_rect = QRect(origin.x(), origin.y(), width, height)

        collapsed = self._launcher_button.isVisible() and not self._card.isVisible()
        self._card.show()
        self._launcher_button.hide()
        first_show = not self.isVisible()

        if collapsed or first_show:
            self._expand_from_launcher_to_card(target_rect)
        else:
            self._apply_window_geometry(
                x=target_rect.x(),
                y=target_rect.y(),
                width=target_rect.width(),
                height=target_rect.height(),
            )
            self.show()
            self.raise_()
        self._play_show_animation(self._state, first_show=first_show)

    def _primary_available_geometry(self) -> QRect:
        primary = QGuiApplication.primaryScreen()
        if primary is not None:
            return primary.availableGeometry()
        screens = list(QGuiApplication.screens())
        if screens:
            return screens[0].availableGeometry()
        return QRect(0, 0, 1280, 720)

    def _launcher_origin(self, bubble_height: int | None = None) -> QPoint:
        geometry = self._primary_available_geometry()
        target_height = self._launcher_size if bubble_height is None else max(1, int(bubble_height))
        min_y = geometry.top() + self._launcher_margin
        max_y = geometry.top() + geometry.height() - target_height - self._launcher_margin
        anchor_y = geometry.top() + int(geometry.height() * self._launcher_vertical_anchor_ratio)
        y = self._clamp(anchor_y, min_y, max_y)
        return QPoint(
            geometry.left() + self._launcher_margin,
            y,
        )

    def _launcher_rect(self) -> QRect:
        origin = self._launcher_origin(bubble_height=self._launcher_size)
        return QRect(origin.x(), origin.y(), self._launcher_size, self._launcher_size)

    def _upsert_interaction_page(
        self,
        prompt_text: str,
        turn_index: int,
        source_material_url: str | None = None,
        source_material_label: str | None = None,
    ) -> int:
        normalized_prompt = " ".join(prompt_text.split()) or "What concept feels least clear in this capture?"
        page_turn = max(0, int(turn_index))
        show_capture_preview = page_turn == 0
        normalized_source_url = " ".join((source_material_url or "").split())
        normalized_source_label = " ".join((source_material_label or "").split())
        existing_index: int | None = None
        for idx, page in enumerate(self._interaction_pages):
            if page.turn_index == page_turn:
                existing_index = idx
                break

        if existing_index is None:
            page = InteractionPage(
                turn_index=page_turn,
                prompt_text=normalized_prompt,
                show_capture_preview=show_capture_preview,
                user_response_text="",
                source_material_url=normalized_source_url,
                source_material_label=normalized_source_label,
            )
            self._interaction_pages.append(page)
            self._interaction_pages.sort(key=lambda item: item.turn_index)
            resolved_index = self._interaction_pages.index(page)
            self._emit(
                "overlay_page_added",
                state=self._state.value,
                page_index=resolved_index,
                page_count=len(self._interaction_pages),
                thread_id=self._thread_id,
                turn_index=page.turn_index,
            )
        else:
            page = self._interaction_pages[existing_index]
            page.prompt_text = normalized_prompt
            page.show_capture_preview = show_capture_preview
            page.source_material_url = normalized_source_url
            page.source_material_label = normalized_source_label
            resolved_index = existing_index

        return resolved_index

    def _current_turn_page_index(self) -> int:
        for idx, page in enumerate(self._interaction_pages):
            if page.turn_index == self._turn_index:
                return idx
        return -1

    def _is_selected_page_current_turn(self) -> bool:
        current_idx = self._current_turn_page_index()
        return current_idx >= 0 and self._selected_page_index == current_idx

    def _sync_prompt_input_availability(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        can_respond = self._is_selected_page_current_turn()
        self._input_edit.setEnabled(can_respond)
        self._submit_button.setEnabled(can_respond)
        self._input_edit.setPlaceholderText(
            "Type your response..." if can_respond else "Switch to current turn to respond..."
        )
        if not can_respond:
            self._set_input_mode(False)

    def _render_selected_prompt_page(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        if not self._interaction_pages:
            self._message_label.setText("")
            self._source_button.setVisible(False)
            self._source_button_row.setVisible(False)
            self._source_button.setEnabled(False)
            return
        selected = self._selected_page_index
        if selected < 0 or selected >= len(self._interaction_pages):
            selected = len(self._interaction_pages) - 1
            self._selected_page_index = selected
        page = self._interaction_pages[selected]
        prompt_text = self._truncate_for_page(page.prompt_text, self._prompt_text_max_chars)
        lines = [prompt_text]
        self._reset_capture_preview()
        if page.show_capture_preview and self._interaction_capture_pixmap is not None:
            content_width = self._message_content.width()
            if content_width <= 0:
                content_width = max(180, self._card.width() - 82)
            preview_width = max(160, content_width - 2)
            rounded = self._rounded_capture_preview(
                source=self._interaction_capture_pixmap,
                target_w=preview_width,
                target_h=self._capture_preview_height,
                radius=self._capture_preview_radius,
            )
            self._capture_preview_label.setPixmap(rounded)
            self._capture_preview_label.setMinimumWidth(rounded.width())
            self._capture_preview_label.setMaximumWidth(rounded.width())
            self._capture_preview_label.setFixedHeight(rounded.height())
            self._capture_preview_label.show()
        if page.user_response_text and not self._is_selected_page_current_turn():
            lines.extend(["", f"You: {page.user_response_text}"])
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._message_label.setText("\n".join(lines))
        self._apply_source_button_for_page(page)

    def _apply_source_button_for_page(self, page: InteractionPage) -> None:
        url = " ".join((page.source_material_url or "").split())
        label = " ".join((page.source_material_label or "").split())
        if url:
            self._source_button_row.setVisible(True)
            self._source_button.setVisible(True)
            self._source_button.setEnabled(True)
            self._source_button.setText("Open Material")
            tooltip = f"Open {label}" if label else "Open grounded source material"
            self._source_button.setToolTip(tooltip)
            return

        self._source_button_row.setVisible(False)
        self._source_button.setVisible(False)
        self._source_button.setEnabled(False)
        page_key = (self._thread_id, page.turn_index)
        if self._last_unavailable_source_key != page_key:
            self._last_unavailable_source_key = page_key
            self._emit(
                "overlay_source_unavailable",
                state=self._state.value,
                thread_id=self._thread_id,
                turn_index=page.turn_index,
            )

    def _visible_page_window(self) -> list[int]:
        total = len(self._interaction_pages)
        if total <= 0:
            return []
        if total <= self._max_visible_page_dots:
            return list(range(total))
        selected = self._selected_page_index
        if selected < 0 or selected >= total:
            selected = total - 1
        half = self._max_visible_page_dots // 2
        start = selected - half
        end = start + self._max_visible_page_dots
        if start < 0:
            start = 0
            end = self._max_visible_page_dots
        if end > total:
            end = total
            start = end - self._max_visible_page_dots
        return list(range(start, end))

    def _refresh_page_dots(self, selected_source: str | None = None) -> None:
        layout = self._page_rail.layout()
        if layout is None:
            return
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._visible_page_indices = self._visible_page_window()
        in_prompt = self._state == OverlayState.PROMPT
        self._page_rail.setVisible(in_prompt and bool(self._visible_page_indices))
        if not in_prompt or not self._visible_page_indices:
            return

        for page_idx in self._visible_page_indices:
            page = self._interaction_pages[page_idx]
            dot = QPushButton("", self._page_rail)
            dot.setObjectName("PageDot")
            dot.setCheckable(True)
            dot.setChecked(page_idx == self._selected_page_index)
            dot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.setFixedSize(10, 10)
            dot.setToolTip(f"Turn {page.turn_index + 1}")
            dot.clicked.connect(lambda _checked=False, idx=page_idx: self._on_page_dot_clicked(idx))
            layout.insertWidget(layout.count() - 1, dot, alignment=Qt.AlignmentFlag.AlignHCenter)

        if selected_source and 0 <= self._selected_page_index < len(self._interaction_pages):
            page = self._interaction_pages[self._selected_page_index]
            self._emit(
                "overlay_page_selected",
                state=self._state.value,
                page_index=self._selected_page_index,
                page_count=len(self._interaction_pages),
                thread_id=self._thread_id,
                turn_index=page.turn_index,
                source=selected_source,
            )

    def _on_page_dot_clicked(self, page_index: int) -> None:
        if self._state != OverlayState.PROMPT:
            return
        if page_index < 0 or page_index >= len(self._interaction_pages):
            return
        self._selected_page_index = page_index
        self._refresh_page_dots(selected_source="dot_click")
        self._render_selected_prompt_page()
        self._reflow_prompt_card_geometry()
        self._sync_prompt_input_availability()

    def _on_source_button_clicked(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        if self._selected_page_index < 0 or self._selected_page_index >= len(self._interaction_pages):
            return
        page = self._interaction_pages[self._selected_page_index]
        source_url = " ".join((page.source_material_url or "").split())
        if not source_url:
            self._emit(
                "overlay_source_unavailable",
                state=self._state.value,
                thread_id=self._thread_id,
                turn_index=page.turn_index,
            )
            return
        opened = QDesktopServices.openUrl(QUrl(source_url))
        self._emit(
            "overlay_source_clicked",
            state=self._state.value,
            thread_id=self._thread_id,
            turn_index=page.turn_index,
            source_url_preview=self._preview_text(source_url, max_len=120),
            open_ok=opened,
        )

    @staticmethod
    def _truncate_for_page(text: str, limit: int) -> str:
        compact = " ".join((text or "").split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: max(0, limit - 3)]}..."

    def _rounded_capture_preview(self, source: QPixmap, target_w: int, target_h: int, radius: int) -> QPixmap:
        width = max(1, int(target_w))
        height = max(1, int(target_h))
        rounded = QPixmap(width, height)
        rounded.fill(Qt.GlobalColor.transparent)
        scaled = source.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, float(radius), float(radius))
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    def _reset_capture_preview(self) -> None:
        self._capture_preview_label.clear()
        self._capture_preview_label.hide()
        self._capture_preview_label.setMinimumWidth(0)
        self._capture_preview_label.setMaximumWidth(16777215)
        self._capture_preview_label.setFixedHeight(self._capture_preview_height)

    def _render_prompt_page_and_reflow(self) -> None:
        if self._state != OverlayState.PROMPT:
            return
        self._render_selected_prompt_page()
        self._reflow_prompt_card_geometry()

    def _reflow_prompt_card_geometry(self) -> None:
        if self._state != OverlayState.PROMPT or not self.isVisible() or not self._card.isVisible():
            return
        geometry = self._primary_available_geometry()
        available_height = max(120, geometry.height() - (self._launcher_margin * 2))
        available_width = max(160, geometry.width() - (self._launcher_margin * 2))

        min_width = min(self._min_width, available_width)
        max_width = min(max(self._min_width, self._max_width), available_width)
        self._card.setMinimumWidth(min_width)
        self._card.setMaximumWidth(max_width)
        card_layout = self._card.layout()
        if card_layout is not None:
            card_layout.activate()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.activate()

        width, measured_height = self._measure_card_target_size(
            min_width=min_width,
            max_width=max_width,
            available_height=available_height,
        )
        height = self._resolve_prompt_height(measured_height, available_height)
        origin = self._launcher_origin(bubble_height=height)
        self._apply_window_geometry(
            x=origin.x(),
            y=origin.y(),
            width=width,
            height=height,
        )

    def _measure_card_target_size(self, min_width: int, max_width: int, available_height: int) -> tuple[int, int]:
        card_hint = self._card.sizeHint()
        card_min_hint = self._card.minimumSizeHint()
        natural_width = max(1, card_hint.width(), card_min_hint.width())
        width = min(max_width, max(min_width, natural_width))
        natural_height = max(1, card_hint.height(), card_min_hint.height())
        card_layout = self._card.layout()
        if card_layout is not None and card_layout.hasHeightForWidth():
            natural_height = max(natural_height, card_layout.heightForWidth(width))

        height_cap = available_height
        if self._state == OverlayState.PROMPT:
            screen_height = max(1, self._primary_available_geometry().height())
            prompt_cap = max(220, int(screen_height * self._prompt_max_height_ratio))
            height_cap = min(height_cap, prompt_cap)

        height = min(natural_height, height_cap)
        return width, height

    def _resolve_prompt_height(self, candidate_height: int, available_height: int) -> int:
        clamped = max(1, min(int(candidate_height), int(available_height)))
        # Adaptive page sizing: allow both expansion and compression based on selected page content.
        self._prompt_locked_height = clamped
        return self._prompt_locked_height

    def _expand_from_launcher_to_card(self, target_rect: QRect) -> None:
        if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
            self._geometry_animation.stop()
        if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
            self._opacity_animation.stop()

        start_rect = self._launcher_rect()
        self._geometry_animation_mode = "expand"
        self._geometry_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._geometry_animation.setDuration(220)
        self._geometry_animation.setStartValue(start_rect)
        self._geometry_animation.setEndValue(target_rect)
        self.setGeometry(start_rect)
        self.show()
        self.raise_()
        self._geometry_animation.start()

    def _collapse_to_launcher(self, reason: str, previous_state: str | None = None) -> None:
        prior = previous_state or self._state.value
        already_launcher = self._launcher_button.isVisible() and not self._card.isVisible()
        self._state = OverlayState.LAUNCHER
        self._set_input_mode(False)
        self._auto_hide_timer.stop()
        self._loading_timer.stop()
        self._loading_label.hide()
        if self._opacity_animation.state() != QPropertyAnimation.State.Stopped:
            self._opacity_animation.stop()
        if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
            self._geometry_animation.stop()

        target_rect = self._launcher_rect()
        duration = 120 if reason == "escape" else 180
        if already_launcher:
            if self._launcher_temporarily_hidden:
                self.hide()
            else:
                self.setGeometry(target_rect)
                self.show()
                self.raise_()
            self._emit(
                "overlay_hidden",
                state=self._state.value,
                previous_state=prior,
                reason=reason,
                region=self._region_payload(self._anchor_region),
            )
            return

        if not self.isVisible():
            self._card.hide()
            self._launcher_button.show()
            if self._launcher_temporarily_hidden:
                self.hide()
            else:
                self.setGeometry(target_rect)
                self.show()
                self.raise_()
            self._emit(
                "overlay_collapsed_to_launcher",
                state=self._state.value,
                previous_state=prior,
                reason=reason,
                region=self._region_payload(self._anchor_region),
            )
            self._emit(
                "overlay_hidden",
                state=self._state.value,
                previous_state=prior,
                reason=reason,
                region=self._region_payload(self._anchor_region),
            )
            return

        self._geometry_animation_mode = "collapse"
        self._pending_collapse_reason = reason
        self._pending_collapse_previous_state = prior
        self._card.show()
        self._launcher_button.hide()
        self._geometry_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._geometry_animation.setDuration(duration)
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(target_rect)
        self._geometry_animation.start()

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
            self._thinking_shimmer_step += 1
            self._message_label.setText(self._build_thinking_shimmer_markup(self._thinking_shimmer_step))
            return

        self._loading_timer.stop()
        self._loading_label.hide()

    def _on_geometry_animation_finished(self) -> None:
        mode = self._geometry_animation_mode
        self._geometry_animation_mode = None
        if mode != "collapse":
            return

        reason = self._pending_collapse_reason
        previous_state = self._pending_collapse_previous_state
        self._card.hide()
        self._launcher_button.show()
        if self._launcher_temporarily_hidden:
            self.hide()
        else:
            self.setGeometry(self._launcher_rect())
            self.show()
            self.raise_()
        self._emit(
            "overlay_collapsed_to_launcher",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )
        self._emit(
            "overlay_hidden",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )

    def _build_thinking_shimmer_markup(self, step: int) -> str:
        text = self._thinking_text
        if not text:
            return "Agent is Thinking"

        width = max(2, min(self._thinking_shimmer_width, len(text)))
        cycle_len = len(text) + (width * 2)
        center = (step % cycle_len) - width
        base = (201, 212, 227, 188)
        highlight = (245, 249, 255, 250)
        parts: list[str] = []

        for index, char in enumerate(text):
            distance = abs(index - center)
            strength = max(0.0, 1.0 - (distance / max(1, width)))
            red = self._lerp_channel(base[0], highlight[0], strength)
            green = self._lerp_channel(base[1], highlight[1], strength)
            blue = self._lerp_channel(base[2], highlight[2], strength)
            alpha = self._lerp_channel(base[3], highlight[3], strength)
            weight = 500 if strength < 0.35 else 600
            escaped = "&nbsp;" if char == " " else html.escape(char, quote=False)
            parts.append(
                f'<span style="color: rgba({red}, {green}, {blue}, {alpha}); font-weight: {weight};">{escaped}</span>'
            )
        return "".join(parts)

    @staticmethod
    def _lerp_channel(start: int, end: int, factor: float) -> int:
        bounded = max(0.0, min(1.0, factor))
        return int(start + ((end - start) * bounded))

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

    def _on_launcher_clicked(self) -> None:
        self._emit(
            "overlay_launcher_clicked",
            state=self._state.value,
            region=self._region_payload(self._anchor_region),
        )
        self.launcher_requested.emit()

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
        if not self._is_selected_page_current_turn():
            return
        raw_text = self._input_edit.text().strip()
        payload_text = raw_text or self._submit_default_intent
        self._emit_submission(payload_text, used_default=not bool(raw_text), raw_text=raw_text)

    def _on_input_focus_intent(self) -> None:
        if self._state != OverlayState.PROMPT or self._input_mode_enabled:
            return
        if not self._is_selected_page_current_turn():
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

    def _emit_submission(self, payload_text: str, used_default: bool, raw_text: str = "") -> None:
        self._last_submitted_text = payload_text
        user_text = " ".join(raw_text.split())
        if user_text:
            idx = self._current_turn_page_index()
            if 0 <= idx < len(self._interaction_pages):
                self._interaction_pages[idx].user_response_text = user_text
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
        if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
            self._geometry_animation.stop()
        self.setWindowOpacity(1.0)
        self.hide()
        self._emit(
            "overlay_hidden",
            state=self._state.value,
            previous_state=previous_state,
            reason=reason,
            region=self._region_payload(self._anchor_region),
        )

    def _apply_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        target_width = max(1, int(width))
        target_height = max(1, int(height))
        target_x = int(x)
        target_y = int(y)
        target_rect = QRect(target_x, target_y, target_width, target_height)
        current_rect = self.geometry()
        if current_rect == target_rect:
            return

        if (
            not self.isVisible()
            or current_rect.width() <= 1
            or current_rect.height() <= 1
        ):
            self.setGeometry(target_rect)
            return

        if self._geometry_animation.state() != QPropertyAnimation.State.Stopped:
            self._geometry_animation.stop()
            current_rect = self.geometry()
            if current_rect == target_rect:
                return

        size_changed = (
            current_rect.width() != target_rect.width()
            or current_rect.height() != target_rect.height()
        )
        if not size_changed:
            self.setGeometry(target_rect)
            return

        delta = abs(target_rect.width() - current_rect.width()) + abs(target_rect.height() - current_rect.height())
        if self._state in (OverlayState.PROMPT, OverlayState.THINKING):
            # Keep prompt<->thinking/page transitions on the same smooth motion profile.
            duration = self._clamp(int(700 + (delta * 0.30)), 700, 900)
            self._geometry_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        else:
            duration = self._clamp(int(120 + (delta * 0.35)), 120, 220)
            self._geometry_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._geometry_animation.setDuration(duration)
        self._geometry_animation.setStartValue(current_rect)
        self._geometry_animation.setEndValue(target_rect)
        self._geometry_animation.start()

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

            QPushButton#LauncherButton {
                background: rgba(26, 31, 38, 234);
                border: 3px solid rgba(22, 124, 203, 236);
                border-radius: 23px;
                padding: 0px;
                margin: 0px;
            }

            QPushButton#LauncherButton:hover {
                background: rgba(34, 40, 49, 238);
                border-color: rgba(38, 138, 218, 238);
            }

            QPushButton#LauncherButton:pressed {
                background: rgba(20, 25, 31, 242);
                border-color: rgba(16, 110, 186, 238);
            }

            QFrame#ResponseCard {
                background: rgba(8, 11, 15, 228);
                border: none;
                border-radius: 16px;
            }

            QFrame#TopHighlight {
                border: none;
                border-radius: 1px;
                background: rgba(219, 231, 245, 36);
            }

            QFrame#MessageRow {
                background: transparent;
                border: none;
            }

            QFrame#MessageContent {
                background: transparent;
                border: none;
            }

            QLabel#CapturePreview {
                background: transparent;
                border: none;
            }

            QFrame#MessageShell {
                background: transparent;
                border: none;
            }

            QFrame#PageRail {
                background: transparent;
                border: none;
            }

            QPushButton#PageDot {
                background: rgba(153, 176, 198, 116);
                border: 1px solid rgba(209, 223, 238, 72);
                border-radius: 5px;
                padding: 0px;
                margin: 0px;
            }

            QPushButton#PageDot:hover {
                background: rgba(176, 197, 218, 158);
            }

            QPushButton#PageDot:checked {
                background: rgba(22, 124, 203, 236);
                border-color: rgba(116, 184, 236, 196);
            }

            QPushButton#DismissButton {
                background: rgba(34, 41, 50, 232);
                border: 1px solid rgba(214, 226, 241, 38);
                border-radius: 10px;
                color: rgba(226, 236, 248, 210);
                font-family: __FONT_STACK__;
                font-size: 12px;
                font-weight: 600;
                padding: 0px;
                margin: 0px;
            }

            QPushButton#DismissButton:hover {
                background: rgba(42, 50, 60, 236);
            }

            QPushButton#DismissButton:pressed {
                background: rgba(27, 33, 40, 240);
            }

            QLabel#MessageLabel {
                background: transparent;
                border: none;
                color: rgba(242, 247, 253, 236);
                font-family: __FONT_STACK__;
                font-size: 13px;
                font-weight: 500;
                selection-background-color: rgba(116, 154, 194, 120);
                selection-color: rgba(247, 251, 255, 250);
            }

            QLabel#LoadingLabel {
                background: transparent;
                border: none;
                color: rgba(201, 212, 227, 190);
                font-family: __FONT_STACK__;
                font-size: 10px;
                font-weight: 450;
                letter-spacing: 0.3px;
            }

            QFrame#PromptDivider {
                border: none;
                background: rgba(228, 237, 249, 56);
                min-height: 1px;
                max-height: 1px;
            }

            QFrame#SourceButtonRow {
                background: transparent;
                border: none;
            }

            QPushButton#SourcePill {
                background: rgba(37, 72, 99, 226);
                color: rgba(236, 245, 255, 246);
                border: 1px solid rgba(142, 189, 227, 152);
                border-radius: 999px;
                padding: 2px 9px;
                font-family: __FONT_STACK__;
                font-size: 10px;
                font-weight: 620;
                min-height: 20px;
                max-height: 20px;
            }

            QPushButton#SourcePill:hover {
                background: rgba(47, 86, 116, 236);
                border-color: rgba(172, 211, 240, 182);
            }

            QPushButton#SourcePill:pressed {
                background: rgba(29, 61, 84, 238);
            }

            QFrame#ComposerPanel {
                background: rgba(0, 0, 0, 214);
                border: 1px solid rgba(220, 231, 244, 74);
                border-radius: 11px;
                min-height: 34px;
                max-height: 34px;
            }

            QLineEdit#InputEdit {
                background: transparent;
                border: none;
                color: rgba(245, 249, 255, 238);
                font-family: __FONT_STACK__;
                font-size: 12px;
                font-weight: 450;
                padding: 3px 1px;
                min-height: 24px;
                max-height: 24px;
                selection-background-color: rgba(105, 139, 170, 132);
                selection-color: rgba(248, 251, 255, 250);
            }

            QLineEdit#InputEdit:focus {
                border: none;
            }

            QLineEdit#InputEdit:disabled {
                border: none;
                color: rgba(183, 198, 214, 178);
            }

            QFrame#ActionsRow {
                background: transparent;
                border: none;
            }

            QPushButton#RetryButton {
                border-radius: 9px;
                padding: 0px;
                font-family: __FONT_STACK__;
                font-size: 11px;
                font-weight: 600;
                min-height: 28px;
                max-height: 28px;
                min-width: 32px;
                max-width: 34px;
            }

            QPushButton#SubmitButton {
                background: rgba(22, 124, 203, 238);
                color: rgba(245, 251, 255, 244);
                border: 1px solid rgba(74, 162, 230, 144);
                border-radius: 12px;
                padding: 0px;
                min-height: 24px;
                max-height: 24px;
                min-width: 24px;
                max-width: 24px;
                font-family: __FONT_STACK__;
                font-size: 10px;
                font-weight: 700;
            }

            QPushButton#SubmitButton:hover {
                background: rgba(30, 134, 213, 244);
            }

            QPushButton#SubmitButton:pressed {
                background: rgba(16, 106, 173, 245);
            }

            QPushButton#RetryButton {
                background: rgba(62, 83, 103, 222);
                color: rgba(232, 241, 251, 236);
                border: 1px solid rgba(184, 202, 223, 104);
            }

            QPushButton#RetryButton:hover {
                background: rgba(68, 91, 113, 228);
            }

            QPushButton#RetryButton:pressed {
                background: rgba(56, 76, 95, 232);
            }

            QPushButton#SubmitButton:disabled,
            QPushButton#RetryButton:disabled,
            QPushButton#SourcePill:disabled {
                color: rgba(176, 188, 202, 140);
                background-color: rgba(246, 249, 253, 14);
                border-color: rgba(246, 249, 253, 18);
            }
        """.replace("__FONT_STACK__", font_stack)
        self.setStyleSheet(stylesheet)


