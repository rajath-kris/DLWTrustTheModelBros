from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SentinelSettings:
    bridge_url: str = os.getenv("SENTINEL_BRIDGE_URL", "http://127.0.0.1:8000")
    bridge_timeout_seconds: float = _env_float("SENTINEL_BRIDGE_TIMEOUT_SECONDS", 45.0)
    active_topic_id: str = (os.getenv("SENTINEL_ACTIVE_TOPIC_ID") or os.getenv("SENTINEL_ACTIVE_MODULE_ID", "")).strip()
    capture_hotkey: str = os.getenv("SENTINEL_CAPTURE_HOTKEY", "alt+s")
    escape_hotkey: str = os.getenv("SENTINEL_ESCAPE_HOTKEY", "esc")

    overlay_prompt_ttl_ms: int = _env_int("SENTINEL_OVERLAY_PROMPT_TTL_MS", 20000)
    overlay_loading_dot_interval_ms: int = _env_int("SENTINEL_OVERLAY_LOADING_DOT_INTERVAL_MS", 350)
    overlay_min_width: int = _env_int("SENTINEL_OVERLAY_MIN_WIDTH", 288)
    overlay_max_width: int = _env_int("SENTINEL_OVERLAY_MAX_WIDTH", 440)
    test_mode: bool = _env_bool("SENTINEL_TEST_MODE", False)
    local_trigger_enabled: bool = _env_bool("SENTINEL_LOCAL_TRIGGER_ENABLED", _env_bool("SENTINEL_TEST_MODE", False))
    local_trigger_key: str = os.getenv("SENTINEL_LOCAL_TRIGGER_KEY", "Ctrl+Shift+S").strip() or "Ctrl+Shift+S"
    test_scenario_label: str = os.getenv("SENTINEL_TEST_SCENARIO_LABEL", "").strip()
    overlay_input_max_chars: int = _env_int("SENTINEL_OVERLAY_INPUT_MAX_CHARS", 280)
    overlay_show_input_confirmation: bool = _env_bool("SENTINEL_OVERLAY_SHOW_INPUT_CONFIRMATION", True)
    overlay_input_required: bool = _env_bool("SENTINEL_OVERLAY_INPUT_REQUIRED", True)
    overlay_thinking_hold_ms: int = _env_int("SENTINEL_OVERLAY_THINKING_HOLD_MS", 2000)
    overlay_thinking_min_width: int = _env_int("SENTINEL_OVERLAY_THINKING_MIN_WIDTH", 188)
    overlay_thinking_max_width: int = _env_int("SENTINEL_OVERLAY_THINKING_MAX_WIDTH", 240)
    ui_fade_in_ms: int = _env_int("SENTINEL_UI_FADE_IN_MS", 220)
    ui_fade_text_stagger_ms: int = _env_int("SENTINEL_UI_FADE_TEXT_STAGGER_MS", 60)
    ui_use_actor_font: bool = _env_bool("SENTINEL_UI_USE_ACTOR_FONT", True)


settings = SentinelSettings()
