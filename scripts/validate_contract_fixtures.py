#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_ROOT = REPO_ROOT / "services" / "bridge-api"
sys.path.insert(0, str(BRIDGE_ROOT))

from app.models import (  # noqa: E402
    CaptureRequest,
    LearningState,
    QuizSubmissionRequest,
    QuizSubmissionResponse,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_schema_required_keys(state_payload: dict) -> None:
    schema_path = REPO_ROOT / "shared" / "schemas" / "learning-state.schema.json"
    schema = load_json(schema_path)
    required = schema.get("required", [])
    missing = [key for key in required if key not in state_payload]
    if missing:
        raise AssertionError(f"state-response.v1.json missing required keys from schema: {missing}")


def main() -> int:
    fixtures_dir = REPO_ROOT / "fixtures"

    capture_fixture = load_json(fixtures_dir / "capture-request.v1.json")
    state_fixture = load_json(fixtures_dir / "state-response.v1.json")
    quiz_fixture = load_json(fixtures_dir / "quiz-submit.v1.json")

    CaptureRequest.model_validate(capture_fixture)
    LearningState.model_validate(state_fixture)
    QuizSubmissionRequest.model_validate(quiz_fixture["request"])
    QuizSubmissionResponse.model_validate(quiz_fixture["response"])

    assert_schema_required_keys(state_fixture)

    print(
        json.dumps(
            {
                "ok": True,
                "validated": [
                    "fixtures/capture-request.v1.json",
                    "fixtures/state-response.v1.json",
                    "fixtures/quiz-submit.v1.json",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
