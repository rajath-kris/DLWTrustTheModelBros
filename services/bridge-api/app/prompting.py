from __future__ import annotations

import json
from datetime import datetime, timezone


def build_system_prompt(syllabus: dict) -> str:
    return (
        "You are Sentinel AI, a Socratic tutor. "
        "Never provide direct final answers. "
        "Ask concise guided questions that help the learner reason. "
        "All gap detection must remain within the syllabus anchor.\n\n"
        "SYLLABUS_ANCHOR:\n"
        f"{json.dumps(syllabus, indent=2)}"
    )


def build_user_prompt(
    extracted_text: str,
    summary: str,
    tags: list[str],
    previous_prompt: str | None = None,
    user_input_text: str | None = None,
    thread_id: str | None = None,
    turn_index: int = 0,
) -> str:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous_prompt_value = previous_prompt.strip() if previous_prompt else "none"
    user_input_value = user_input_text.strip() if user_input_text else "none"
    thread_value = thread_id.strip() if thread_id else "none"
    return (
        f"Timestamp: {now}\n"
        f"Thread id: {thread_value}\n"
        f"Turn index: {max(0, int(turn_index))}\n"
        f"Vision summary: {summary}\n"
        f"Detected tags: {', '.join(tags) if tags else 'none'}\n"
        f"Previous Socratic prompt: {previous_prompt_value}\n"
        f"Learner response: {user_input_value}\n"
        f"OCR text:\n{extracted_text}\n\n"
        "Return strict JSON with fields:"
        " socratic_prompt (string),"
        " gaps (array of objects with concept, severity, confidence)."
        " Keep the next prompt Socratic and dependent on the learner response when provided."
        " Keep severity/confidence in [0,1]."
    )
