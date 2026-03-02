from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


SCHEMA_VERSION = 1

GapStatus = Literal["open", "reviewing", "closed"]
PlatformName = Literal["windows", "macos"]
<<<<<<< Updated upstream
=======
SentinelRuntimeLastAction = Literal["none", "start", "stop"]
SentinelRuntimeAction = Literal["start", "stop"]
QuestionSource = Literal["pyq", "tutorial", "sentinel"]
>>>>>>> Stashed changes


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ApiError(BaseModel):
    detail: str
    code: str


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


<<<<<<< Updated upstream
=======
class TopicMastery(BaseModel):
    topic: str
    mastery: float = Field(ge=0.0, le=1.0)
    momentum: float = Field(default=0.0, ge=-1.0, le=1.0)
    last_updated: str = Field(default_factory=utc_now_iso)


class QuestionBankItem(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    source: QuestionSource
    concept: str
    question: str
    options: list[str] = Field(default_factory=list, min_length=2)
    correct_answer: str
    explanation: str | None = None


class QuizAnswerSubmission(BaseModel):
    question_id: str
    user_answer: str


class QuizSubmitRequest(BaseModel):
    topic: str
    sources: list[QuestionSource] = Field(default_factory=list)
    answers: list[QuizAnswerSubmission] = Field(default_factory=list)


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


class TopicUpdate(BaseModel):
    topic: str
    before_mastery: float = Field(ge=0.0, le=1.0)
    after_mastery: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=-1.0, le=1.0)


class SourceContext(BaseModel):
    module_id: str
    module_name: str
    material_id: str | None = None
    material_name: str | None = None
    match_score: float = Field(ge=0.0, le=1.0)
    matched: bool


>>>>>>> Stashed changes
class CaptureEvent(BaseModel):
    capture_id: str
    timestamp_utc: str
    app_name: str
    window_title: str
    socratic_prompt: str
    gaps: list[str]


class LearningState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    updated_at: str = Field(default_factory=utc_now_iso)
    captures: list[CaptureEvent] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
<<<<<<< Updated upstream
    readiness_axes: ReadinessAxes = Field(default_factory=lambda: ReadinessAxes(
        concept_mastery=0.0,
        deadline_pressure=0.0,
        retention_risk=0.0,
        problem_transfer=0.0,
        consistency=0.0,
    ))
=======
    topics: list[TopicMastery] = Field(default_factory=list)
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
    courses: list[CourseSummary] = Field(default_factory=list)
    topic_mastery: list[TopicMasteryItem] = Field(default_factory=list)
    study_actions: list[StudyAction] = Field(default_factory=list)
    deadlines: list[CourseDeadline] = Field(default_factory=list)
    documents: list[CourseDocument] = Field(default_factory=list)
    sessions: list[SessionEvent] = Field(default_factory=list)
>>>>>>> Stashed changes


class CaptureResponse(BaseModel):
    schema_version: int = SCHEMA_VERSION
    capture_id: str
    socratic_prompt: str
    gaps: list[KnowledgeGap]
    readiness_axes: ReadinessAxes


class QuizSubmitResponse(BaseModel):
    schema_version: int = SCHEMA_VERSION
    quiz: QuizRecord
    readiness_axes: ReadinessAxes
    topic_updates: list[TopicUpdate] = Field(default_factory=list)
    new_gap_ids: list[str] = Field(default_factory=list)


class GapStatusUpdate(BaseModel):
    status: GapStatus


class EventEnvelope(BaseModel):
    type: str
    payload: dict
