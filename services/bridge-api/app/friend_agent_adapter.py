from __future__ import annotations

import importlib.util
import io
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, Settings
from .grounding import tokenize


@dataclass
class FriendAgentResult:
    reply: str
    current_topic: str | None
    reply_mode: str | None
    dashboard_state: dict[str, Any]
    notes_path: str | None


class FriendAgentAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._session_class: type[Any] | None = None
        self._sessions: dict[str, tuple[str, Any]] = {}
        self._load_error: str | None = None
        self._script_path = self._resolve_script_path()

        if self._settings.agent_backend != "friend":
            return
        try:
            self._session_class = self._load_session_class(self._script_path)
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._session_class = None

    @property
    def enabled(self) -> bool:
        return self._settings.agent_backend == "friend" and self._session_class is not None

    @property
    def configured(self) -> bool:
        return self._settings.agent_backend == "friend"

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def script_path(self) -> str:
        return str(self._script_path)

    def chat(
        self,
        *,
        thread_id: str,
        user_text: str,
        notes_path: str | None,
        image_bytes: bytes | None = None,
    ) -> FriendAgentResult:
        if not self.enabled:
            raise RuntimeError("Friend agent is not enabled.")

        with self._lock:
            session = self._get_or_create_session(thread_id=thread_id, notes_path=notes_path)

        screenshot = self._to_pil_image(image_bytes)
        reply = str(session.chat(user_text, screenshot_pil=screenshot)).strip()
        dashboard_state = session.get_gaps_for_dashboard()
        if not isinstance(dashboard_state, dict):
            dashboard_state = {}

        current_topic = getattr(session, "current_topic", None)
        if current_topic is not None:
            current_topic = str(current_topic).strip() or None

        reply_mode: str | None = None
        sessions = dashboard_state.get("sessions")
        if isinstance(sessions, list) and sessions:
            latest = sessions[-1]
            if isinstance(latest, dict):
                mode = latest.get("reply_mode")
                if mode is not None:
                    reply_mode = str(mode).strip() or None

        return FriendAgentResult(
            reply=reply,
            current_topic=current_topic,
            reply_mode=reply_mode,
            dashboard_state=dashboard_state,
            notes_path=notes_path,
        )

    def _get_or_create_session(self, *, thread_id: str, notes_path: str | None):
        if self._session_class is None:
            raise RuntimeError("Friend agent session class was not loaded.")

        resolved_notes = self._resolve_notes_path(notes_path)
        cache_key = self._cache_key(thread_id)
        cached = self._sessions.get(cache_key)
        if cached is not None:
            cached_notes_path, session = cached
            if cached_notes_path == resolved_notes:
                return session

        kwargs: dict[str, Any] = {
            "notes_path": resolved_notes,
            "state_file": str(self._state_file_for_thread(thread_id)),
        }
        if self._settings.friend_agent_model:
            kwargs["model"] = self._settings.friend_agent_model
        if self._settings.friend_agent_aux_model:
            kwargs["aux_model"] = self._settings.friend_agent_aux_model

        session = self._session_class(**kwargs)
        self._sessions[cache_key] = (resolved_notes, session)
        return session

    def _resolve_script_path(self) -> Path:
        if self._settings.friend_agent_script_path:
            return Path(self._settings.friend_agent_script_path).expanduser().resolve()

        candidates = [
            PROJECT_ROOT.parent / "aayush code" / "sentinel_brain (1).py",
            PROJECT_ROOT / "sentinel_brain (1).py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        # Keep the primary default path for clearer startup errors.
        return candidates[0].resolve()

    def _resolve_notes_path(self, notes_path: str | None) -> str:
        if notes_path:
            return str(Path(notes_path).expanduser().resolve())
        if self._settings.friend_agent_notes_path:
            return str(Path(self._settings.friend_agent_notes_path).expanduser().resolve())
        return "lecture_notes.pdf"

    def _load_session_class(self, script_path: Path):
        if not script_path.exists():
            raise FileNotFoundError(f"Friend agent script not found: {script_path}")

        spec = importlib.util.spec_from_file_location("sentinel_friend_agent", str(script_path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load module spec from {script_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._patch_module_tokenizer(module)

        session_class = getattr(module, "SentinelSession", None)
        if session_class is None:
            raise RuntimeError(f"'SentinelSession' was not found in {script_path}")
        return session_class

    def _patch_module_tokenizer(self, module: Any) -> None:
        if not hasattr(module, "_tokenize"):
            return

        def _tokenize_with_math(text: str) -> list[str]:
            return tokenize(text)

        module._tokenize = _tokenize_with_math  # type: ignore[attr-defined]

    def _state_file_for_thread(self, thread_id: str) -> Path:
        self._settings.friend_agent_state_dir.mkdir(parents=True, exist_ok=True)
        safe = self._cache_key(thread_id)
        return self._settings.friend_agent_state_dir / f"{safe}.json"

    def _cache_key(self, thread_id: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", thread_id.strip())
        cleaned = cleaned.strip("-")
        return cleaned[:80] or "thread"

    def _to_pil_image(self, image_bytes: bytes | None):
        if image_bytes is None:
            return None
        try:
            from PIL import Image
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Pillow is required for screenshot-backed friend-agent calls."
            ) from exc

        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.convert("RGB")
