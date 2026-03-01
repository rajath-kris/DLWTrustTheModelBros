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


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SentinelSettings:
    bridge_url: str = os.getenv("SENTINEL_BRIDGE_URL", "http://127.0.0.1:8000")
    capture_hotkey: str = os.getenv("SENTINEL_CAPTURE_HOTKEY", "alt+s")
    escape_hotkey: str = os.getenv("SENTINEL_ESCAPE_HOTKEY", "esc")

    overlay_prompt_ttl_ms: int = _env_int("SENTINEL_OVERLAY_PROMPT_TTL_MS", 20000)
    overlay_loading_dot_interval_ms: int = _env_int("SENTINEL_OVERLAY_LOADING_DOT_INTERVAL_MS", 350)
    overlay_min_width: int = _env_int("SENTINEL_OVERLAY_MIN_WIDTH", 320)
    overlay_max_width: int = _env_int("SENTINEL_OVERLAY_MAX_WIDTH", 520)
    test_mode: bool = _env_bool("SENTINEL_TEST_MODE", False)
    local_trigger_enabled: bool = _env_bool("SENTINEL_LOCAL_TRIGGER_ENABLED", _env_bool("SENTINEL_TEST_MODE", False))
    local_trigger_key: str = os.getenv("SENTINEL_LOCAL_TRIGGER_KEY", "Ctrl+Shift+S").strip() or "Ctrl+Shift+S"
    test_scenario_label: str = os.getenv("SENTINEL_TEST_SCENARIO_LABEL", "").strip()


settings = SentinelSettings()
