from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class SentinelSessionContextStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._lock = threading.Lock()
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists() or self._file_path.read_text(encoding="utf-8").strip() == "":
            self._write_unlocked(self._default_payload())

    def get(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def set(
        self,
        *,
        course_id: str,
        course_name: str,
        topic_id: str,
        topic_name: str,
        updated_at: str,
    ) -> dict[str, Any]:
        with self._lock:
            payload = {
                "course_id": course_id,
                "course_name": course_name,
                "topic_id": topic_id,
                "topic_name": topic_name,
                "updated_at": updated_at,
            }
            self._write_unlocked(payload)
            return dict(payload)

    def clear(self) -> dict[str, Any]:
        with self._lock:
            payload = self._default_payload()
            self._write_unlocked(payload)
            return dict(payload)

    def _default_payload(self) -> dict[str, Any]:
        return {
            "course_id": None,
            "course_name": None,
            "topic_id": None,
            "topic_name": None,
            "updated_at": None,
        }

    def _read_unlocked(self) -> dict[str, Any]:
        if not self._file_path.exists():
            return self._default_payload()
        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_payload()

        result = self._default_payload()
        for key in ("course_id", "course_name", "topic_id", "topic_name", "updated_at"):
            value = payload.get(key)
            result[key] = value if value is None or isinstance(value, str) else None
        return result

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        tmp_path = self._file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._file_path)
