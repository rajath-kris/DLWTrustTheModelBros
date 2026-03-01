from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import CaptureEvent, KnowledgeGap, LearningState, ReadinessAxes, utc_now_iso


class StateStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists() or self.file_path.read_text(encoding="utf-8").strip() == "":
            self.write(LearningState())

    def read(self) -> LearningState:
        with self._lock:
            return self._read_unlocked()

    def write(self, state: LearningState) -> None:
        with self._lock:
            self._write_unlocked(state)

    def append_capture(
        self,
        event: CaptureEvent,
        new_gaps: list[KnowledgeGap],
        readiness_axes: ReadinessAxes,
    ) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            state.captures.append(event)
            state.gaps.extend(new_gaps)
            state.readiness_axes = readiness_axes
            self._write_unlocked(state)
            return state

    def update_gap_status(self, gap_id: str, status: str) -> LearningState | None:
        with self._lock:
            state = self._read_unlocked()
            target = next((gap for gap in state.gaps if gap.gap_id == gap_id), None)
            if target is None:
                return None
            target.status = status
            self._write_unlocked(state)
            return state

    def _read_unlocked(self) -> LearningState:
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        return LearningState.model_validate(payload)

    def _write_unlocked(self, state: LearningState) -> None:
        state.updated_at = utc_now_iso()
        tmp_path = self.file_path.with_suffix(".tmp")
        tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp_path, self.file_path)
