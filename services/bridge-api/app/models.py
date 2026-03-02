from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


GapStatus = Literal["open", "reviewing", "closed"]
GapType = Literal["concept", "reasoning", "misconception"]
PlatformName = Literal["windows", "macos"]
SentinelRuntimeLastAction = Literal["none", "start", "stop"]
SentinelRuntimeAction = Literal["start", "stop"]


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
    course_id: str | None = None
    module_id: str | None = None


class VisionExtraction(BaseModel):
    raw_text: str
    summary: str
    tags: list[str] = Field(default_factory=list)


class KnowledgeGap(BaseModel):
    gap_id: str = Field(default_factory=lambda: str(uuid4()))
    concept: str
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    basis_question: str | None = None
    basis_answer_excerpt: str | None = None
    gap_type: GapType | None = None
    course_id: str = "all"
    module_id: str | None = None
    material_id: str | None = None
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


class SourceContext(BaseModel):
    module_id: str
    module_name: str
    material_id: str | None = None
    material_name: str | None = None
    match_score: float = Field(ge=0.0, le=1.0)
    matched: bool


class CaptureEvent(BaseModel):
    capture_id: str
    timestamp_utc: str
    app_name: str
    window_title: str
    socratic_prompt: str
    gaps: list[str]
    course_id: str = "all"
    module_id: str | None = None
    material_id: str | None = None
    source_warning: str | None = None
    source_context: SourceContext | None = None


class CourseSummary(BaseModel):
    course_id: str
    course_name: str


class TopicMasteryItem(BaseModel):
    topic_id: str
    course_id: str
    name: str
    current: float = Field(ge=0.0, le=1.0)
    target: float = Field(ge=0.0, le=1.0)
    open_gaps: int = Field(ge=0)


class StudyAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str
    topic_id: str
    title: str
    rationale: str
    eta_minutes: int = Field(ge=5, le=240)
    priority: float = Field(ge=0.0, le=1.0)
    source_gap_ids: list[str] = Field(default_factory=list)


class CourseDeadline(BaseModel):
    deadline_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str = "all"
    name: str
    due_date: str
    readiness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    associated_gap_ids: list[str] = Field(default_factory=list)


class CourseDocument(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str = "all"
    name: str
    size_bytes: int = Field(ge=0)
    type: str = "other"
    uploaded_at: str = Field(default_factory=utc_now_iso)
    file_url: str
    is_anchor: bool = False


class SessionEvent(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str = "all"
    thread_id: str
    turn_index: int = Field(default=0, ge=0)
    timestamp_utc: str = Field(default_factory=utc_now_iso)
    summary: str
    topic: str
    gap_ids: list[str] = Field(default_factory=list)
    capture_id: str | None = None


class LearningState(BaseModel):
    updated_at: str = Field(default_factory=utc_now_iso)
    captures: list[CaptureEvent] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    courses: list[CourseSummary] = Field(default_factory=list)
    topic_mastery: list[TopicMasteryItem] = Field(default_factory=list)
    study_actions: list[StudyAction] = Field(default_factory=list)
    deadlines: list[CourseDeadline] = Field(default_factory=list)
    documents: list[CourseDocument] = Field(default_factory=list)
    sessions: list[SessionEvent] = Field(default_factory=list)
    readiness_axes: ReadinessAxes = Field(
        default_factory=lambda: ReadinessAxes(
            concept_mastery=0.0,
            deadline_pressure=0.0,
            retention_risk=0.0,
            problem_transfer=0.0,
            consistency=0.0,
        )
    )


class CaptureResponse(BaseModel):
    capture_id: str
    thread_id: str
    turn_index: int
    socratic_prompt: str
    gaps: list[KnowledgeGap]
    readiness_axes: ReadinessAxes
    topic_label: str | None = None
    course_id: str | None = None
    source_warning: str | None = None
    source_context: SourceContext | None = None


class GapStatusUpdate(BaseModel):
    status: GapStatus


class CreateDeadlineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    due_date: str
    readiness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    associated_gap_ids: list[str] = Field(default_factory=list)
    course_id: str | None = None


class AskRequest(BaseModel):
    course_id: str | None = None
    thread_id: str | None = None
    turn_index: int = Field(default=0, ge=0)
    message: str = Field(min_length=1, max_length=1200)


class AskResponse(BaseModel):
    thread_id: str
    turn_index: int
    socratic_prompt: str
    citations: list[str] = Field(default_factory=list)


class SentinelRuntimeStatus(BaseModel):
    running: bool
    process_count: int = Field(ge=0)
    detected_pids: list[int] = Field(default_factory=list)
    managed_pids: list[int] = Field(default_factory=list)
    last_action: SentinelRuntimeLastAction = "none"
    last_action_at: str | None = None
    last_error: str | None = None


class SentinelRuntimeActionResponse(BaseModel):
    ok: bool
    action: SentinelRuntimeAction
    message: str | None = None
    stopped_count: int | None = None
    failed_count: int | None = None
    status: SentinelRuntimeStatus


class EventEnvelope(BaseModel):
    type: str
    payload: dict
