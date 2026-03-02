from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from .module_matching import build_material_tokens, score_capture_against_material
from .module_models import MaterialSummary, ModuleMatchResult, ModuleSummary, utc_now_iso
from .openai_clients import OpenAIVisionClient


class ModuleStore:
    _ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
    _MATCH_THRESHOLD = 0.22

    def __init__(self, modules_dir: Path, vision_client: OpenAIVisionClient) -> None:
        self.modules_dir = modules_dir
        self._vision_client = vision_client
        self._index_path = modules_dir / "index.json"
        self._lock = threading.Lock()
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists() or self._index_path.read_text(encoding="utf-8").strip() == "":
            self._write_index_unlocked({"active_module_id": None, "modules": {}})

    def upsert_module(self, module_id: str, module_name: str) -> ModuleSummary:
        cleaned_id = self._sanitize_id(module_id)
        cleaned_name = self._compact_text(module_name, max_chars=120) or cleaned_id
        with self._lock:
            index = self._read_index_unlocked()
            modules = index.setdefault("modules", {})
            existing = modules.get(cleaned_id)
            now = utc_now_iso()
            if existing is None:
                existing = {
                    "module_id": cleaned_id,
                    "module_name": cleaned_name,
                    "created_at": now,
                    "updated_at": now,
                    "materials": {},
                }
                modules[cleaned_id] = existing
            else:
                existing["module_name"] = cleaned_name
                existing["updated_at"] = now
            self._write_index_unlocked(index)
            return self._module_summary(existing)

    def list_modules(self) -> list[ModuleSummary]:
        with self._lock:
            index = self._read_index_unlocked()
            modules = index.get("modules", {})
            summaries = [self._module_summary(entry) for entry in modules.values()]
            return sorted(summaries, key=lambda item: item.updated_at, reverse=True)

    def get_module(self, module_id: str) -> ModuleSummary | None:
        cleaned_id = self._sanitize_id(module_id)
        with self._lock:
            index = self._read_index_unlocked()
            module_entry = index.get("modules", {}).get(cleaned_id)
            if module_entry is None:
                return None
            return self._module_summary(module_entry)

    def set_active_module(self, module_id: str) -> ModuleSummary | None:
        cleaned_id = self._sanitize_id(module_id)
        with self._lock:
            index = self._read_index_unlocked()
            module_entry = index.get("modules", {}).get(cleaned_id)
            if module_entry is None:
                return None
            index["active_module_id"] = cleaned_id
            self._write_index_unlocked(index)
            return self._module_summary(module_entry)

    def get_active_module(self) -> ModuleSummary | None:
        with self._lock:
            index = self._read_index_unlocked()
            active_id = index.get("active_module_id")
            if not active_id:
                return None
            module_entry = index.get("modules", {}).get(active_id)
            if module_entry is None:
                return None
            return self._module_summary(module_entry)

    def add_material(
        self,
        module_id: str,
        material_name: str,
        material_type: str | None,
        original_filename: str,
        file_bytes: bytes,
    ) -> MaterialSummary:
        cleaned_module_id = self._sanitize_id(module_id)
        cleaned_material_name = self._compact_text(material_name, max_chars=140) or "Untitled material"
        extension = Path(original_filename).suffix.lower().strip()
        if extension not in self._ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {extension or '(none)'}")
        if not file_bytes:
            raise ValueError("Uploaded material is empty.")

        with self._lock:
            index = self._read_index_unlocked()
            module_entry = index.get("modules", {}).get(cleaned_module_id)
            if module_entry is None:
                raise ValueError(f"Module does not exist: {cleaned_module_id}")

        material_id = str(uuid4())
        module_dir = self.modules_dir / cleaned_module_id
        material_dir = module_dir / "materials" / material_id
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
            "module_id": cleaned_module_id,
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
            module_entry = index.get("modules", {}).get(cleaned_module_id)
            if module_entry is None:
                raise ValueError(f"Module does not exist: {cleaned_module_id}")
            materials = module_entry.setdefault("materials", {})
            materials[material_id] = entry
            module_entry["updated_at"] = now
            self._write_index_unlocked(index)
        return MaterialSummary.model_validate(entry)

    def list_materials(self, module_id: str) -> list[MaterialSummary]:
        cleaned_module_id = self._sanitize_id(module_id)
        with self._lock:
            index = self._read_index_unlocked()
            module_entry = index.get("modules", {}).get(cleaned_module_id)
            if module_entry is None:
                return []
            materials = module_entry.get("materials", {})
            items = [MaterialSummary.model_validate(item) for item in materials.values()]
            return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def match_capture(self, module_id: str, capture_text: str, capture_tags: list[str]) -> ModuleMatchResult | None:
        cleaned_module_id = self._sanitize_id(module_id)
        with self._lock:
            index = self._read_index_unlocked()
            module_entry = index.get("modules", {}).get(cleaned_module_id)
            if module_entry is None:
                return None
            material_entries = list(module_entry.get("materials", {}).values())

        module_name = str(module_entry.get("module_name", cleaned_module_id))
        if not material_entries:
            return ModuleMatchResult(
                module_id=cleaned_module_id,
                module_name=module_name,
                material_id=None,
                material_name=None,
                match_score=0.0,
                matched=False,
            )

        best_entry: dict[str, Any] | None = None
        best_score = -1.0
        for material_entry in material_entries:
            tokens_path = self.modules_dir / str(material_entry.get("tokens_path", ""))
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
            return ModuleMatchResult(
                module_id=cleaned_module_id,
                module_name=module_name,
                material_id=None,
                material_name=None,
                match_score=0.0,
                matched=False,
            )

        return ModuleMatchResult(
            module_id=cleaned_module_id,
            module_name=module_name,
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
        if extension in {".txt", ".md"}:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            warning = None if text else "Uploaded text material is empty after decoding."
            return text or "No text detected.", [], warning

        if extension == ".pdf":
            return self._extract_pdf_text(source_path)

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

    def _module_summary(self, module_entry: dict[str, Any]) -> ModuleSummary:
        return ModuleSummary(
            module_id=str(module_entry.get("module_id", "")),
            module_name=str(module_entry.get("module_name", "")),
            material_count=len(module_entry.get("materials", {})),
            created_at=str(module_entry.get("created_at", utc_now_iso())),
            updated_at=str(module_entry.get("updated_at", utc_now_iso())),
        )

    def _read_index_unlocked(self) -> dict[str, Any]:
        payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        payload.setdefault("active_module_id", None)
        payload.setdefault("modules", {})
        return payload

    def _write_index_unlocked(self, payload: dict[str, Any]) -> None:
        tmp_path = self._index_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._index_path)

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.modules_dir)).replace("\\", "/")

    def _sanitize_id(self, raw_value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", (raw_value or "").strip())
        trimmed = cleaned[:80].strip("-")
        if trimmed:
            return trimmed
        return str(uuid4())

    def _compact_text(self, raw_value: str, max_chars: int) -> str:
        return " ".join((raw_value or "").split())[:max_chars]

    def _derive_material_type(self, extension: str, material_type: str | None) -> str:
        if material_type and material_type.strip():
            return self._compact_text(material_type, max_chars=40).lower()
        if extension == ".pdf":
            return "pdf"
        if extension in {".txt", ".md"}:
            return "text"
        return "image"
