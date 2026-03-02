from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


GapStatus = Literal["open", "reviewing", "closed"]
PlatformName = Literal["windows", "macos"]
SCHEMA_VERSION = 1


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


class TopicMastery(BaseModel):
    topic_id: str
    name: str
    mastery_score: float = Field(ge=0.0, le=1.0)


class QuestionBankItem(BaseModel):
    id: str
    topic: str
    type: Literal["MCQ"] = "MCQ"
    question_text: str
    options: list[str] = Field(default_factory=list, min_length=2)
    correct_answer: str
    source: str
    source_type: Literal["pyq", "tutorial", "sentinel"] = "tutorial"
    captured_from_sentinel: bool = False
    concept: str = ""


class QuizQuestionResult(BaseModel):
    question_id: str
    question_text: str
    options: list[str] = Field(default_factory=list, min_length=2)
    correct_answer: str
    user_answer: str
    is_correct: bool
    source: str
    concept: str = ""


class QuizScore(BaseModel):
    correct: int = Field(ge=0)
    total: int = Field(ge=1)


class QuizRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    date_taken: str = Field(default_factory=utc_now_iso)
    sources: list[Literal["pyq", "tutorial", "sentinel"]] = Field(default_factory=list)
    score: QuizScore
    questions: list[QuizQuestionResult] = Field(default_factory=list)
    mastery_delta: float = 0.0
    generated_gap_ids: list[str] = Field(default_factory=list)


class CaptureEvent(BaseModel):
    capture_id: str
    timestamp_utc: str
    app_name: str
    window_title: str
    socratic_prompt: str
    gaps: list[str]


class LearningState(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    updated_at: str = Field(default_factory=utc_now_iso)
    captures: list[CaptureEvent] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    topics: list[TopicMastery] = Field(default_factory=list)
    question_bank: list[QuestionBankItem] = Field(default_factory=list)
    quizzes: list[QuizRecord] = Field(default_factory=list)
    readiness_axes: ReadinessAxes = Field(default_factory=lambda: ReadinessAxes(
        concept_mastery=0.0,
        deadline_pressure=0.0,
        retention_risk=0.0,
        problem_transfer=0.0,
        consistency=0.0,
    ))


class CaptureResponse(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    capture_id: str
    socratic_prompt: str
    gaps: list[KnowledgeGap]
    readiness_axes: ReadinessAxes


class GapStatusUpdate(BaseModel):
    status: GapStatus


class QuizSubmissionItem(BaseModel):
    question_id: str
    user_answer: str


class QuizSubmissionRequest(BaseModel):
    topic: str
    sources: list[Literal["pyq", "tutorial", "sentinel"]] = Field(default_factory=list)
    answers: list[QuizSubmissionItem] = Field(default_factory=list, min_length=1)


class QuizSubmissionResponse(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    quiz: QuizRecord
    readiness_axes: ReadinessAxes
    topic_updates: list[TopicMastery]
    new_gap_ids: list[str]


class APIErrorResponse(BaseModel):
    detail: str
    code: str


class EventEnvelope(BaseModel):
    type: str
    payload: dict
