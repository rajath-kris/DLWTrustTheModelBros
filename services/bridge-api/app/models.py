from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


GapStatus = Literal["open", "reviewing", "closed"]
PlatformName = Literal["windows", "macos"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MonitorInfo(BaseModel):
    left: int
    top: int
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    scale: float = Field(ge=0.5)


class RegionInfo(BaseModel):
    x: int
    y: int
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class CaptureRequest(BaseModel):
    capture_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp_utc: str = Field(default_factory=utc_now_iso)
    platform: PlatformName
    app_name: str
    window_title: str
    monitor: MonitorInfo
    region: RegionInfo
    image_base64: str = Field(min_length=1)
    thread_id: str | None = None
    turn_index: int = Field(default=0, ge=0)
    previous_prompt: str | None = None
    user_input_text: str | None = None


class VisionExtraction(BaseModel):
    raw_text: str
    summary: str
    tags: list[str] = Field(default_factory=list)


class KnowledgeGap(BaseModel):
    gap_id: str = Field(default_factory=lambda: str(uuid4()))
    concept: str
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    status: GapStatus = "open"
    capture_id: str
    evidence_url: str
    deadline_score: float = Field(ge=0.0, le=1.0)
    priority_score: float = Field(ge=0.0, le=1.0)


class ReadinessAxes(BaseModel):
    concept_mastery: float = Field(ge=0.0, le=1.0)
    deadline_pressure: float = Field(ge=0.0, le=1.0)
    retention_risk: float = Field(ge=0.0, le=1.0)
    problem_transfer: float = Field(ge=0.0, le=1.0)
    consistency: float = Field(ge=0.0, le=1.0)


class CaptureEvent(BaseModel):
    capture_id: str
    timestamp_utc: str
    app_name: str
    window_title: str
    socratic_prompt: str
    gaps: list[str]


class LearningState(BaseModel):
    updated_at: str = Field(default_factory=utc_now_iso)
    captures: list[CaptureEvent] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    readiness_axes: ReadinessAxes = Field(default_factory=lambda: ReadinessAxes(
        concept_mastery=0.0,
        deadline_pressure=0.0,
        retention_risk=0.0,
        problem_transfer=0.0,
        consistency=0.0,
    ))


class CaptureResponse(BaseModel):
    capture_id: str
    thread_id: str
    turn_index: int
    socratic_prompt: str
    gaps: list[KnowledgeGap]
    readiness_axes: ReadinessAxes


class GapStatusUpdate(BaseModel):
    status: GapStatus


class EventEnvelope(BaseModel):
    type: str
    payload: dict
