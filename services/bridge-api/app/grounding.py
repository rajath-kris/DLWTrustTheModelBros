from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


_WORD_PATTERN = re.compile(r"[^\W_]+(?:_[^\W_]+)?", re.UNICODE)
_MATH_EXPRESSION_PATTERN = re.compile(
    r"[A-Za-z0-9\u0370-\u03FF][A-Za-z0-9\u0370-\u03FF(){}\[\].,_]*"
    r"(?:\s*(?:\^|[*/+\-=<>!~]+)\s*[A-Za-z0-9\u0370-\u03FF(){}\[\].,_^*/+\-]+)+",
    re.UNICODE,
)
_MATH_SYMBOL_PATTERN = re.compile(r"(<=|>=|!=|~=|<->|->|<-|[+\-*/^=<>])")

_SUPERSCRIPT_TO_ASCII = {
    "\u2070": "0",
    "\u00b9": "1",
    "\u00b2": "2",
    "\u00b3": "3",
    "\u2074": "4",
    "\u2075": "5",
    "\u2076": "6",
    "\u2077": "7",
    "\u2078": "8",
    "\u2079": "9",
    "\u207a": "+",
    "\u207b": "-",
}
_SUBSCRIPT_TO_ASCII = {
    "\u2080": "0",
    "\u2081": "1",
    "\u2082": "2",
    "\u2083": "3",
    "\u2084": "4",
    "\u2085": "5",
    "\u2086": "6",
    "\u2087": "7",
    "\u2088": "8",
    "\u2089": "9",
    "\u208a": "+",
    "\u208b": "-",
}
_SUPERSCRIPT_PATTERN = re.compile("[" + re.escape("".join(_SUPERSCRIPT_TO_ASCII.keys())) + "]+")
_SUBSCRIPT_PATTERN = re.compile("[" + re.escape("".join(_SUBSCRIPT_TO_ASCII.keys())) + "]+")

_UNICODE_OPERATOR_TRANSLATION = str.maketrans(
    {
        "\u00d7": "*",
        "\u00f7": "/",
        "\u22c5": "*",
        "\u00b7": "*",
        "\u2212": "-",
        "\u2215": "/",
        "\u2044": "/",
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2248": "~=",
        "\u2260": "!=",
        "\u2192": "->",
        "\u2190": "<-",
        "\u2194": "<->",
    }
)

_GREEK_ALIAS_MAP = {
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u03b5": "epsilon",
    "\u03b6": "zeta",
    "\u03b7": "eta",
    "\u03b8": "theta",
    "\u03bb": "lambda",
    "\u03bc": "mu",
    "\u03bd": "nu",
    "\u03c0": "pi",
    "\u03c1": "rho",
    "\u03c3": "sigma",
    "\u03c4": "tau",
    "\u03c6": "phi",
    "\u03c7": "chi",
    "\u03c8": "psi",
    "\u03c9": "omega",
    "\u0394": "delta",
    "\u2202": "partial",
    "\u2207": "nabla",
}

_WORD_ALIAS_MAP = {
    "squared": "^2",
    "cubed": "^3",
    "square": "^2",
    "cube": "^3",
    "integral": "int",
    "summation": "sum",
    "derivative": "d/dx",
    "gradient": "nabla",
}


def _normalize_math_expression(text: str) -> str:
    collapsed = re.sub(r"\s+", "", text)
    return re.sub(r"^[,.;:]+|[,.;:]+$", "", collapsed)


def _translate_script_sequence(value: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(char, char) for char in value)


def _replace_unicode_script_tokens(text: str) -> str:
    replaced = _SUPERSCRIPT_PATTERN.sub(
        lambda match: f"^{_translate_script_sequence(match.group(0), _SUPERSCRIPT_TO_ASCII)}",
        text,
    )
    replaced = _SUBSCRIPT_PATTERN.sub(
        lambda match: f"_{_translate_script_sequence(match.group(0), _SUBSCRIPT_TO_ASCII)}",
        replaced,
    )
    return replaced


def _normalize_math_text(text: str) -> str:
    normalized = text.translate(_UNICODE_OPERATOR_TRANSLATION)
    normalized = _replace_unicode_script_tokens(normalized)
    normalized = normalized.replace("\u00a0", " ")
    return normalized


def _append_token(token: str, normalized: list[str], seen: set[str]) -> None:
    if not token:
        return
    if token in seen:
        return
    seen.add(token)
    normalized.append(token)


def _append_expression_and_variants(expression: str, normalized: list[str], seen: set[str]) -> None:
    clean = _normalize_math_expression(expression)
    if not clean:
        return
    _append_token(clean, normalized, seen)
    compact = clean.replace("{", "").replace("}", "")
    if compact != clean:
        _append_token(compact, normalized, seen)
    without_underscores = clean.replace("_", "")
    if without_underscores != clean:
        _append_token(without_underscores, normalized, seen)


def _append_greek_aliases(value: str, normalized: list[str], seen: set[str]) -> None:
    for char in value:
        alias = _GREEK_ALIAS_MAP.get(char)
        if alias:
            _append_token(alias, normalized, seen)


@dataclass
class GroundingBundle:
    context_text: str
    citations: list[str]
    warnings: list[str]
    primary_source_url: str | None = None
    primary_source_label: str | None = None
    primary_source_score: int = 0


def tokenize(text: str) -> list[str]:
    raw_value = (text or "").lower()
    value = _normalize_math_text(raw_value)
    normalized: list[str] = []
    seen: set[str] = set()

    for expression in _MATH_EXPRESSION_PATTERN.findall(value):
        _append_expression_and_variants(expression, normalized, seen)

    for token in _WORD_PATTERN.findall(value):
        clean = token
        if clean.isascii() and clean.isalpha() and clean.endswith("s") and len(clean) > 3:
            clean = clean[:-1]
        _append_token(clean, normalized, seen)
        alias = _WORD_ALIAS_MAP.get(clean)
        if alias:
            _append_token(alias, normalized, seen)

    for symbol in _MATH_SYMBOL_PATTERN.findall(value):
        _append_token(symbol, normalized, seen)

    _append_greek_aliases(raw_value, normalized, seen)
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
        return []

    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        chunk_tokens = set(tokenize(chunk))
        score = len(query_tokens & chunk_tokens)
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)

    return [chunk for score, chunk in scored[:limit] if score > 0]


def _extract_zip_xml_text(
    path: Path,
    *,
    member_prefixes: tuple[str, ...],
    text_tag_names: set[str],
    source_label: str,
) -> tuple[str, str | None]:
    try:
        archive = zipfile.ZipFile(path)
    except Exception as exc:  # noqa: BLE001
        return "No text detected.", f"{source_label} parse failure: {type(exc).__name__}"

    with archive:
        xml_members = [
            name
            for name in archive.namelist()
            if name.endswith(".xml") and any(name.startswith(prefix) for prefix in member_prefixes)
        ]
        if not xml_members:
            return "No text detected.", f"{source_label} parsed but no supported XML parts were found."

        parts: list[str] = []
        parse_failures = 0
        for member_name in sorted(xml_members):
            try:
                xml_bytes = archive.read(member_name)
                root = ET.fromstring(xml_bytes)
            except Exception:  # noqa: BLE001
                parse_failures += 1
                continue

            fragment_tokens: list[str] = []
            for node in root.iter():
                local_name = node.tag.rsplit("}", 1)[-1]
                if local_name not in text_tag_names:
                    continue
                token = (node.text or "").strip()
                if token:
                    fragment_tokens.append(token)
            if fragment_tokens:
                parts.append(" ".join(fragment_tokens))

        text = "\n".join(parts).strip()
        if text:
            warning = None
            if parse_failures > 0:
                warning = f"{source_label} partially parsed ({parse_failures} XML part(s) failed)."
            return text, warning

        if parse_failures > 0:
            return "No text detected.", f"{source_label} parse failure: no readable XML text nodes were found."
        return "No text detected.", f"{source_label} parsed but no extractable text was found."


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

    if extension == ".docx":
        return _extract_zip_xml_text(
            path,
            member_prefixes=(
                "word/document.xml",
                "word/header",
                "word/footer",
                "word/footnotes",
                "word/endnotes",
            ),
            text_tag_names={"t"},
            source_label="DOCX",
        )

    if extension == ".pptx":
        return _extract_zip_xml_text(
            path,
            member_prefixes=("ppt/slides/slide",),
            text_tag_names={"t"},
            source_label="PPTX",
        )

    return "No text detected.", f"Unsupported document type for grounding: {extension or '(none)'}"
