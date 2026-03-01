from __future__ import annotations

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


class AzureVisionClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(self, image_bytes: bytes) -> VisionExtraction:
        endpoint = self._settings.azure_vision_endpoint
        key = self._settings.azure_vision_key
        if not endpoint or not key:
            return VisionExtraction(
                raw_text="No Azure Vision credentials configured.",
                summary="Captured study content awaiting cloud interpretation.",
                tags=["capture", "unparsed"],
            )

        url = f"{endpoint.rstrip('/')}/computervision/imageanalysis:analyze"
        params = {
            "api-version": "2024-02-01",
            "features": "read,caption,tags",
            "language": "en",
        }
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/octet-stream",
        }

        try:
            response = requests.post(
                url,
                params=params,
                headers=headers,
                data=image_bytes,
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return VisionExtraction(
                raw_text=f"Vision request failed: {exc}",
                summary="Could not parse visual content from Azure Vision.",
                tags=["vision-error"],
            )

        caption = payload.get("captionResult", {}).get("text", "")
        tags = [item.get("name", "") for item in payload.get("tagsResult", {}).get("values", []) if item.get("name")]

        lines: list[str] = []
        for block in payload.get("readResult", {}).get("blocks", []):
            for line in block.get("lines", []):
                text = line.get("text", "").strip()
                if text:
                    lines.append(text)

        return VisionExtraction(
            raw_text="\n".join(lines) if lines else "No text detected.",
            summary=caption or "No caption detected.",
            tags=tags,
        )


class AzureSocraticClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, capture: CaptureRequest, extraction: VisionExtraction, syllabus: dict) -> SocraticOutput:
        endpoint = self._settings.azure_openai_endpoint
        key = self._settings.azure_openai_key
        deployment = self._settings.azure_openai_deployment

        fallback = self._fallback_output(capture, extraction)
        if not endpoint or not key or not deployment:
            return fallback

        url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._settings.azure_openai_api_version}"
        )
        headers = {
            "api-key": key,
            "Content-Type": "application/json",
        }

        system_prompt = build_system_prompt(syllabus)
        user_prompt = build_user_prompt(
            extraction.raw_text,
            extraction.summary,
            extraction.tags,
            previous_prompt=capture.previous_prompt,
            user_input_text=capture.user_input_text,
            thread_id=capture.thread_id,
            turn_index=capture.turn_index,
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 400,
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            blob = _extract_json_blob(content)
            if not blob:
                return fallback

            prompt = str(blob.get("socratic_prompt", "")).strip() or fallback.socratic_prompt
            gaps = blob.get("gaps", [])
            if not isinstance(gaps, list):
                gaps = fallback.gaps

            cleaned_gaps: list[dict[str, Any]] = []
            for gap in gaps:
                if not isinstance(gap, dict):
                    continue
                concept = str(gap.get("concept", "")).strip()
                if not concept:
                    continue
                severity = float(gap.get("severity", 0.5))
                confidence = float(gap.get("confidence", 0.6))
                cleaned_gaps.append(
                    {
                        "concept": concept,
                        "severity": max(0.0, min(1.0, severity)),
                        "confidence": max(0.0, min(1.0, confidence)),
                    }
                )
            return SocraticOutput(socratic_prompt=prompt, gaps=cleaned_gaps or fallback.gaps)
        except Exception:
            return fallback

    def _fallback_output(self, capture: CaptureRequest, extraction: VisionExtraction) -> SocraticOutput:
        seed_concept = "Concept interpretation"
        if extraction.tags:
            seed_concept = extraction.tags[0].replace("_", " ").title()
        learner_reply = (capture.user_input_text or "").strip()
        if learner_reply:
            prompt = (
                "What assumption in your last response is strongest, and which one needs evidence?"
            )
        else:
            prompt = (
                "What is the first principle behind this section, and how would you explain it "
                "in one sentence before solving anything?"
            )
        return SocraticOutput(
            socratic_prompt=prompt,
            gaps=[
                {
                    "concept": seed_concept,
                    "severity": 0.58,
                    "confidence": 0.62,
                }
            ],
        )
