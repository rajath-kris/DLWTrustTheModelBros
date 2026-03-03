from __future__ import annotations

import json
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


def build_system_prompt(syllabus: dict, grounding_sources: list[str] | None = None) -> str:
    sources_value = _compact_sources(grounding_sources)
    return (
        "You are Sentinel AI, a Socratic tutor. "
        "Do not provide direct final answers, completed derivations, or final numeric results. "
        "Ask one concise, high-leverage question that advances reasoning. "
        "For follow-up turns that include a learner response, briefly acknowledge the response first, then ask one guiding question. "
        "When grounding context exists, make the question specific to the uploaded material by referencing one concrete term, equation, or section cue from that context. "
        "Do not mention source names, file names, citations, or material labels in socratic_prompt text. "
        "If the learner asks for the answer, redirect with a guiding question instead. "
        "Keep all interpretation and gap detection inside the syllabus anchor. "
        "Use grounding context from uploaded materials when relevant, but do not invent facts. "
        "Preserve mathematical and physics notation when present (for example: \u222b, \u2211, \u03bb, \u03b8, e^{-st}, x^2, x\u00b2, 10^-3, m/s^2, F=ma, d/dx). "
        "If you reference an equation from context, keep exponents, subscripts, symbols, and operators intact. "
        "Return strict JSON only with keys socratic_prompt and gaps. "
        "Each gap must include concept, severity, confidence with severity/confidence in [0,1]."
        "\n\n"
        "Gap extraction policy: when a learner response exists, infer gaps from the evidence path "
        "(previous Socratic prompt + learner response + OCR context). "
        "When no learner response exists, infer preliminary gaps from OCR and visual summary only."
        "\n\n"
        f"GROUNDING_SOURCES: {sources_value}\n\n"
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
    grounding_context: str | None = None,
    grounding_sources: list[str] | None = None,
) -> str:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous_prompt_value = _compact_text(previous_prompt, _MAX_PREVIOUS_PROMPT_CHARS, "none")
    user_input_value = _compact_text(user_input_text, _MAX_LEARNER_REPLY_CHARS, "none")
    thread_value = _compact_text(thread_id, 80, "none")
    summary_value = _compact_text(summary, _MAX_SUMMARY_CHARS, "none")
    ocr_value = _compact_text(extracted_text, _MAX_OCR_CHARS, "none")
    grounding_value = _compact_text(grounding_context, _MAX_GROUNDING_CHARS, "none")
    grounding_sources_value = _compact_sources(grounding_sources)
    has_learner_response = user_input_value != "none"

    turn_mode = "follow_up" if has_learner_response else "first_turn"
    turn_instruction = (
        "Use the previous Socratic prompt and learner response as primary evidence for gap extraction. "
        "Briefly acknowledge the learner response, then ask one guiding question that probes the reasoning weakness. "
        "Anchor the follow-up question to a concrete clue from grounding context or detected tags so it is specific to the uploaded material. "
        "Do not cite or name any source/material inside the socratic prompt text. "
        "Do not provide the solution."
        if has_learner_response
        else (
            "Ask a first diagnostic Socratic question based on OCR/summary without giving any solution steps. "
            "Do not cite or name any source/material inside the socratic prompt text."
        )
    )

    return (
        f"Timestamp: {now}\n"
        f"Thread id: {thread_value}\n"
        f"Turn index: {max(0, int(turn_index))}\n"
        f"Turn mode: {turn_mode}\n"
        f"Vision summary: {summary_value}\n"
        f"Detected tags: {_compact_tags(tags)}\n"
        f"Previous Socratic prompt: {previous_prompt_value}\n"
        f"Learner response: {user_input_value}\n"
        f"OCR text: {ocr_value}\n\n"
        f"Grounding sources: {grounding_sources_value}\n"
        f"Grounding context: {grounding_value}\n\n"
        f"Instruction: {turn_instruction}\n"
        "Return strict JSON with fields: "
        "socratic_prompt (string), gaps (array of objects with concept, severity, confidence)."
    )


def build_ask_system_prompt(syllabus: dict, grounding_sources: list[str] | None = None) -> str:
    sources_value = _compact_sources(grounding_sources)
    return (
        "You are Sentinel AI, a Socratic tutor. "
        "Respond with one concise Socratic question only. "
        "Do not provide direct final answers. "
        "Preserve mathematical/physics notation when relevant, including exponents and subscripts."
        "\n\n"
        f"GROUNDING_SOURCES: {sources_value}\n\n"
        "Stay inside the syllabus anchor and avoid out-of-scope concepts."
        "\n\n"
        "SYLLABUS_ANCHOR:\n"
        f"{json.dumps(syllabus, indent=2)}"
    )


def build_ask_user_prompt(
    *,
    message: str,
    thread_id: str,
    turn_index: int,
    course_id: str,
    grounding_context: str | None = None,
) -> str:
    cleaned_message = _compact_text(message, 900, "Help me understand this topic.")
    grounding_value = _compact_text(grounding_context, _MAX_GROUNDING_CHARS, "none")
    return (
        f"Course id: {course_id}\n"
        f"Thread id: {thread_id}\n"
        f"Turn index: {max(0, int(turn_index))}\n"
        f"Learner message: {cleaned_message}\n"
        f"Grounding context: {grounding_value}\n"
        "Return only the next Socratic question."
    )
