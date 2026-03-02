from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from .config import Settings
from .models import CaptureRequest, VisionExtraction
from .prompting import build_system_prompt, build_user_prompt


@dataclass
class SocraticOutput:
    socratic_prompt: str
    gaps: list[dict[str, Any]]


def _extract_json_blob(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _normalize_text(value: object, max_chars: int = 280) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    return text[:max_chars]


def _normalize_gap_type(raw_value: object) -> str | None:
    value = _normalize_text(raw_value, max_chars=32)
    if value is None:
        return None
    lowered = value.lower()
    if lowered in {"concept", "reasoning", "misconception"}:
        return lowered
    return None


def _to_float(raw_value: object, default: float) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


class _OpenAIChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return bool(self._settings.openai_api_key and self._settings.openai_base_url and self._settings.openai_model)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes | None = None,
        temperature: float = 0.3,
        max_tokens: int = 400,
    ) -> str | None:
        if not self.configured:
            return None

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        if image_bytes is not None:
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                }
            )

        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                f"{self._settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
        except Exception:
            return None
        return None


class OpenAIVisionClient:
    def __init__(self, settings: Settings) -> None:
        self._chat_client = _OpenAIChatClient(settings)

    def extract(self, image_bytes: bytes) -> VisionExtraction:
        if not self._chat_client.configured:
            return VisionExtraction(
                raw_text="No OpenAI API key configured.",
                summary="Captured study content awaiting cloud interpretation.",
                tags=["capture", "unparsed"],
            )

        system_prompt = (
            "Extract study context from a screenshot. "
            "Return strict JSON only: "
            "{\"raw_text\":\"...\",\"summary\":\"...\",\"tags\":[\"...\"]}. "
            "raw_text should contain OCR-like text when visible. "
            "summary should be one concise sentence. "
            "tags should be 2-8 short topic tags. "
            "If text is not readable, set raw_text to \"No text detected.\"."
        )
        user_prompt = "Analyze this screenshot and return the JSON object."
        content = self._chat_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=image_bytes,
            temperature=0.1,
            max_tokens=350,
        )
        if not content:
            return VisionExtraction(
                raw_text="No text detected.",
                summary="Could not parse visual content from OpenAI Vision.",
                tags=["vision-error"],
            )

        blob = _extract_json_blob(content)
        if not blob:
            return VisionExtraction(
                raw_text="No text detected.",
                summary="Could not parse visual content from OpenAI Vision.",
                tags=["vision-error"],
            )

        raw_text = _normalize_text(blob.get("raw_text"), max_chars=6000) or "No text detected."
        summary = _normalize_text(blob.get("summary"), max_chars=500) or "No caption detected."
        raw_tags = blob.get("tags", [])
        tags: list[str] = []
        if isinstance(raw_tags, list):
            for item in raw_tags:
                normalized = _normalize_text(item, max_chars=40)
                if normalized:
                    tags.append(normalized.lower())
        if not tags:
            tags = ["capture", "unparsed"]

        return VisionExtraction(raw_text=raw_text, summary=summary, tags=tags[:8])


class OpenAISocraticClient:
    def __init__(self, settings: Settings) -> None:
        self._chat_client = _OpenAIChatClient(settings)

    def generate(self, capture: CaptureRequest, extraction: VisionExtraction, syllabus: dict) -> SocraticOutput:
        fallback = self._fallback_output(capture, extraction)
        content = self._chat_client.complete(
            system_prompt=build_system_prompt(syllabus),
            user_prompt=build_user_prompt(
                extraction.raw_text,
                extraction.summary,
                extraction.tags,
                previous_prompt=capture.previous_prompt,
                user_input_text=capture.user_input_text,
                thread_id=capture.thread_id,
                turn_index=capture.turn_index,
            ),
            max_tokens=420,
        )
        if content is None:
            return fallback
        return self._parse_socratic_output(content, fallback)

    def _parse_socratic_output(self, content: str, fallback: SocraticOutput) -> SocraticOutput:
        blob = _extract_json_blob(content)
        if not blob:
            return fallback

        prompt = _normalize_text(blob.get("socratic_prompt"), max_chars=500) or fallback.socratic_prompt
        raw_gaps = blob.get("gaps", [])
        if not isinstance(raw_gaps, list):
            return SocraticOutput(socratic_prompt=prompt, gaps=fallback.gaps)

        cleaned_gaps: list[dict[str, Any]] = []
        for gap in raw_gaps:
            if not isinstance(gap, dict):
                continue
            concept = _normalize_text(gap.get("concept"), max_chars=160)
            if not concept:
                continue
            severity = max(0.0, min(1.0, _to_float(gap.get("severity"), 0.5)))
            confidence = max(0.0, min(1.0, _to_float(gap.get("confidence"), 0.6)))
            cleaned: dict[str, Any] = {
                "concept": concept,
                "severity": severity,
                "confidence": confidence,
            }
            basis_question = _normalize_text(gap.get("basis_question"), max_chars=320)
            if basis_question is not None:
                cleaned["basis_question"] = basis_question
            basis_answer_excerpt = _normalize_text(gap.get("basis_answer_excerpt"), max_chars=320)
            if basis_answer_excerpt is not None:
                cleaned["basis_answer_excerpt"] = basis_answer_excerpt
            gap_type = _normalize_gap_type(gap.get("gap_type"))
            if gap_type is not None:
                cleaned["gap_type"] = gap_type
            cleaned_gaps.append(cleaned)
        return SocraticOutput(socratic_prompt=prompt, gaps=cleaned_gaps or fallback.gaps)

    def _fallback_output(self, capture: CaptureRequest, extraction: VisionExtraction) -> SocraticOutput:
        seed_concept = "Concept interpretation"
        if extraction.tags:
            seed_concept = extraction.tags[0].replace("_", " ").title()

        learner_reply = (capture.user_input_text or "").strip()
        if learner_reply:
            prompt = "What assumption in your last response is strongest, and which one needs evidence?"
            basis_answer_excerpt = _normalize_text(learner_reply, max_chars=320)
        else:
            prompt = (
                "What is the first principle behind this section, and how would you explain it "
                "in one sentence before solving anything?"
            )
            basis_answer_excerpt = None

        gap: dict[str, Any] = {
            "concept": seed_concept,
            "severity": 0.58,
            "confidence": 0.62,
            "basis_question": prompt,
            "gap_type": "reasoning",
        }
        if basis_answer_excerpt is not None:
            gap["basis_answer_excerpt"] = basis_answer_excerpt

        return SocraticOutput(socratic_prompt=prompt, gaps=[gap])
