from __future__ import annotations

import re


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


def normalize_tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    tokens = _TOKEN_PATTERN.findall(lowered)
    return [token for token in tokens if token and token not in _STOPWORDS]


def build_material_tokens(material_text: str, material_name: str, tags: list[str] | None = None) -> dict[str, list[str]]:
    text_tokens = normalize_tokens(material_text)
    tag_seed = " ".join(tags or [])
    tag_tokens = normalize_tokens(f"{material_name} {tag_seed}")
    return {
        "text_tokens": sorted(set(text_tokens)),
        "tag_tokens": sorted(set(tag_tokens)),
    }


def score_capture_against_material(
    capture_text: str,
    capture_tags: list[str],
    material_text_tokens: list[str],
    material_tag_tokens: list[str],
) -> float:
    capture_tokens = set(normalize_tokens(capture_text))
    material_tokens = set(material_text_tokens)
    capture_tag_tokens = set(normalize_tokens(" ".join(capture_tags)))
    material_tags = set(material_tag_tokens)

    text_overlap = len(capture_tokens & material_tokens) / max(1, len(capture_tokens))
    tag_overlap = len(capture_tag_tokens & material_tags) / max(1, len(capture_tag_tokens))
    score = (text_overlap * 0.7) + (tag_overlap * 0.3)
    return max(0.0, min(1.0, score))

