from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import Settings
from .models import VisionExtraction

_RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_BASE_RETRY_DELAY_SECONDS = 0.8
_MAX_RETRY_DELAY_SECONDS = 2.0


@dataclass
class TopicPickerOutput:
    topic_id: str
    confidence: float
    reason: str | None = None


@dataclass
class OpenAIFallbackOutput:
    socratic_prompt: str
    fallback_reason: str | None = None


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


def _to_float(raw_value: object, default: float) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


class _OpenAIChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._last_failure_reason: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self._settings.openai_api_key and self._settings.openai_base_url and self._settings.openai_model)

    @property
    def last_failure_reason(self) -> str | None:
        return self._last_failure_reason

    def _request(self, payload: dict[str, Any]) -> str | None:
        self._last_failure_reason = None
        if not self.configured:
            self._last_failure_reason = "not_configured"
            return None

        retry_delay_seconds = _BASE_RETRY_DELAY_SECONDS
        for attempt_index in range(_MAX_RETRIES):
            is_last_attempt = attempt_index >= (_MAX_RETRIES - 1)
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
                if response.status_code in _RETRIABLE_STATUS_CODES:
                    if is_last_attempt:
                        self._last_failure_reason = f"http_{response.status_code}"
                        return None
                    time.sleep(retry_delay_seconds)
                    retry_delay_seconds = min(_MAX_RETRY_DELAY_SECONDS, retry_delay_seconds * 1.8)
                    continue

                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if isinstance(content, str):
                    self._last_failure_reason = None
                    return content
                if isinstance(content, list):
                    self._last_failure_reason = None
                    return "\n".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                self._last_failure_reason = "invalid_response_content"
                return None
            except (requests.Timeout, requests.ConnectionError):
                if is_last_attempt:
                    self._last_failure_reason = "timeout_or_connection_error"
                    return None
                time.sleep(retry_delay_seconds)
                retry_delay_seconds = min(_MAX_RETRY_DELAY_SECONDS, retry_delay_seconds * 1.8)
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code in _RETRIABLE_STATUS_CODES and not is_last_attempt:
                    time.sleep(retry_delay_seconds)
                    retry_delay_seconds = min(_MAX_RETRY_DELAY_SECONDS, retry_delay_seconds * 1.8)
                    continue
                self._last_failure_reason = f"http_{status_code}" if status_code is not None else "http_error"
                return None
            except Exception:
                self._last_failure_reason = "unexpected_client_error"
                return None
        self._last_failure_reason = "retry_exhausted"
        return None

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes | None = None,
        temperature: float = 0.3,
        max_tokens: int = 400,
    ) -> str | None:
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
        return self._request(payload)

    def complete_user_only(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 220,
    ) -> str | None:
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._request(payload)


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
            "raw_text should contain OCR-like text when visible, preserving equation symbols and operators exactly. "
            "Keep notation like integrals, summations, greek letters, superscripts/subscripts, scientific notation, vectors, and fractions in plain text form. "
            "Preserve exponent forms such as x^2, x², 10^-3, and e^{-st} without rewriting their meaning. "
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


class OpenAIPlainFallbackClient:
    def __init__(self, settings: Settings) -> None:
        self._chat_client = _OpenAIChatClient(settings)
        self.last_failure_reason: str | None = None

    def generate(self, *, prompt_text: str) -> OpenAIFallbackOutput:
        content = self._chat_client.complete_user_only(
            user_prompt=prompt_text,
            temperature=0.3,
            max_tokens=220,
        )
        if content is None:
            self.last_failure_reason = self._chat_client.last_failure_reason or "llm_unavailable"
            return OpenAIFallbackOutput(
                socratic_prompt="What step in your current reasoning needs the most evidence?",
                fallback_reason=self.last_failure_reason,
            )
        cleaned = _normalize_text(content, max_chars=500)
        if not cleaned:
            self.last_failure_reason = "empty_response"
            return OpenAIFallbackOutput(
                socratic_prompt="What step in your current reasoning needs the most evidence?",
                fallback_reason=self.last_failure_reason,
            )
        self.last_failure_reason = None
        return OpenAIFallbackOutput(socratic_prompt=cleaned, fallback_reason=None)


class OpenAITopicPickerClient:
    def __init__(self, settings: Settings) -> None:
        self._chat_client = _OpenAIChatClient(settings)

    @property
    def configured(self) -> bool:
        return self._chat_client.configured

    def pick_topic(
        self,
        *,
        signal_text: str,
        signal_tags: list[str],
        topic_options: list[dict[str, str]],
        min_confidence: float,
    ) -> TopicPickerOutput | None:
        if not self._chat_client.configured:
            return None

        normalized_options: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in topic_options:
            topic_id = _normalize_text(item.get("topic_id"), max_chars=80)
            topic_name = _normalize_text(item.get("topic_name"), max_chars=140)
            if topic_id is None or topic_name is None:
                continue
            topic_key = topic_id.strip().lower()
            if topic_key in seen:
                continue
            seen.add(topic_key)
            normalized_options.append({"topic_id": topic_id, "topic_name": topic_name})

        if not normalized_options:
            return None

        safe_signal_text = _normalize_text(signal_text, max_chars=2200) or ""
        compact_tags = [tag for tag in (_normalize_text(item, max_chars=40) for item in signal_tags) if tag]
        system_prompt = (
            "You classify a student capture into one existing topic. "
            "Return strict JSON only with keys: topic_id, confidence, reason. "
            "topic_id must be one of the provided candidate topic_ids. "
            "confidence must be a number between 0 and 1."
        )
        user_prompt = (
            "Student capture signal:\n"
            f"text: {safe_signal_text or '[empty]'}\n"
            f"tags: {', '.join(compact_tags) if compact_tags else '[none]'}\n"
            f"candidate_topics: {json.dumps(normalized_options, ensure_ascii=True)}\n"
            "Pick the best candidate topic_id. If uncertain, use lower confidence."
        )
        content = self._chat_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=180,
        )
        if content is None:
            return None

        blob = _extract_json_blob(content)
        if not isinstance(blob, dict):
            return None

        topic_id = _normalize_text(blob.get("topic_id"), max_chars=80)
        if topic_id is None:
            return None

        allowed_ids = {item["topic_id"].strip().lower() for item in normalized_options}
        normalized_topic_id = topic_id.strip().lower()
        if normalized_topic_id not in allowed_ids:
            return None

        confidence = max(0.0, min(1.0, _to_float(blob.get("confidence"), 0.0)))
        if confidence < max(0.0, min(1.0, float(min_confidence))):
            return None

        reason = _normalize_text(blob.get("reason"), max_chars=260)
        return TopicPickerOutput(topic_id=topic_id, confidence=confidence, reason=reason)
