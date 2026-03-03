from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bridge_host: str = os.getenv("BRIDGE_HOST", "127.0.0.1")
    bridge_port: int = int(os.getenv("BRIDGE_PORT", "8000"))
    dashboard_origin: str = os.getenv("DASHBOARD_ORIGIN", "http://localhost:5173")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
    agent_backend: str = os.getenv("SENTINEL_AGENT_BACKEND", "bridge").strip().lower()
    friend_agent_script_path: str = os.getenv("SENTINEL_FRIEND_AGENT_SCRIPT_PATH", "").strip()
    friend_agent_notes_path: str = os.getenv("SENTINEL_FRIEND_AGENT_NOTES_PATH", "").strip()
    friend_agent_model: str = os.getenv("SENTINEL_TUTOR_MODEL", "").strip()
    friend_agent_aux_model: str = os.getenv("SENTINEL_AUX_MODEL", "").strip()

    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12.0"))
    material_upload_max_bytes: int = int(os.getenv("BRIDGE_MATERIAL_UPLOAD_MAX_BYTES", "15728640"))
    sentinel_runtime_enabled: bool = _env_bool("SENTINEL_RUNTIME_ENABLED", True)
    sentinel_runtime_python: str = os.getenv("SENTINEL_RUNTIME_PYTHON", "").strip()
    sentinel_runtime_workdir: str = os.getenv("SENTINEL_RUNTIME_WORKDIR", "").strip()
    sentinel_runtime_stop_timeout_seconds: float = float(os.getenv("SENTINEL_RUNTIME_STOP_TIMEOUT_SECONDS", "2.0"))

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
    def documents_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "course-documents"

    @property
    def state_file(self) -> Path:
        return PROJECT_ROOT / "data" / "state.json"

    @property
    def sentinel_session_context_file(self) -> Path:
        return PROJECT_ROOT / "data" / "sentinel-session-context.json"

    @property
    def topics_dir(self) -> Path:
        preferred = PROJECT_ROOT / "data" / "topics"
        legacy = PROJECT_ROOT / "data" / "modules"
        if preferred.exists():
            return preferred
        if legacy.exists():
            return legacy
        return preferred

    @property
    def modules_dir(self) -> Path:
        # Backward-compatible alias for legacy imports.
        return self.topics_dir

    @property
    def friend_agent_state_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "friend-agent-state"

    @property
    def syllabus_file(self) -> Path:
        return PROJECT_ROOT / "syllabus.json"

    @property
    def sentinel_runtime_default_python(self) -> Path:
        return PROJECT_ROOT / "apps" / "sentinel-desktop" / ".venv" / "Scripts" / "python.exe"

    @property
    def sentinel_runtime_default_workdir(self) -> Path:
        return PROJECT_ROOT / "apps" / "sentinel-desktop"

    @property
    def sentinel_runtime_metadata_file(self) -> Path:
        return PROJECT_ROOT / "data" / "sentinel-runtime.json"

    @property
    def sentinel_runtime_logs_dir(self) -> Path:
        return PROJECT_ROOT / "artifacts" / "sentinel-runtime"


settings = Settings()
