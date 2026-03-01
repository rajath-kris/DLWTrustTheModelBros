from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    bridge_host: str = os.getenv("BRIDGE_HOST", "127.0.0.1")
    bridge_port: int = int(os.getenv("BRIDGE_PORT", "8000"))
    dashboard_origin: str = os.getenv("DASHBOARD_ORIGIN", "http://localhost:5173")

    azure_vision_endpoint: str = os.getenv("AZURE_VISION_ENDPOINT", "").strip()
    azure_vision_key: str = os.getenv("AZURE_VISION_KEY", "").strip()

    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_openai_key: str = os.getenv("AZURE_OPENAI_KEY", "").strip()
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12.0"))

    @property
    def dashboard_origins(self) -> list[str]:
        defaults = {"http://localhost:5173", "http://127.0.0.1:5173"}
        raw_items = [item.strip() for item in self.dashboard_origin.split(",") if item.strip()]
        if not raw_items:
            return sorted(defaults)
        return sorted(set(raw_items).union(defaults))

    @property
    def captures_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "captures"

    @property
    def state_file(self) -> Path:
        return PROJECT_ROOT / "data" / "state.json"

    @property
    def syllabus_file(self) -> Path:
        return PROJECT_ROOT / "syllabus.json"


settings = Settings()
