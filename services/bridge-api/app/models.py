from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


GapStatus = Literal["open", "reviewing", "closed"]
GapType = Literal["concept", "reasoning", "misconception"]
ReplyMode = Literal["right_path_intuition", "gentle_correction", "off_topic_redirect", "session_complete"]
PlatformName = Literal["windows", "macos"]
SentinelRuntimeLastAction = Literal["none", "start", "stop"]
SentinelRuntimeAction = Literal["start", "stop"]
QuestionSource = Literal["pyq", "tutorial", "sentinel"]


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
    topic_id: str | None = None


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
    topic_id: str | None = None
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
    topic_id: str = ""
    topic_name: str = "Unresolved"
    material_id: str | None = None
    material_name: str | None = None
    match_score: float = Field(ge=0.0, le=1.0)
    matched: bool

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if not value.get("topic_id") and value.get("module_id"):
            value["topic_id"] = value.get("module_id")
        if not value.get("topic_name") and value.get("module_name"):
            value["topic_name"] = value.get("module_name")
        return value


class CaptureEvent(BaseModel):
    capture_id: str
    timestamp_utc: str
    app_name: str
    window_title: str
    socratic_prompt: str
    gaps: list[str]
    course_id: str = "all"
    topic_id: str | None = None
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


class TopicCatalogItem(BaseModel):
    topic_id: str = Field(default_factory=lambda: str(uuid4()))
    course_id: str = "all"
    parent_topic_id: str = ""
    name: str
    normalized_name: str
    source_doc_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if not value.get("parent_topic_id"):
            legacy_parent = value.get("module_id") or value.get("topic_id")
            if legacy_parent:
                value["parent_topic_id"] = str(legacy_parent)
        return value


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
    topic_id: str
    name: str
    size_bytes: int = Field(ge=0)
    type: str = "other"
    uploaded_at: str = Field(default_factory=utc_now_iso)
    file_url: str
    is_anchor: bool = False


class DocumentRetagRequest(BaseModel):
    topic_id: str = Field(min_length=1, max_length=80)


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


class QuestionBankItem(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    source: QuestionSource
    concept: str
    question: str
    options: list[str] = Field(default_factory=list, min_length=2)
    correct_answer: str
    explanation: str | None = None
    course_id: str = "all"
    topic_id: str | None = None
    origin_doc_id: str | None = None
    origin_material_id: str | None = None
    origin_topic_id: str | None = None
    generated: bool = False


class QuizAnswerSubmission(BaseModel):
    question_id: str
    user_answer: str


class QuizSubmitRequest(BaseModel):
    topic: str
    sources: list[QuestionSource] = Field(default_factory=list)
    answers: list[QuizAnswerSubmission] = Field(default_factory=list)
    course_id: str | None = None
    topic_id: str | None = None
    session_id: str | None = None


class QuizPrepareRequest(BaseModel):
    topic: str
    sources: list[QuestionSource] = Field(default_factory=list)
    question_count: int = Field(default=5, ge=1, le=25)
    course_id: str | None = None
    topic_id: str | None = None


class QuizSelectionSummary(BaseModel):
    gap_matched_count: int = Field(default=0, ge=0)
    wrong_repeat_count: int = Field(default=0, ge=0)
    deadline_boosted_count: int = Field(default=0, ge=0)
    coverage_count: int = Field(default=0, ge=0)


class QuizPrepareResponse(BaseModel):
    session_id: str
    topic: str
    questions: list[QuestionBankItem] = Field(default_factory=list)
    selection_summary: QuizSelectionSummary


class QuizQuestionResult(BaseModel):
    question_id: str
    topic: str
    source: QuestionSource
    concept: str
    user_answer: str
    correct_answer: str
    is_correct: bool


class QuizRecord(BaseModel):
    quiz_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp_utc: str = Field(default_factory=utc_now_iso)
    topic: str
    sources: list[QuestionSource] = Field(default_factory=list)
    total_questions: int = Field(ge=0)
    correct_answers: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    results: list[QuizQuestionResult] = Field(default_factory=list)
    course_id: str = "all"
    topic_id: str | None = None


class TopicUpdate(BaseModel):
    topic: str
    before_mastery: float = Field(ge=0.0, le=1.0)
    after_mastery: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=-1.0, le=1.0)


class QuizSubmitResponse(BaseModel):
    quiz: QuizRecord
    readiness_axes: ReadinessAxes
    topic_updates: list[TopicUpdate] = Field(default_factory=list)
    new_gap_ids: list[str] = Field(default_factory=list)


class LearningState(BaseModel):
    updated_at: str = Field(default_factory=utc_now_iso)
    captures: list[CaptureEvent] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    courses: list[CourseSummary] = Field(default_factory=list)
    topic_mastery: list[TopicMasteryItem] = Field(default_factory=list)
    topics: list[TopicCatalogItem] = Field(default_factory=list)
    study_actions: list[StudyAction] = Field(default_factory=list)
    deadlines: list[CourseDeadline] = Field(default_factory=list)
    documents: list[CourseDocument] = Field(default_factory=list)
    sessions: list[SessionEvent] = Field(default_factory=list)
    question_bank: list[QuestionBankItem] = Field(default_factory=list)
    quizzes: list[QuizRecord] = Field(default_factory=list)
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
    source_material_url: str | None = None
    source_material_label: str | None = None


class GapStatusUpdate(BaseModel):
    status: GapStatus


class CreateDeadlineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    due_date: str
    readiness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    associated_gap_ids: list[str] = Field(default_factory=list)
    course_id: str | None = None


class CourseCreateRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    course_name: str = Field(min_length=1, max_length=160)


class SentinelSessionContext(BaseModel):
    course_id: str | None = None
    course_name: str | None = None
    topic_id: str | None = None
    topic_name: str | None = None
    updated_at: str | None = None


class SentinelSessionContextRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    topic_id: str = Field(min_length=1, max_length=80)


class SentinelRuntimeStartRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    topic_id: str = Field(min_length=1, max_length=80)


class SentinelRuntimeStatus(BaseModel):
    running: bool
    process_count: int = Field(ge=0)
    detected_pids: list[int] = Field(default_factory=list)
    managed_pids: list[int] = Field(default_factory=list)
    active_course_id: str | None = None
    active_topic_id: str | None = None
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
