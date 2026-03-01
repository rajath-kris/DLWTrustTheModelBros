from __future__ import annotations

import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import requests
from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QPushButton, QVBoxLayout, QWidget

from .bridge_client import BridgeClient
from .capture import capture_region
from .config import settings
from .hotkey import HotkeyManager
from .overlay import OverlayBubble, OverlayState
from .platform import get_active_window_metadata, platform_name
from .region_selector import select_region
from .types import CaptureRegion, MonitorSnapshot, WindowMetadata
from .ui_theme import load_actor_font, qss_font_family_stack


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CaptureContext:
    platform: str
    window: WindowMetadata
    monitor: MonitorSnapshot
    region: CaptureRegion
    image_bytes: bytes


@dataclass
class AnalysisResult:
    request_id: int
    status: str
    region: CaptureRegion
    prompt: str = ""
    capture_id: str = ""
    thread_id: str = ""
    turn_index: int = 0
    source_mode: str = ""
    error_message: str = ""
    error_hint: str = ""
    error_category: str = ""


class JourneyControlPanel(QWidget):
    capture_requested = pyqtSignal(str)

    def __init__(self, local_trigger_key: str, scenario_label: str, font_family: str, fade_in_ms: int) -> None:
        super().__init__()
        self.setWindowTitle("Sentinel Journey Control")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.resize(320, 180)
        self._fade_in_ms = max(100, int(fade_in_ms))
        self._font_stack = qss_font_family_stack(font_family)

        title = QLabel("Overlay Test Mode")
        title.setStyleSheet("font-family: __FONT_STACK__; font-size:16px;font-weight:700;color:#f8fbff;".replace("__FONT_STACK__", self._font_stack))

        scenario = QLabel(f"Scenario: {scenario_label or 'unspecified'}")
        scenario.setStyleSheet("font-family: __FONT_STACK__; font-size:12px;color:#d8e0eb;".replace("__FONT_STACK__", self._font_stack))

        hint = QLabel(
            "Use Alt+S globally, or use the local trigger below.\n"
            "Press Esc to dismiss selector/overlay."
        )
        hint.setStyleSheet("font-family: __FONT_STACK__; font-size:12px;color:#adbacb;".replace("__FONT_STACK__", self._font_stack))
        hint.setWordWrap(True)

        button = QPushButton(f"Start Capture ({local_trigger_key})")
        button.setStyleSheet(
            (
                "font-family: __FONT_STACK__;font-size:13px;font-weight:600;padding:8px 10px;border-radius:10px;"
                "background:#141923;color:#eef4ff;border:1px solid #2a3447;"
            ).replace("__FONT_STACK__", self._font_stack)
        )
        button.clicked.connect(lambda: self.capture_requested.emit("local_panel_button"))

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(scenario)
        layout.addWidget(hint)
        layout.addWidget(button)
        self.setLayout(layout)
        self.setStyleSheet("background:#0c1119;border:1px solid #2f3b4e;border-radius:12px;")

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_animation.setDuration(self._fade_in_ms)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shortcut = QShortcut(QKeySequence(local_trigger_key), self)
        self._shortcut.activated.connect(lambda: self.capture_requested.emit("local_panel_shortcut"))

    def showEvent(self, event) -> None:
        self._fade_animation.stop()
        self._opacity_effect.setOpacity(0.0)
        self._fade_animation.start()
        super().showEvent(event)


class SentinelController(QObject):
    capture_requested = pyqtSignal(str)
    escape_requested = pyqtSignal(str)
    analysis_ready = pyqtSignal(object)

    def __init__(self, overlay: OverlayBubble, bridge: BridgeClient) -> None:
        super().__init__()
        self.overlay = overlay
        self.bridge = bridge
        self._last_region: CaptureRegion | None = None
        self._last_capture_context: CaptureContext | None = None
        self._request_sequence = 0
        self._active_request_id = 0
        self._request_started_at: dict[int, float] = {}
        self._scenario_label = settings.test_scenario_label
        self._active_thread_id: str | None = None
        self._active_turn_index = 0
        self._last_prompt_text = ""
        self._pending_user_input_text: str | None = None
        self._pending_success_result: AnalysisResult | None = None
        self._pending_success_duration_ms: int | None = None
        self._pending_success_was_turn_analysis = False
        self._thinking_visible_request_id: int | None = None
        self._thinking_visible_started_at: float | None = None
        self._selector_active = False
        self._analysis_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sentinel-analysis")

        self._thinking_hold_timer = QTimer(self)
        self._thinking_hold_timer.setSingleShot(True)
        self._thinking_hold_timer.timeout.connect(self._finalize_success_after_thinking)

        self.capture_requested.connect(self._on_capture_requested)
        self.escape_requested.connect(self._on_escape_requested)
        self.analysis_ready.connect(self._on_analysis_ready)
        self.overlay.retry_requested.connect(self._on_retry_requested)
        self.overlay.dismiss_requested.connect(lambda: self.trigger_escape("overlay_dismiss"))
        self.overlay.user_input_submitted.connect(self._on_user_input_submitted)
        self.overlay.set_telemetry_callback(self._on_overlay_event)

        self.overlay.set_retry_enabled(False)

    def trigger_capture(self, source_mode: str = "programmatic") -> None:
        self.capture_requested.emit(source_mode)

    def trigger_escape(self, source_mode: str = "programmatic") -> None:
        self.escape_requested.emit(source_mode)

    def shutdown(self) -> None:
        self._analysis_executor.shutdown(wait=False, cancel_futures=True)
        self._request_started_at.clear()

    def _on_capture_requested(self, source_mode: str) -> None:
        self._cancel_thinking_hold()
        if self._selector_active:
            self._log_event(
                "capture_ignored",
                source_mode=source_mode,
                reason="selector_active",
            )
            return

        self._log_event("capture_triggered", source_mode=source_mode)
        self._selector_active = True
        try:
            region = select_region(telemetry_callback=self._on_selector_event)
        finally:
            self._selector_active = False
        if region is None:
            self._log_event("capture_aborted", source_mode=source_mode, reason="selector_cancelled")
            return

        self._reset_turn_state()
        self._last_region = region
        self.overlay.show_analyzing_state(region)

        try:
            context = self._build_capture_context(region)
        except Exception:
            self.overlay.show_error_state(
                "Capture failed.",
                "Try selecting a smaller region and retry.",
                region,
                retry_enabled=self._last_capture_context is not None,
            )
            self._log_event(
                "request_failed",
                request_id=-1,
                source_mode=source_mode,
                error_category="capture_failure",
            )
            traceback.print_exc()
            return

        self._last_capture_context = context
        self._start_analysis(
            context,
            source_mode=source_mode,
            show_loading=False,
            thread_id=None,
            turn_index=0,
            previous_prompt=None,
            user_input_text=None,
            is_turn_analysis=False,
        )

    def _on_escape_requested(self, source_mode: str) -> None:
        self._log_event("escape_triggered", source_mode=source_mode)
        self._cancel_thinking_hold()
        self.overlay.hide_prompt(reason="escape")

    def _on_retry_requested(self) -> None:
        context = self._last_capture_context
        if context is None:
            self.overlay.show_error_state(
                "No previous capture available.",
                "Press Alt+S to create a capture first.",
                self._fallback_region(),
                retry_enabled=False,
            )
            self._log_event("retry_unavailable", reason="no_previous_capture")
            return

        pending_input = self._pending_user_input_text
        self._start_analysis(
            context,
            source_mode="retry",
            show_loading=True,
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
            previous_prompt=self._last_prompt_text or None,
            user_input_text=pending_input,
            is_turn_analysis=bool(pending_input),
        )

    def _on_user_input_submitted(self, text: str) -> None:
        context = self._last_capture_context
        if context is None:
            self.overlay.show_error_state(
                "No active capture context.",
                "Press Alt+S to capture first.",
                self._fallback_region(),
                retry_enabled=False,
            )
            self._log_event("user_input_rejected", reason="no_capture_context")
            return

        trimmed = text.strip()
        if not trimmed:
            self._log_event("user_input_rejected", reason="empty_input")
            return

        self._pending_user_input_text = trimmed
        self._log_event(
            "user_input_submitted",
            char_count=len(trimmed),
            preview=self._preview_text(trimmed),
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
        )
        self._start_analysis(
            context,
            source_mode="user_input_submit",
            show_loading=True,
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
            previous_prompt=self._last_prompt_text or None,
            user_input_text=trimmed,
            is_turn_analysis=True,
        )

    def _build_capture_context(self, region: CaptureRegion) -> CaptureContext:
        image_bytes, monitor = capture_region(region)
        window = get_active_window_metadata()
        platform = platform_name()
        return CaptureContext(
            platform=platform,
            window=window,
            monitor=monitor,
            region=region,
            image_bytes=image_bytes,
        )

    def _start_analysis(
        self,
        context: CaptureContext,
        source_mode: str,
        show_loading: bool,
        thread_id: str | None,
        turn_index: int,
        previous_prompt: str | None,
        user_input_text: str | None,
        is_turn_analysis: bool,
    ) -> None:
        self._cancel_thinking_hold()
        request_id = self._next_request_id()
        self._request_started_at[request_id] = time.monotonic()

        if show_loading:
            if is_turn_analysis:
                self._thinking_visible_request_id = request_id
                self._thinking_visible_started_at = time.monotonic()
                self.overlay.show_thinking_state(context.region, text="Thinking...")
            else:
                self._thinking_visible_request_id = None
                self._thinking_visible_started_at = None
                self.overlay.show_analyzing_state(
                    context.region,
                    status_text="Analyzing your response" if is_turn_analysis else "Analyzing capture",
                    message="Generating your next Socratic prompt...",
                )
        else:
            self._thinking_visible_request_id = None
            self._thinking_visible_started_at = None

        effective_turn_index = max(0, int(turn_index))
        user_input = user_input_text.strip() if user_input_text is not None else None

        self._log_event(
            "request_started",
            request_id=request_id,
            source_mode=source_mode,
            region=self._region_payload(context.region),
            thread_id=thread_id,
            turn_index=effective_turn_index,
            user_input_char_count=len(user_input) if user_input else 0,
        )
        if is_turn_analysis:
            self._log_event(
                "turn_analysis_started",
                request_id=request_id,
                source_mode=source_mode,
                thread_id=thread_id,
                turn_index=effective_turn_index,
                user_input_char_count=len(user_input) if user_input else 0,
            )

        def worker() -> None:
            try:
                result = self.bridge.submit_capture(
                    context.platform,
                    context.window,
                    context.monitor,
                    context.region,
                    context.image_bytes,
                    thread_id=thread_id,
                    turn_index=effective_turn_index,
                    previous_prompt=previous_prompt,
                    user_input_text=user_input,
                )
                prompt = str(
                    result.get("socratic_prompt", "What concept feels least clear in this capture?")
                ).strip() or "What concept feels least clear in this capture?"
                capture_id = str(result.get("capture_id", "")).strip()
                resolved_thread_id = str(result.get("thread_id", "")).strip() or thread_id or capture_id or str(uuid4())
                resolved_turn_index = self._coerce_turn_index(
                    result.get("turn_index"),
                    default=(effective_turn_index + 1 if is_turn_analysis else effective_turn_index),
                )
                self.analysis_ready.emit(
                    AnalysisResult(
                        request_id=request_id,
                        status="success",
                        region=context.region,
                        prompt=prompt,
                        capture_id=capture_id,
                        thread_id=resolved_thread_id,
                        turn_index=resolved_turn_index,
                        source_mode=source_mode,
                    )
                )
            except requests.Timeout:
                self._log_event(
                    "request_failed",
                    request_id=request_id,
                    error_category="timeout",
                )
                self.analysis_ready.emit(
                    AnalysisResult(
                        request_id=request_id,
                        status="error",
                        region=context.region,
                        thread_id=thread_id or "",
                        turn_index=effective_turn_index,
                        source_mode=source_mode,
                        error_message="Analysis timed out.",
                        error_hint="Retry, or check connection to the bridge.",
                        error_category="timeout",
                    )
                )
            except requests.ConnectionError:
                self._log_event(
                    "request_failed",
                    request_id=request_id,
                    error_category="bridge_unreachable",
                )
                self.analysis_ready.emit(
                    AnalysisResult(
                        request_id=request_id,
                        status="error",
                        region=context.region,
                        thread_id=thread_id or "",
                        turn_index=effective_turn_index,
                        source_mode=source_mode,
                        error_message="Cannot reach bridge API.",
                        error_hint="Start FastAPI on port 8000, then Retry.",
                        error_category="bridge_unreachable",
                    )
                )
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else -1
                self._log_event(
                    "request_failed",
                    request_id=request_id,
                    error_category="http_error",
                    status_code=status_code,
                )
                self.analysis_ready.emit(
                    AnalysisResult(
                        request_id=request_id,
                        status="error",
                        region=context.region,
                        thread_id=thread_id or "",
                        turn_index=effective_turn_index,
                        source_mode=source_mode,
                        error_message="Bridge returned an error.",
                        error_hint=f"HTTP {status_code}. Retry, or check bridge logs.",
                        error_category="http_error",
                    )
                )
            except Exception as exc:
                self._log_event(
                    "request_failed",
                    request_id=request_id,
                    error_category="unknown",
                    detail=type(exc).__name__,
                )
                self.analysis_ready.emit(
                    AnalysisResult(
                        request_id=request_id,
                        status="error",
                        region=context.region,
                        thread_id=thread_id or "",
                        turn_index=effective_turn_index,
                        source_mode=source_mode,
                        error_message="Unexpected analysis failure.",
                        error_hint="Retry. If it keeps failing, inspect terminal logs.",
                        error_category="unknown",
                    )
                )
                traceback.print_exc()

        try:
            self._analysis_executor.submit(worker)
        except RuntimeError:
            self._request_started_at.pop(request_id, None)
            self._log_event(
                "request_failed",
                request_id=request_id,
                source_mode=source_mode,
                error_category="analysis_worker_unavailable",
            )
            self.analysis_ready.emit(
                AnalysisResult(
                    request_id=request_id,
                    status="error",
                    region=context.region,
                    thread_id=thread_id or "",
                    turn_index=effective_turn_index,
                    source_mode=source_mode,
                    error_message="Analysis worker is unavailable.",
                    error_hint="Restart Sentinel and retry capture.",
                    error_category="analysis_worker_unavailable",
                )
            )

    def _on_analysis_ready(self, result: AnalysisResult) -> None:
        duration_ms = self._consume_duration_ms(result.request_id)
        if result.request_id != self._active_request_id:
            self._log_event(
                "stale_response_ignored",
                request_id=result.request_id,
                active_request_id=self._active_request_id,
                duration_ms=duration_ms,
            )
            return

        if result.status == "success":
            self._active_thread_id = result.thread_id.strip() or self._active_thread_id or result.capture_id or str(uuid4())
            self._active_turn_index = max(0, int(result.turn_index))
            self._last_prompt_text = result.prompt.strip()
            turn_request_was_submitted = self._pending_user_input_text is not None
            self._pending_user_input_text = None
            self._start_thinking_hold(
                result=result,
                duration_ms=duration_ms,
                was_turn_analysis=turn_request_was_submitted,
            )
            return

        self.overlay.show_error_state(
            result.error_message or "Could not analyze capture.",
            result.error_hint or "Retry, or check bridge status.",
            result.region,
            retry_enabled=self._last_capture_context is not None,
        )
        self._thinking_visible_request_id = None
        self._thinking_visible_started_at = None
        self._log_event(
            "request_error_presented",
            request_id=result.request_id,
            error_category=result.error_category or "unknown",
            duration_ms=duration_ms,
        )
        if self._pending_user_input_text is not None:
            self._log_event(
                "turn_analysis_completed",
                request_id=result.request_id,
                status="error",
                duration_ms=duration_ms,
                thread_id=result.thread_id or self._active_thread_id,
                turn_index=max(0, int(result.turn_index)),
                error_category=result.error_category or "unknown",
                )

    def _start_thinking_hold(
        self,
        result: AnalysisResult,
        duration_ms: int | None,
        was_turn_analysis: bool,
    ) -> None:
        if self._thinking_hold_timer.isActive():
            self._thinking_hold_timer.stop()
        self._pending_success_result = result
        self._pending_success_duration_ms = duration_ms
        self._pending_success_was_turn_analysis = was_turn_analysis
        target_hold_ms = max(0, int(settings.overlay_thinking_hold_ms))
        already_thinking = (
            self._thinking_visible_request_id == result.request_id
            and self.overlay.state == OverlayState.THINKING
        )
        hold_elapsed_ms = 0
        hold_ms = target_hold_ms
        if already_thinking:
            started_at = self._thinking_visible_started_at or time.monotonic()
            hold_elapsed_ms = int(max(0.0, (time.monotonic() - started_at) * 1000.0))
            hold_ms = max(0, target_hold_ms - hold_elapsed_ms)
        else:
            self.overlay.show_thinking_state(result.region, text="Thinking...")
            self._thinking_visible_request_id = result.request_id
            self._thinking_visible_started_at = time.monotonic()
        self._log_event(
            "thinking_hold_started",
            request_id=result.request_id,
            hold_ms=hold_ms,
            hold_target_ms=target_hold_ms,
            hold_elapsed_ms=hold_elapsed_ms,
            already_thinking=already_thinking,
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
        )
        if hold_ms <= 0:
            self._finalize_success_after_thinking()
            return
        self._thinking_hold_timer.start(hold_ms)

    def _finalize_success_after_thinking(self) -> None:
        result = self._pending_success_result
        if result is None:
            return

        duration_ms = self._pending_success_duration_ms
        was_turn_analysis = self._pending_success_was_turn_analysis
        self._pending_success_result = None
        self._pending_success_duration_ms = None
        self._pending_success_was_turn_analysis = False

        if result.request_id != self._active_request_id:
            self._log_event(
                "stale_response_ignored",
                request_id=result.request_id,
                active_request_id=self._active_request_id,
            )
            return

        self._log_event(
            "thinking_hold_completed",
            request_id=result.request_id,
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
        )
        self._thinking_visible_request_id = None
        self._thinking_visible_started_at = None
        self.overlay.show_prompt_input_state(
            result.prompt,
            result.region,
            thread_id=self._active_thread_id or result.thread_id,
            turn_index=self._active_turn_index,
            ttl_ms=settings.overlay_prompt_ttl_ms,
            retry_enabled=self._last_capture_context is not None,
        )
        self._log_event(
            "request_success",
            request_id=result.request_id,
            capture_id=result.capture_id,
            duration_ms=duration_ms,
            thread_id=self._active_thread_id,
            turn_index=self._active_turn_index,
        )
        if was_turn_analysis:
            self._log_event(
                "turn_analysis_completed",
                request_id=result.request_id,
                status="success",
                duration_ms=duration_ms,
                thread_id=self._active_thread_id,
                turn_index=self._active_turn_index,
            )

    def _cancel_thinking_hold(self) -> None:
        if self._thinking_hold_timer.isActive():
            self._thinking_hold_timer.stop()
        self._pending_success_result = None
        self._pending_success_duration_ms = None
        self._pending_success_was_turn_analysis = False
        self._thinking_visible_request_id = None
        self._thinking_visible_started_at = None

    def _next_request_id(self) -> int:
        self._request_sequence += 1
        self._active_request_id = self._request_sequence
        return self._active_request_id

    def _consume_duration_ms(self, request_id: int) -> int | None:
        start = self._request_started_at.pop(request_id, None)
        if start is None:
            return None
        return int(max(0.0, (time.monotonic() - start) * 1000.0))

    def _coerce_turn_index(self, value: Any, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return max(0, int(default))

    def _fallback_region(self) -> CaptureRegion:
        if self._last_region is not None:
            return self._last_region
        return CaptureRegion(x=40, y=40, width=320, height=160)

    def _region_payload(self, region: CaptureRegion | None) -> dict[str, int] | None:
        if region is None:
            return None
        return {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
        }

    def _on_overlay_event(self, event: str, fields: dict[str, Any]) -> None:
        self._log_event(event, **fields)

    def _on_selector_event(self, event: str, fields: dict[str, Any]) -> None:
        self._log_event(event, **fields)

    def _reset_turn_state(self) -> None:
        self._active_thread_id = None
        self._active_turn_index = 0
        self._last_prompt_text = ""
        self._pending_user_input_text = None

    def _preview_text(self, text: str, max_len: int = 64) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= max_len:
            return collapsed
        return f"{collapsed[: max_len - 3]}..."

    def _log_event(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "component": "sentinel_overlay",
            "event": event,
            "timestamp_utc": utc_now_iso(),
            "scenario": self._scenario_label,
            "state": self.overlay.state.value,
            "request_id": None,
            "region": None,
            "duration_ms": None,
            "error_category": None,
            "thread_id": self._active_thread_id,
            "turn_index": self._active_turn_index if self._active_thread_id else None,
        }
        payload.update(fields)
        print(json.dumps(payload, ensure_ascii=True), flush=True)


def main() -> None:
    app = QApplication(sys.argv)
    ui_font_family = load_actor_font(use_actor_font=settings.ui_use_actor_font)

    overlay = OverlayBubble(
        min_width=settings.overlay_min_width,
        max_width=settings.overlay_max_width,
        loading_dot_interval_ms=settings.overlay_loading_dot_interval_ms,
        input_max_chars=settings.overlay_input_max_chars,
        show_input_confirmation=settings.overlay_show_input_confirmation,
        input_required=settings.overlay_input_required,
        font_family=ui_font_family,
        fade_in_ms=settings.ui_fade_in_ms,
        fade_text_stagger_ms=settings.ui_fade_text_stagger_ms,
        thinking_min_width=settings.overlay_thinking_min_width,
        thinking_max_width=settings.overlay_thinking_max_width,
    )
    bridge = BridgeClient(settings.bridge_url)
    controller = SentinelController(overlay, bridge)

    hotkeys = HotkeyManager(settings.capture_hotkey, settings.escape_hotkey)
    hotkeys.start(
        lambda: controller.trigger_capture("hotkey"),
        lambda: controller.trigger_escape("hotkey_escape"),
    )

    control_panel: JourneyControlPanel | None = None
    if settings.test_mode and settings.local_trigger_enabled:
        control_panel = JourneyControlPanel(
            local_trigger_key=settings.local_trigger_key,
            scenario_label=settings.test_scenario_label,
            font_family=ui_font_family,
            fade_in_ms=settings.ui_fade_in_ms,
        )
        control_panel.capture_requested.connect(controller.trigger_capture)
        control_panel.show()
        controller._log_event(  # noqa: SLF001
            "journey_control_opened",
            local_trigger_key=settings.local_trigger_key,
        )

    print("Sentinel running. Press Alt+S to capture region. Press Esc to close overlay.")
    if settings.test_mode:
        print("Test mode enabled.")
    print(f"Bridge: {settings.bridge_url}")

    try:
        app.exec()
    finally:
        controller.shutdown()
        if control_panel is not None:
            control_panel.close()
        hotkeys.stop()


if __name__ == "__main__":
    main()
