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


def build_user_prompt(extracted_text: str, summary: str, tags: list[str]) -> str:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return (
        f"Timestamp: {now}\n"
        f"Vision summary: {summary}\n"
        f"Detected tags: {', '.join(tags) if tags else 'none'}\n"
        f"OCR text:\n{extracted_text}\n\n"
        "Return strict JSON with fields:"
        " socratic_prompt (string),"
        " gaps (array of objects with concept, severity, confidence)."
        " Keep severity/confidence in [0,1]."
    )
