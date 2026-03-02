from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ModuleUpsertRequest(BaseModel):
    module_id: str = Field(min_length=1)
    module_name: str = Field(min_length=1)


class ModuleSummary(BaseModel):
    module_id: str
    module_name: str
    material_count: int = 0
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class MaterialSummary(BaseModel):
    material_id: str
    module_id: str
    material_name: str
    material_type: str
    original_filename: str
    source_path: str
    extracted_path: str
    tokens_path: str
    tokens_count: int = 0
    parse_warning: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class ActiveModuleRequest(BaseModel):
    module_id: str = Field(min_length=1)


class ActiveModuleResponse(BaseModel):
    active_module_id: str | None = None
    active_module_name: str | None = None


class ModuleListResponse(BaseModel):
    modules: list[ModuleSummary]
    active_module_id: str | None = None


class ModuleMatchResult(BaseModel):
    module_id: str
    module_name: str
    material_id: str | None = None
    material_name: str | None = None
    match_score: float = 0.0
    matched: bool = False
