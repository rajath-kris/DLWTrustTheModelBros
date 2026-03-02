from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

<<<<<<< Updated upstream
from fastapi import FastAPI, HTTPException
=======
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
>>>>>>> Stashed changes
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .azure_clients import AzureSocraticClient, AzureVisionClient
from .config import settings
from .models import (
    CaptureEvent,
    CaptureRequest,
    CaptureResponse,
    EventEnvelope,
    GapStatusUpdate,
    KnowledgeGap,
<<<<<<< Updated upstream
=======
    LearningState,
    QuestionBankItem,
    QuizQuestionResult,
    QuizRecord,
    QuizSubmitRequest,
    QuizSubmitResponse,
    SCHEMA_VERSION,
    SessionEvent,
    SentinelRuntimeActionResponse,
    SentinelRuntimeStatus,
    SourceContext,
    StudyAction,
    TopicMastery,
    TopicMasteryItem,
    TopicUpdate,
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
vision_client = AzureVisionClient(settings)
socratic_client = AzureSocraticClient(settings)
=======
vision_client = OpenAIVisionClient(settings)
socratic_client = OpenAISocraticClient(settings)
module_store = ModuleStore(settings.modules_dir, vision_client)
runtime_manager = SentinelRuntimeManager(settings)
logger = logging.getLogger("bridge_api")

MATCH_THRESHOLD = 0.22
WEAK_MATCH_THRESHOLD = 0.14
MAX_STUDY_ACTIONS = 5
NO_ACTIVE_MODULE_WARNING = "No active module selected; response may not be grounded in uploaded materials."
NO_MATCH_WARNING_TEMPLATE = (
    "No close match found in uploaded materials for active module '{module_name}'; response is best-effort."
)
>>>>>>> Stashed changes


def _api_error(status_code: int, detail: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": detail, "code": code})


def _json_log(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=True))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed.", "code": "VALIDATION_ERROR", "errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "detail" in exc.detail and "code" in exc.detail:
        payload = exc.detail
    else:
        payload = {"detail": str(exc.detail), "code": "VALIDATION_ERROR"}
    return JSONResponse(status_code=exc.status_code, content=payload)


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


<<<<<<< Updated upstream
=======
def _topic_label_from_gaps(gaps: list[KnowledgeGap]) -> str | None:
    if not gaps:
        return None
    ranked = sorted(
        gaps,
        key=lambda gap: (gap.priority_score, gap.severity, gap.confidence),
        reverse=True,
    )
    concept = ranked[0].concept.strip()
    if not concept:
        return None
    return concept


def _normalize_topic(raw: str) -> str:
    compact = " ".join(raw.strip().split())
    return compact or "General"


def _to_slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    return slug or "topic"


def _ensure_topic_entry(state: LearningState, topic_name: str) -> TopicMastery:
    normalized = _normalize_topic(topic_name)
    for topic in state.topics:
        if topic.topic.strip().lower() == normalized.lower():
            return topic
    item = TopicMastery(topic=normalized, mastery=0.5, momentum=0.0)
    state.topics.append(item)
    return item


def _default_question_bank() -> list[QuestionBankItem]:
    return [
        QuestionBankItem(
            question_id="qb-dp-01",
            topic="Dynamic Programming",
            source="tutorial",
            concept="State transition",
            question="What is the key step when building a DP recurrence?",
            options=[
                "Define states and valid transitions",
                "Start coding before defining states",
                "Only optimize space first",
                "Ignore base cases",
            ],
            correct_answer="Define states and valid transitions",
            explanation="A correct recurrence starts from explicit state meaning and transitions.",
        ),
        QuestionBankItem(
            question_id="qb-graph-01",
            topic="Graph Algorithms",
            source="pyq",
            concept="BFS shortest path",
            question="For an unweighted graph, which algorithm gives shortest path length?",
            options=["BFS", "DFS", "Dijkstra with negative edges", "Floyd only"],
            correct_answer="BFS",
            explanation="BFS explores layer by layer and returns minimum edge distance.",
        ),
        QuestionBankItem(
            question_id="qb-circuit-01",
            topic="AC Circuits",
            source="sentinel",
            concept="Phasor form",
            question="A sinusoid in steady state is most compactly represented as:",
            options=["Phasor", "Truth table", "State machine", "Prefix tree"],
            correct_answer="Phasor",
            explanation="Phasors convert sinusoidal time-domain quantities into complex-domain constants.",
        ),
    ]


def _resolve_module(module_id: str | None) -> ModuleSummary | None:
    requested_module_id = (module_id or "").strip()
    if requested_module_id:
        requested_module = module_store.get_module(requested_module_id)
        if requested_module is not None:
            return requested_module
    return module_store.get_active_module()


def _build_source_context(module: ModuleSummary, extraction_text: str, extraction_tags: list[str]) -> SourceContext:
    match = module_store.match_capture(module.module_id, extraction_text, extraction_tags)
    if match is None:
        return SourceContext(
            module_id=module.module_id,
            module_name=module.module_name,
            material_id=None,
            material_name=None,
            match_score=0.0,
            matched=False,
        )
    score = max(0.0, min(1.0, float(match.match_score)))
    matched = score >= MATCH_THRESHOLD
    return SourceContext(
        module_id=module.module_id,
        module_name=module.module_name,
        material_id=match.material_id,
        material_name=match.material_name,
        match_score=score,
        matched=matched,
    )


def _source_warning_for(module: ModuleSummary | None, source_context: SourceContext | None) -> str | None:
    if module is None:
        return NO_ACTIVE_MODULE_WARNING
    if source_context is None:
        return NO_MATCH_WARNING_TEMPLATE.format(module_name=module.module_name)
    score = max(0.0, min(1.0, source_context.match_score))
    if score >= MATCH_THRESHOLD:
        return None
    if score >= WEAK_MATCH_THRESHOLD:
        return NO_MATCH_WARNING_TEMPLATE.format(module_name=module.module_name)
    return NO_MATCH_WARNING_TEMPLATE.format(module_name=module.module_name)


def _nearest_deadline_days(deadlines: list[CourseDeadline], course_id: str) -> int | None:
    now = datetime.now(timezone.utc)
    best: int | None = None
    for deadline in deadlines:
        if deadline.course_id != course_id:
            continue
        try:
            due = datetime.fromisoformat(deadline.due_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        days = int((due - now).total_seconds() // 86400)
        if best is None or days < best:
            best = days
    return best


def _recompute_derived(state: LearningState) -> LearningState:
    if not state.question_bank:
        state.question_bank = _default_question_bank()

    open_gaps = [gap for gap in state.gaps if gap.status != "closed"]

    topic_buckets: dict[tuple[str, str], list[KnowledgeGap]] = {}
    for gap in open_gaps:
        course_id = _normalize_course_id(gap.course_id)
        topic_name = _topic_name_from_concept(gap.concept)
        key = (course_id, topic_name)
        topic_buckets.setdefault(key, []).append(gap)

    topic_rows: list[TopicMasteryItem] = []
    for (course_id, topic_name), bucket in topic_buckets.items():
        avg_severity = sum(item.severity for item in bucket) / max(1, len(bucket))
        current = max(0.0, min(1.0, 1.0 - avg_severity))
        nearest_days = _nearest_deadline_days(state.deadlines, course_id)
        target = 0.8 if nearest_days is not None and nearest_days <= 7 else 0.7
        topic_rows.append(
            TopicMasteryItem(
                topic_id=_topic_id_from_name(topic_name),
                course_id=course_id,
                name=topic_name,
                current=current,
                target=target,
                open_gaps=len(bucket),
            )
        )

    topic_rows.sort(key=lambda item: (item.course_id, item.current, -item.open_gaps, item.name))

    ranked_gaps = sorted(
        open_gaps,
        key=lambda gap: (gap.priority_score, gap.severity, gap.confidence),
        reverse=True,
    )
    actions: list[StudyAction] = []
    for gap in ranked_gaps[:MAX_STUDY_ACTIONS]:
        topic_name = _topic_name_from_concept(gap.concept)
        eta = max(15, min(120, 20 + int(gap.severity * 50)))
        actions.append(
            StudyAction(
                course_id=_normalize_course_id(gap.course_id),
                topic_id=_topic_id_from_name(topic_name),
                title=f"Review {topic_name}",
                rationale=(gap.basis_question or "Use active recall and worked examples.")[:220],
                eta_minutes=eta,
                priority=max(0.0, min(1.0, float(gap.priority_score))),
                source_gap_ids=[gap.gap_id],
            )
        )

    course_ids: set[str] = set()
    for gap in state.gaps:
        course_ids.add(_normalize_course_id(gap.course_id))
    for capture in state.captures:
        course_ids.add(_normalize_course_id(capture.course_id))
    for deadline in state.deadlines:
        course_ids.add(_normalize_course_id(deadline.course_id))
    for document in state.documents:
        course_ids.add(_normalize_course_id(document.course_id))
    for session in state.sessions:
        course_ids.add(_normalize_course_id(session.course_id))
    if not course_ids:
        course_ids.add("all")

    courses = [
        CourseSummary(course_id=course_id, course_name=_course_display_name(course_id))
        for course_id in sorted(course_ids)
    ]

    topic_lookup = {item.topic.strip().lower(): item for item in state.topics}
    for row in topic_rows:
        key = row.name.strip().lower()
        if key in topic_lookup:
            existing = topic_lookup[key]
            existing.mastery = max(0.0, min(1.0, row.current))
            existing.last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        else:
            state.topics.append(
                TopicMastery(
                    topic=row.name,
                    mastery=max(0.0, min(1.0, row.current)),
                    momentum=0.0,
                )
            )

    return state.model_copy(
        update={
            "schema_version": SCHEMA_VERSION,
            "courses": courses,
            "topic_mastery": topic_rows,
            "study_actions": actions,
        }
    )


>>>>>>> Stashed changes
def _state_payload() -> dict:
    state = store.read()
    return state.model_dump(mode="json")


<<<<<<< Updated upstream
def _sanitize_capture_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return (cleaned[:80] or str(uuid4())).strip("-") or str(uuid4())
=======
def _require_runtime_control_enabled() -> None:
    if settings.sentinel_runtime_enabled:
        return
    raise _api_error(403, "Sentinel runtime control is disabled by server configuration.", "VALIDATION_ERROR")


async def _publish_state(state: LearningState) -> None:
    envelope = EventEnvelope(
        type="state_updated",
        payload={"state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))


def _save_state(state: LearningState) -> LearningState:
    derived = _recompute_derived(state)
    store.write(derived)
    return derived


def _filter_state_for_course(state: LearningState, course_id: str) -> LearningState:
    normalized = _normalize_course_id(course_id)
    if normalized == "all":
        return state

    filtered = state.model_copy(
        update={
            "captures": [item for item in state.captures if _normalize_course_id(item.course_id) == normalized],
            "gaps": [item for item in state.gaps if _normalize_course_id(item.course_id) == normalized],
            "topic_mastery": [item for item in state.topic_mastery if _normalize_course_id(item.course_id) == normalized],
            "study_actions": [item for item in state.study_actions if _normalize_course_id(item.course_id) == normalized],
            "deadlines": [item for item in state.deadlines if _normalize_course_id(item.course_id) == normalized],
            "documents": [item for item in state.documents if _normalize_course_id(item.course_id) == normalized],
            "sessions": [item for item in state.sessions if _normalize_course_id(item.course_id) == normalized],
            "courses": [item for item in state.courses if _normalize_course_id(item.course_id) == normalized],
        }
    )
    filtered.readiness_axes = calculate_readiness(filtered.gaps)
    return filtered
>>>>>>> Stashed changes


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
        raise _api_error(400, f"Invalid image_base64: {exc}", "INVALID_IMAGE_BASE64") from exc

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
    readiness = calculate_readiness(merged_gaps)
    state = store.append_capture(event, new_gaps, readiness)

    envelope = EventEnvelope(
        type="state_updated",
        payload={"state": state.model_dump(mode="json")},
    )
<<<<<<< Updated upstream
    await broker.publish(envelope.model_dump(mode="json"))
=======
    state.readiness_axes = calculate_readiness(state.gaps)
    state = _save_state(state)
    await _publish_state(state)
    _json_log(
        "capture_processed",
        endpoint="/api/v1/captures",
        capture_id=capture_id,
        gap_count=len(new_gaps),
    )
>>>>>>> Stashed changes

    return CaptureResponse(
        capture_id=capture_id,
        socratic_prompt=socratic.socratic_prompt,
        gaps=new_gaps,
        readiness_axes=readiness,
    )


@app.post("/api/v1/quizzes/submit", response_model=QuizSubmitResponse)
async def submit_quiz(request: QuizSubmitRequest) -> QuizSubmitResponse:
    state = store.read()
    state = _recompute_derived(state)
    if not state.question_bank:
        raise _api_error(400, "Question bank is empty.", "EMPTY_QUESTION_BANK")
    if not request.answers:
        raise _api_error(400, "Quiz answers must not be empty.", "EMPTY_QUIZ_RESULTS")

    requested_topic = _normalize_topic(request.topic)
    requested_sources = set(request.sources)
    if not requested_sources:
        requested_sources = {"pyq", "tutorial", "sentinel"}

    bank_by_id = {item.question_id: item for item in state.question_bank}
    question_results: list[QuizQuestionResult] = []
    for answer in request.answers:
        item = bank_by_id.get(answer.question_id)
        if item is None:
            raise _api_error(404, f"Unknown question_id: {answer.question_id}", "UNKNOWN_QUESTION_ID")
        if item.source not in requested_sources:
            raise _api_error(
                400,
                f"Question source mismatch for {answer.question_id}.",
                "QUESTION_SOURCE_MISMATCH",
            )
        if item.topic.strip().lower() != requested_topic.lower():
            raise _api_error(
                400,
                f"Question topic mismatch for {answer.question_id}.",
                "QUESTION_TOPIC_MISMATCH",
            )
        user_answer = " ".join(answer.user_answer.strip().split())
        correct_answer = " ".join(item.correct_answer.strip().split())
        is_correct = user_answer.lower() == correct_answer.lower()
        question_results.append(
            QuizQuestionResult(
                question_id=item.question_id,
                topic=item.topic,
                source=item.source,
                concept=item.concept,
                user_answer=user_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
            )
        )

    if not question_results:
        raise _api_error(400, "No quiz results computed.", "EMPTY_QUIZ_RESULTS")

    total = len(question_results)
    correct = sum(1 for item in question_results if item.is_correct)
    score = correct / total if total else 0.0
    quiz = QuizRecord(
        topic=requested_topic,
        sources=sorted(requested_sources),
        total_questions=total,
        correct_answers=correct,
        score=max(0.0, min(1.0, score)),
        results=question_results,
    )

    topic_entry = _ensure_topic_entry(state, requested_topic)
    before_mastery = topic_entry.mastery
    delta = (score - 0.5) * 0.2
    after_mastery = max(0.0, min(1.0, before_mastery + delta))
    topic_entry.mastery = after_mastery
    topic_entry.momentum = max(-1.0, min(1.0, delta * 3.0))
    topic_entry.last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    topic_updates = [
        TopicUpdate(
            topic=topic_entry.topic,
            before_mastery=before_mastery,
            after_mastery=after_mastery,
            delta=after_mastery - before_mastery,
        )
    ]

    new_gap_ids: list[str] = []
    for item in question_results:
        if item.is_correct:
            continue
        gap = KnowledgeGap(
            concept=f"{item.topic}: {item.concept}",
            severity=max(0.35, min(0.85, 0.5 + (1.0 - score) * 0.25)),
            confidence=0.7,
            basis_question=f"Quiz miss: {item.question_id}",
            basis_answer_excerpt=item.user_answer[:240] or None,
            gap_type="concept",
            course_id="all",
            capture_id=quiz.quiz_id,
            evidence_url=f"http://{settings.bridge_host}:{settings.bridge_port}/api/v1/quizzes/submit",
            deadline_score=0.4,
            priority_score=max(0.0, min(1.0, 0.55 + (1.0 - score) * 0.2)),
        )
        state.gaps.append(gap)
        new_gap_ids.append(gap.gap_id)

    state.quizzes.append(quiz)
    state.readiness_axes = calculate_readiness(state.gaps)
    state = _save_state(state)
    await _publish_state(state)
    _json_log(
        "quiz_submitted",
        endpoint="/api/v1/quizzes/submit",
        quiz_id=quiz.quiz_id,
        topic=requested_topic,
        total=total,
        correct=correct,
    )
    return QuizSubmitResponse(
        quiz=quiz,
        readiness_axes=state.readiness_axes,
        topic_updates=topic_updates,
        new_gap_ids=new_gap_ids,
    )


@app.post("/api/v1/gaps/{gap_id}/status")
async def update_gap_status(gap_id: str, request: GapStatusUpdate) -> dict:
    state = store.update_gap_status(gap_id, request.status)
    if state is None:
        raise _api_error(404, f"Gap not found: {gap_id}", "GAP_NOT_FOUND")

    state.readiness_axes = calculate_readiness(state.gaps)
<<<<<<< Updated upstream
    store.write(state)

    envelope = EventEnvelope(
        type="gap_updated",
        payload={"gap_id": gap_id, "status": request.status, "state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))

=======
    state = _save_state(state)
    await _publish_state(state)
    _json_log(
        "gap_status_updated",
        endpoint="/api/v1/gaps/{gap_id}/status",
        gap_id=gap_id,
        status=request.status,
    )
>>>>>>> Stashed changes
    return {"ok": True, "gap_id": gap_id, "status": request.status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.bridge_host, port=8000, reload=True)
