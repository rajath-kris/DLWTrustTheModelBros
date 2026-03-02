from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .azure_clients import AzureSocraticClient, AzureVisionClient
from .config import settings
from .models import (
    APIErrorResponse,
    CaptureEvent,
    CaptureRequest,
    CaptureResponse,
    EventEnvelope,
    GapStatusUpdate,
    KnowledgeGap,
    QuizRecord,
    QuizScore,
    QuizSubmissionRequest,
    QuizSubmissionResponse,
    QuizQuestionResult,
    SCHEMA_VERSION,
    TopicMastery,
)
from .readiness import calculate_readiness
from .sse import SSEBroker, sse_generator
from .state_store import StateStore

app = FastAPI(title="Sentinel Bridge API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.captures_dir.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(settings.captures_dir)), name="captures")

store = StateStore(settings.state_file)
broker = SSEBroker()
vision_client = AzureVisionClient(settings)
socratic_client = AzureSocraticClient(settings)
logger = logging.getLogger("sentinel.bridge")


class BridgeAPIError(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _log_event(level: str, **payload: object) -> None:
    line = json.dumps(payload, ensure_ascii=True)
    if level == "error":
        logger.error(line)
    else:
        logger.info(line)


def _load_syllabus() -> dict:
    if not settings.syllabus_file.exists():
        return {"concepts": []}
    with settings.syllabus_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_concept(raw: str) -> str:
    return " ".join(raw.strip().split()).lower()


def _deadline_score_for_concept(concept: str, syllabus: dict) -> float:
    normalized = _normalize_concept(concept)
    today = date.today()
    for item in syllabus.get("concepts", []):
        name = _normalize_concept(str(item.get("name", "")))
        if not name:
            continue
        if normalized in name or name in normalized:
            deadline_raw = item.get("deadline")
            if not deadline_raw:
                return 0.5
            deadline = datetime.strptime(deadline_raw, "%Y-%m-%d").date()
            days = (deadline - today).days
            if days <= 0:
                return 1.0
            if days <= 3:
                return 0.9
            if days <= 7:
                return 0.75
            if days <= 14:
                return 0.55
            return 0.35
    return 0.4


def _state_payload() -> dict:
    state = store.read()
    return state.model_dump(mode="json")


def _sanitize_capture_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return (cleaned[:80] or str(uuid4())).strip("-") or str(uuid4())


def _sanitize_topic_id(raw_value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw_value.strip().lower()).strip("-")
    return slug or f"topic-{uuid4()}"


def _find_topic(state_topics: list[TopicMastery], topic_name: str) -> TopicMastery | None:
    normalized = _normalize_concept(topic_name)
    for topic in state_topics:
        if _normalize_concept(topic.name) == normalized:
            return topic
    return None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@app.exception_handler(BridgeAPIError)
async def handle_bridge_error(_: Request, exc: BridgeAPIError) -> JSONResponse:
    _log_event(
        "error",
        event="request_failed",
        code=exc.code,
        detail=exc.detail,
        status_code=exc.status_code,
    )
    payload = APIErrorResponse(detail=exc.detail, code=exc.code)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    _log_event(
        "error",
        event="request_validation_failed",
        code="VALIDATION_ERROR",
        errors=exc.errors(),
    )
    payload = APIErrorResponse(detail="Request validation failed", code="VALIDATION_ERROR")
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "timestamp_utc": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/state")
def get_state() -> dict:
    return _state_payload()


@app.get("/api/v1/events/stream")
async def stream_events() -> StreamingResponse:
    queue = broker.subscribe()

    async def event_stream():
        try:
            async for chunk in sse_generator(queue):
                yield chunk
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/v1/captures", response_model=CaptureResponse)
async def create_capture(payload: CaptureRequest) -> CaptureResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception as exc:
        raise BridgeAPIError(status_code=400, code="INVALID_IMAGE_BASE64", detail=f"Invalid image_base64: {exc}") from exc

    capture_id = _sanitize_capture_id(payload.capture_id or str(uuid4()))
    filename = f"{capture_id}.png"
    capture_path = Path(settings.captures_dir) / filename
    capture_path.write_bytes(image_bytes)

    syllabus = _load_syllabus()
    extraction = vision_client.extract(image_bytes)
    socratic = socratic_client.generate(payload, extraction, syllabus)

    new_gaps: list[KnowledgeGap] = []
    for raw_gap in socratic.gaps:
        concept = str(raw_gap.get("concept", "Unknown Concept")).strip() or "Unknown Concept"
        severity = max(0.0, min(1.0, float(raw_gap.get("severity", 0.5))))
        confidence = max(0.0, min(1.0, float(raw_gap.get("confidence", 0.6))))
        deadline_score = _deadline_score_for_concept(concept, syllabus)
        priority_score = max(0.0, min(1.0, (severity * 0.7) + (deadline_score * 0.3)))

        new_gaps.append(
            KnowledgeGap(
                concept=concept,
                severity=severity,
                confidence=confidence,
                capture_id=capture_id,
                evidence_url=f"http://{settings.bridge_host}:{settings.bridge_port}/captures/{filename}",
                deadline_score=deadline_score,
                priority_score=priority_score,
            )
        )

    event = CaptureEvent(
        capture_id=capture_id,
        timestamp_utc=payload.timestamp_utc,
        app_name=payload.app_name,
        window_title=payload.window_title,
        socratic_prompt=socratic.socratic_prompt,
        gaps=[item.gap_id for item in new_gaps],
    )

    existing_state = store.read()
    merged_gaps = [*existing_state.gaps, *new_gaps]
    readiness = calculate_readiness(merged_gaps, [topic.mastery_score for topic in existing_state.topics])
    state = store.append_capture(event, new_gaps, readiness)

    envelope = EventEnvelope(
        type="state_updated",
        payload={"state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))
    _log_event(
        "info",
        event="capture_processed",
        endpoint="/api/v1/captures",
        capture_id=capture_id,
        gap_count=len(new_gaps),
    )

    return CaptureResponse(
        schema_version=SCHEMA_VERSION,
        capture_id=capture_id,
        socratic_prompt=socratic.socratic_prompt,
        gaps=new_gaps,
        readiness_axes=readiness,
    )


@app.post("/api/v1/quizzes/submit", response_model=QuizSubmissionResponse)
async def submit_quiz(payload: QuizSubmissionRequest) -> QuizSubmissionResponse:
    state = store.read()
    if not state.question_bank:
        raise BridgeAPIError(status_code=400, code="EMPTY_QUESTION_BANK", detail="Question bank is empty")

    question_by_id = {question.id: question for question in state.question_bank}
    source_filter = set(payload.sources)

    results: list[QuizQuestionResult] = []
    for attempt in payload.answers:
        question = question_by_id.get(attempt.question_id)
        if question is None:
            raise BridgeAPIError(
                status_code=400,
                code="UNKNOWN_QUESTION_ID",
                detail=f"Unknown question_id: {attempt.question_id}",
            )
        if source_filter and question.source_type not in source_filter:
            raise BridgeAPIError(
                status_code=400,
                code="QUESTION_SOURCE_MISMATCH",
                detail=f"Question source '{question.source_type}' not allowed by selected filters",
            )
        if payload.topic.strip() and payload.topic.strip().lower() != "all topics":
            if _normalize_concept(question.topic) != _normalize_concept(payload.topic):
                raise BridgeAPIError(
                    status_code=400,
                    code="QUESTION_TOPIC_MISMATCH",
                    detail=f"Question '{question.id}' does not belong to topic '{payload.topic}'",
                )

        normalized_user_answer = attempt.user_answer.strip()
        is_correct = _normalize_concept(normalized_user_answer) == _normalize_concept(question.correct_answer)

        results.append(
            QuizQuestionResult(
                question_id=question.id,
                question_text=question.question_text,
                options=question.options,
                correct_answer=question.correct_answer,
                user_answer=normalized_user_answer,
                is_correct=is_correct,
                source=question.source,
                concept=question.concept or question.topic,
            )
        )

    if not results:
        raise BridgeAPIError(status_code=400, code="EMPTY_QUIZ_RESULTS", detail="Quiz submission has no answer entries")

    correct_count = sum(1 for item in results if item.is_correct)
    total_count = len(results)
    accuracy = correct_count / total_count
    quiz_topic = payload.topic if payload.topic.strip() else results[0].concept

    target_topic = _find_topic(state.topics, quiz_topic)
    if target_topic is None:
        target_topic = TopicMastery(
            topic_id=_sanitize_topic_id(quiz_topic),
            name=quiz_topic,
            mastery_score=0.6,
        )

    # Quiz performance updates topic mastery with bounded delta to keep progress smooth.
    mastery_delta = round(_clamp((accuracy - 0.6) * 0.18, -0.08, 0.08), 4)
    updated_mastery = _clamp(target_topic.mastery_score + mastery_delta, 0.0, 1.0)
    updated_topic = target_topic.model_copy(update={"mastery_score": updated_mastery})

    syllabus = _load_syllabus()
    seen_concepts: set[str] = set()
    new_gaps: list[KnowledgeGap] = []
    for result in results:
        if result.is_correct:
            continue
        concept = (result.concept or result.question_text).strip() or "Unknown Concept"
        normalized_concept = _normalize_concept(concept)
        if normalized_concept in seen_concepts:
            continue
        seen_concepts.add(normalized_concept)

        severity = _clamp(0.5 + (1.0 - accuracy) * 0.5, 0.0, 1.0)
        confidence = _clamp(0.65 + (1.0 - accuracy) * 0.2, 0.0, 1.0)
        deadline_score = _deadline_score_for_concept(concept, syllabus)
        priority_score = _clamp((severity * 0.7) + (deadline_score * 0.3), 0.0, 1.0)
        new_gaps.append(
            KnowledgeGap(
                concept=concept,
                severity=severity,
                confidence=confidence,
                capture_id=f"quiz-{uuid4()}",
                evidence_url=f"quiz://{result.question_id}",
                deadline_score=deadline_score,
                priority_score=priority_score,
            )
        )

    quiz_record = QuizRecord(
        topic=quiz_topic,
        sources=payload.sources,
        score=QuizScore(correct=correct_count, total=total_count),
        questions=results,
        mastery_delta=mastery_delta,
        generated_gap_ids=[gap.gap_id for gap in new_gaps],
    )

    merged_topics = [topic for topic in state.topics if topic.topic_id != updated_topic.topic_id] + [updated_topic]
    merged_gaps = [*state.gaps, *new_gaps]
    readiness = calculate_readiness(merged_gaps, [topic.mastery_score for topic in merged_topics])
    state = store.append_quiz(quiz_record, [updated_topic], new_gaps, readiness)

    envelope = EventEnvelope(
        type="state_updated",
        payload={"state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))
    _log_event(
        "info",
        event="quiz_submitted",
        endpoint="/api/v1/quizzes/submit",
        quiz_id=quiz_record.id,
        topic=quiz_topic,
        total=total_count,
        correct=correct_count,
    )

    return QuizSubmissionResponse(
        schema_version=SCHEMA_VERSION,
        quiz=quiz_record,
        readiness_axes=readiness,
        topic_updates=[updated_topic],
        new_gap_ids=[gap.gap_id for gap in new_gaps],
    )


@app.post("/api/v1/gaps/{gap_id}/status")
async def update_gap_status(gap_id: str, request: GapStatusUpdate) -> dict:
    state = store.update_gap_status(gap_id, request.status)
    if state is None:
        raise BridgeAPIError(status_code=404, code="GAP_NOT_FOUND", detail=f"Gap not found: {gap_id}")

    state.readiness_axes = calculate_readiness(state.gaps, [topic.mastery_score for topic in state.topics])
    store.write(state)

    envelope = EventEnvelope(
        type="gap_updated",
        payload={"gap_id": gap_id, "status": request.status, "state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))
    _log_event(
        "info",
        event="gap_status_updated",
        endpoint=f"/api/v1/gaps/{gap_id}/status",
        gap_id=gap_id,
        status=request.status,
    )

    return {"ok": True, "gap_id": gap_id, "status": request.status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.bridge_host, port=8000, reload=True)
