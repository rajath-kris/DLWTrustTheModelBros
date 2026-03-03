from __future__ import annotations

from datetime import datetime, timezone

_MAX_OCR_CHARS = 2400
_MAX_SUMMARY_CHARS = 480
_MAX_PREVIOUS_PROMPT_CHARS = 380
_MAX_LEARNER_REPLY_CHARS = 600
_MAX_TAGS = 12
_MAX_GROUNDING_CHARS = 5200
_MAX_GROUNDING_SOURCES = 12


def _compact_text(value: str | None, max_chars: int, empty_fallback: str) -> str:
    if not value:
        return empty_fallback
    normalized = " ".join(value.split())
    if not normalized:
        return empty_fallback
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."


def _compact_tags(tags: list[str]) -> str:
    if not tags:
        return "none"
    cleaned = [" ".join(tag.split()) for tag in tags if tag and tag.strip()]
    if not cleaned:
        return "none"
    return ", ".join(cleaned[:_MAX_TAGS])


def _compact_sources(sources: list[str] | None) -> str:
    if not sources:
        return "none"
    cleaned = [" ".join(source.split()) for source in sources if source and source.strip()]
    if not cleaned:
        return "none"
    return ", ".join(cleaned[:_MAX_GROUNDING_SOURCES])


def build_scoratic_capture_input(
    *,
    extracted_text: str,
    summary: str,
    tags: list[str],
    previous_prompt: str | None = None,
    user_input_text: str | None = None,
    thread_id: str | None = None,
    turn_index: int = 0,
    grounding_context: str | None = None,
    grounding_sources: list[str] | None = None,
) -> str:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous_prompt_value = _compact_text(previous_prompt, _MAX_PREVIOUS_PROMPT_CHARS, "none")
    user_input_value = _compact_text(user_input_text, _MAX_LEARNER_REPLY_CHARS, "none")
    summary_value = _compact_text(summary, _MAX_SUMMARY_CHARS, "none")
    ocr_value = _compact_text(extracted_text, _MAX_OCR_CHARS, "none")
    grounding_value = _compact_text(grounding_context, _MAX_GROUNDING_CHARS, "none")
    grounding_sources_value = _compact_sources(grounding_sources)
    thread_value = _compact_text(thread_id, 80, "none")

    return (
        f"Timestamp: {timestamp}\n"
        f"Thread id: {thread_value}\n"
        f"Turn index: {max(0, int(turn_index))}\n"
        f"Vision summary: {summary_value}\n"
        f"Detected tags: {_compact_tags(tags)}\n"
        f"Previous prompt: {previous_prompt_value}\n"
        f"Learner response: {user_input_value}\n"
        f"OCR text: {ocr_value}\n"
        f"Grounding sources: {grounding_sources_value}\n"
        f"Grounding context: {grounding_value}\n"
    )


def build_plain_openai_fallback_input(
    *,
    extracted_text: str,
    summary: str,
    tags: list[str],
    previous_prompt: str | None = None,
    user_input_text: str | None = None,
    thread_id: str | None = None,
    turn_index: int = 0,
    grounding_context: str | None = None,
) -> str:
    summary_value = _compact_text(summary, _MAX_SUMMARY_CHARS, "none")
    ocr_value = _compact_text(extracted_text, _MAX_OCR_CHARS, "none")
    user_input_value = _compact_text(user_input_text, _MAX_LEARNER_REPLY_CHARS, "none")
    previous_prompt_value = _compact_text(previous_prompt, _MAX_PREVIOUS_PROMPT_CHARS, "none")
    grounding_value = _compact_text(grounding_context, _MAX_GROUNDING_CHARS, "none")
    thread_value = _compact_text(thread_id, 80, "none")
    return (
        f"Thread: {thread_value}\n"
        f"Turn: {max(0, int(turn_index))}\n"
        f"Summary: {summary_value}\n"
        f"Tags: {_compact_tags(tags)}\n"
        f"OCR: {ocr_value}\n"
        f"Previous prompt: {previous_prompt_value}\n"
        f"Learner response: {user_input_value}\n"
        f"Grounding: {grounding_value}"
    )
