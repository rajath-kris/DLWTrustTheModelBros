from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


@dataclass
class GroundingBundle:
    context_text: str
    citations: list[str]
    warnings: list[str]


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall((text or "").lower())
    normalized: list[str] = []
    for token in tokens:
        if token.endswith("s") and len(token) > 3:
            token = token[:-1]
        normalized.append(token)
    return normalized


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 140) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for index in range(0, len(text), step):
        chunk = text[index : index + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks or [text]


def select_top_chunks(query_text: str, chunks: list[str], limit: int = 3) -> list[str]:
    if not chunks or limit <= 0:
        return []

    query_tokens = set(tokenize(query_text))
    if not query_tokens:
        return chunks[:limit]

    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        chunk_tokens = set(tokenize(chunk))
        score = len(query_tokens & chunk_tokens)
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)

    top = [chunk for score, chunk in scored[:limit] if score > 0]
    if not top:
        return chunks[:limit]
    return top


def extract_supported_text(path: Path) -> tuple[str, str | None]:
    extension = path.suffix.lower()
    if extension in {".txt", ".md"}:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as exc:  # noqa: BLE001
            return "No text detected.", f"Text read failure: {type(exc).__name__}"
        if text:
            return text, None
        return "No text detected.", "Text file is empty after decoding."

    if extension == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except Exception:
            return "No text detected.", "PDF extraction unavailable because 'pypdf' is not installed."

        try:
            reader = PdfReader(str(path))
            parts: list[str] = []
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    parts.append(page_text)
            text = "\n".join(parts).strip()
            if text:
                return text, None
            return "No text detected.", "PDF parsed but no extractable text was found."
        except Exception as exc:  # noqa: BLE001
            return "No text detected.", f"PDF parse failure: {type(exc).__name__}"

    return "No text detected.", f"Unsupported document type for grounding: {extension or '(none)'}"
