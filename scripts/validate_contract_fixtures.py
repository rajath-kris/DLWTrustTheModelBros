#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_APP_ROOT = REPO_ROOT / "services" / "bridge-api"
if str(BRIDGE_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_APP_ROOT))

from app.models import CaptureRequest, LearningState, QuizSubmitRequest  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    fixtures_dir = REPO_ROOT / "fixtures"
    schema_path = REPO_ROOT / "shared" / "schemas" / "learning-state.schema.json"

    capture_fixture = _load_json(fixtures_dir / "capture-request.v1.json")
    state_fixture = _load_json(fixtures_dir / "state-response.v1.json")
    quiz_fixture = _load_json(fixtures_dir / "quiz-submit.v1.json")
    state_schema = _load_json(schema_path)

    CaptureRequest.model_validate(capture_fixture)
    LearningState.model_validate(state_fixture)
    QuizSubmitRequest.model_validate(quiz_fixture)

    required_keys = state_schema.get("required", [])
    missing = [key for key in required_keys if key not in state_fixture]
    if missing:
        raise SystemExit(f"State fixture missing required keys from schema: {missing}")

    summary = {
        "ok": True,
        "validated": [
            "fixtures/capture-request.v1.json",
            "fixtures/state-response.v1.json",
            "fixtures/quiz-submit.v1.json",
        ],
        "state_required_keys_checked": required_keys,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
