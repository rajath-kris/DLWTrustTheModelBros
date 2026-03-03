from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from .grounding import extract_supported_text
from .topic_matching import build_material_tokens, score_capture_against_material
from .topic_models import MaterialSummary, TopicMatchResult, TopicSummary, utc_now_iso
from .openai_clients import OpenAIVisionClient


class TopicStore:
    _ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}
    _MATCH_THRESHOLD = 0.22

    def __init__(self, topics_dir: Path, vision_client: OpenAIVisionClient) -> None:
        self.topics_dir = topics_dir
        self._vision_client = vision_client
        self._index_path = topics_dir / "index.json"
        self._lock = threading.Lock()
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists() or self._index_path.read_text(encoding="utf-8").strip() == "":
            self._write_index_unlocked({"active_topic_id": None, "topics": {}})

    def upsert_topic(self, topic_id: str, topic_name: str, course_id: str = "all") -> TopicSummary:
        cleaned_id = self._sanitize_id(topic_id)
        cleaned_name = self._compact_text(topic_name, max_chars=120) or cleaned_id
        cleaned_course_id = self._sanitize_course_id(course_id)
        with self._lock:
            index = self._read_index_unlocked()
            topics = index.setdefault("topics", {})
            existing = topics.get(cleaned_id)
            now = utc_now_iso()
            if existing is None:
                existing = {
                    "topic_id": cleaned_id,
                    "topic_name": cleaned_name,
                    "course_id": cleaned_course_id,
                    "created_at": now,
                    "updated_at": now,
                    "materials": {},
                }
                topics[cleaned_id] = existing
            else:
                existing["topic_name"] = cleaned_name
                existing_course = self._sanitize_course_id(str(existing.get("course_id") or "all"))
                if existing_course != "all" and cleaned_course_id == "all":
                    cleaned_course_id = existing_course
                existing["course_id"] = cleaned_course_id
                existing["updated_at"] = now
            self._write_index_unlocked(index)
            return self._topic_summary(existing)

    def list_topics(self, course_id: str | None = None, *, include_shared: bool = True) -> list[TopicSummary]:
        normalized_course_filter = None
        if course_id is not None:
            normalized_course_filter = self._sanitize_course_id(course_id)
            if normalized_course_filter == "all":
                normalized_course_filter = None
        with self._lock:
            index = self._read_index_unlocked()
            topics = index.get("topics", {})
            summaries = [self._topic_summary(entry) for entry in topics.values()]
            if normalized_course_filter is not None:
                allowed_courses = {normalized_course_filter}
                if include_shared:
                    allowed_courses.add("all")
                summaries = [
                    item
                    for item in summaries
                    if item.course_id in allowed_courses
                ]
            return sorted(summaries, key=lambda item: item.updated_at, reverse=True)

    def list_owned_topics(self, course_id: str) -> list[TopicSummary]:
        normalized_course = self._sanitize_course_id(course_id)
        if normalized_course == "all":
            return []
        return self.list_topics(normalized_course, include_shared=False)

    def get_topic(self, topic_id: str) -> TopicSummary | None:
        cleaned_id = self._sanitize_id(topic_id)
        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_id)
            if topic_entry is None:
                return None
            return self._topic_summary(topic_entry)

    def set_active_topic(self, topic_id: str) -> TopicSummary | None:
        cleaned_id = self._sanitize_id(topic_id)
        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_id)
            if topic_entry is None:
                return None
            index["active_topic_id"] = cleaned_id
            self._write_index_unlocked(index)
            return self._topic_summary(topic_entry)

    def get_active_topic(self) -> TopicSummary | None:
        with self._lock:
            index = self._read_index_unlocked()
            active_id = index.get("active_topic_id")
            if not active_id:
                return None
            topic_entry = index.get("topics", {}).get(active_id)
            if topic_entry is None:
                return None
            return self._topic_summary(topic_entry)

    def remove_topics_for_course(self, course_id: str) -> int:
        target_course = self._sanitize_course_id(course_id)
        removed_topic_ids: list[str] = []
        with self._lock:
            index = self._read_index_unlocked()
            topics = index.get("topics", {})
            kept_topics: dict[str, Any] = {}
            for topic_id, topic_entry in topics.items():
                if self._sanitize_course_id(str(topic_entry.get("course_id") or "all")) == target_course:
                    removed_topic_ids.append(topic_id)
                    continue
                kept_topics[topic_id] = topic_entry
            if not removed_topic_ids:
                return 0
            index["topics"] = kept_topics
            if index.get("active_topic_id") in removed_topic_ids:
                index["active_topic_id"] = None
            self._write_index_unlocked(index)

        for topic_id in removed_topic_ids:
            topic_dir = self.topics_dir / topic_id
            if topic_dir.exists():
                shutil.rmtree(topic_dir, ignore_errors=True)
        return len(removed_topic_ids)

    def add_material(
        self,
        topic_id: str,
        material_name: str,
        material_type: str | None,
        original_filename: str,
        file_bytes: bytes,
    ) -> MaterialSummary:
        cleaned_topic_id = self._sanitize_id(topic_id)
        cleaned_material_name = self._compact_text(material_name, max_chars=140) or "Untitled material"
        extension = Path(original_filename).suffix.lower().strip()
        if extension not in self._ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {extension or '(none)'}")
        if not file_bytes:
            raise ValueError("Uploaded material is empty.")

        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_topic_id)
            if topic_entry is None:
                raise ValueError(f"Topic does not exist: {cleaned_topic_id}")

        material_id = str(uuid4())
        topic_dir = self.topics_dir / cleaned_topic_id
        material_dir = topic_dir / "materials" / material_id
        material_dir.mkdir(parents=True, exist_ok=True)

        source_path = material_dir / f"source{extension}"
        source_path.write_bytes(file_bytes)

        extracted_text, extracted_tags, parse_warning = self._extract_material_content(
            file_bytes=file_bytes,
            extension=extension,
            source_path=source_path,
        )
        token_payload = build_material_tokens(extracted_text, cleaned_material_name, extracted_tags)
        extracted_path = material_dir / "extracted.txt"
        extracted_path.write_text(extracted_text, encoding="utf-8")
        tokens_path = material_dir / "tokens.json"
        tokens_path.write_text(json.dumps(token_payload, indent=2), encoding="utf-8")

        now = utc_now_iso()
        entry = {
            "material_id": material_id,
            "topic_id": cleaned_topic_id,
            "material_name": cleaned_material_name,
            "material_type": self._derive_material_type(extension, material_type),
            "original_filename": original_filename,
            "source_path": self._relative_path(source_path),
            "extracted_path": self._relative_path(extracted_path),
            "tokens_path": self._relative_path(tokens_path),
            "tokens_count": len(token_payload.get("text_tokens", [])),
            "parse_warning": parse_warning,
            "created_at": now,
            "updated_at": now,
        }
        metadata_path = material_dir / "material.json"
        metadata_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_topic_id)
            if topic_entry is None:
                raise ValueError(f"Topic does not exist: {cleaned_topic_id}")
            materials = topic_entry.setdefault("materials", {})
            materials[material_id] = entry
            topic_entry["updated_at"] = now
            self._write_index_unlocked(index)
        return MaterialSummary.model_validate(entry)

    def list_materials(self, topic_id: str) -> list[MaterialSummary]:
        cleaned_topic_id = self._sanitize_id(topic_id)
        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_topic_id)
            if topic_entry is None:
                return []
            materials = topic_entry.get("materials", {})
            items = [MaterialSummary.model_validate(item) for item in materials.values()]
            return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def match_capture(self, topic_id: str, capture_text: str, capture_tags: list[str]) -> TopicMatchResult | None:
        cleaned_topic_id = self._sanitize_id(topic_id)
        with self._lock:
            index = self._read_index_unlocked()
            topic_entry = index.get("topics", {}).get(cleaned_topic_id)
            if topic_entry is None:
                return None
            material_entries = list(topic_entry.get("materials", {}).values())

        topic_name = str(topic_entry.get("topic_name", cleaned_topic_id))
        if not material_entries:
            return TopicMatchResult(
                topic_id=cleaned_topic_id,
                topic_name=topic_name,
                material_id=None,
                material_name=None,
                match_score=0.0,
                matched=False,
            )

        best_entry: dict[str, Any] | None = None
        best_score = -1.0
        for material_entry in material_entries:
            tokens_path = self.topics_dir / str(material_entry.get("tokens_path", ""))
            if not tokens_path.exists():
                continue
            try:
                token_payload = json.loads(tokens_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            score = score_capture_against_material(
                capture_text=capture_text,
                capture_tags=capture_tags,
                material_text_tokens=list(token_payload.get("text_tokens", [])),
                material_tag_tokens=list(token_payload.get("tag_tokens", [])),
            )
            if score > best_score:
                best_score = score
                best_entry = material_entry

        if best_entry is None:
            return TopicMatchResult(
                topic_id=cleaned_topic_id,
                topic_name=topic_name,
                material_id=None,
                material_name=None,
                match_score=0.0,
                matched=False,
            )

        return TopicMatchResult(
            topic_id=cleaned_topic_id,
            topic_name=topic_name,
            material_id=str(best_entry.get("material_id")),
            material_name=str(best_entry.get("material_name", "")) or None,
            match_score=max(0.0, min(1.0, best_score)),
            matched=best_score >= self._MATCH_THRESHOLD,
        )

    def _extract_material_content(
        self,
        *,
        file_bytes: bytes,
        extension: str,
        source_path: Path,
    ) -> tuple[str, list[str], str | None]:
        if extension in {".txt", ".md", ".pdf", ".docx", ".pptx"}:
            text, warning = extract_supported_text(source_path)
            return text, [], warning

        if extension in {".png", ".jpg", ".jpeg"}:
            extraction = self._vision_client.extract(file_bytes)
            merged = "\n".join(item for item in [extraction.summary, extraction.raw_text] if item.strip()).strip()
            warning = None
            if "vision-error" in extraction.tags:
                warning = "Image parse used fallback due to vision extraction error."
            return merged or "No text detected.", extraction.tags, warning

        return "No text detected.", [], "Unsupported material type for extraction."

    def _extract_pdf_text(self, source_path: Path) -> tuple[str, list[str], str | None]:
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except Exception:
            return (
                "No text detected.",
                [],
                "PDF extraction unavailable because 'pypdf' is not installed.",
            )

        try:
            reader = PdfReader(str(source_path))
            chunks: list[str] = []
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    chunks.append(page_text)
            text = "\n".join(chunks).strip()
            warning = None if text else "PDF parsed but no extractable text was found."
            return text or "No text detected.", [], warning
        except Exception as exc:
            return "No text detected.", [], f"PDF parse failure: {type(exc).__name__}"

    def _topic_summary(self, topic_entry: dict[str, Any]) -> TopicSummary:
        return TopicSummary(
            topic_id=str(topic_entry.get("topic_id") or topic_entry.get("module_id") or ""),
            topic_name=str(topic_entry.get("topic_name") or topic_entry.get("module_name") or ""),
            course_id=self._sanitize_course_id(str(topic_entry.get("course_id") or "all")),
            material_count=len(topic_entry.get("materials", {})),
            created_at=str(topic_entry.get("created_at", utc_now_iso())),
            updated_at=str(topic_entry.get("updated_at", utc_now_iso())),
        )

    def _read_index_unlocked(self) -> dict[str, Any]:
        payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        if "topics" not in payload and isinstance(payload.get("modules"), dict):
            payload["topics"] = payload.get("modules", {})
        payload.setdefault("topics", {})

        if not payload.get("active_topic_id"):
            payload["active_topic_id"] = payload.get("active_module_id")
        payload.setdefault("active_topic_id", None)

        normalized_topics: dict[str, Any] = {}
        for raw_key, raw_entry in payload.get("topics", {}).items():
            if not isinstance(raw_entry, dict):
                continue
            topic_id = str(raw_entry.get("topic_id") or raw_entry.get("module_id") or raw_key).strip()
            if not topic_id:
                continue
            topic_name = str(raw_entry.get("topic_name") or raw_entry.get("module_name") or topic_id).strip() or topic_id
            course_id = self._sanitize_course_id(str(raw_entry.get("course_id") or "all"))
            materials = raw_entry.get("materials")
            if not isinstance(materials, dict):
                materials = {}
            for material in materials.values():
                if not isinstance(material, dict):
                    continue
                if not str(material.get("topic_id", "")).strip():
                    material["topic_id"] = str(material.get("module_id") or topic_id)
            raw_entry["topic_id"] = topic_id
            raw_entry["topic_name"] = topic_name
            raw_entry["course_id"] = course_id
            raw_entry["materials"] = materials
            normalized_topics[topic_id] = raw_entry

        payload["topics"] = normalized_topics
        if payload.get("active_topic_id") not in payload["topics"]:
            payload["active_topic_id"] = None
        return payload

    def _write_index_unlocked(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload.pop("modules", None)
        payload.pop("active_module_id", None)
        payload.setdefault("active_topic_id", None)
        payload.setdefault("topics", {})
        tmp_path = self._index_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._index_path)

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.topics_dir)).replace("\\", "/")

    def _sanitize_id(self, raw_value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", (raw_value or "").strip())
        trimmed = cleaned[:80].strip("-")
        if trimmed:
            return trimmed
        return str(uuid4())

    def _compact_text(self, raw_value: str, max_chars: int) -> str:
        return " ".join((raw_value or "").split())[:max_chars]

    def _sanitize_course_id(self, raw_value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", (raw_value or "").strip().lower())
        trimmed = cleaned[:80].strip("-")
        return trimmed or "all"

    def _derive_material_type(self, extension: str, material_type: str | None) -> str:
        if material_type and material_type.strip():
            return self._compact_text(material_type, max_chars=40).lower()
        if extension == ".pdf":
            return "pdf"
        if extension in {".txt", ".md"}:
            return "text"
        if extension == ".docx":
            return "docx"
        if extension == ".pptx":
            return "pptx"
        return "image"

