from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class SentinelSettings:
    bridge_url: str = os.getenv("SENTINEL_BRIDGE_URL", "http://127.0.0.1:8000")
    capture_hotkey: str = os.getenv("SENTINEL_CAPTURE_HOTKEY", "alt+s")
    escape_hotkey: str = os.getenv("SENTINEL_ESCAPE_HOTKEY", "esc")


settings = SentinelSettings()
