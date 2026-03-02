from __future__ import annotations

import base64
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .grounding import GroundingBundle, chunk_text, extract_supported_text, select_top_chunks, tokenize
from .models import (
    AskRequest,
    AskResponse,
    CaptureEvent,
    CaptureRequest,
    CaptureResponse,
    CourseDeadline,
    CourseDocument,
    CourseSummary,
    CreateDeadlineRequest,
    EventEnvelope,
    GapStatusUpdate,
    KnowledgeGap,
    LearningState,
    QuestionBankItem,
    QuizQuestionResult,
    QuizRecord,
    QuizSubmitRequest,
    QuizSubmitResponse,
    SessionEvent,
    SentinelRuntimeActionResponse,
    SentinelRuntimeStatus,
    SourceContext,
    StudyAction,
    TopicUpdate,
    TopicMasteryItem,
)
from .module_models import (
    ActiveModuleRequest,
    ActiveModuleResponse,
    MaterialSummary,
    ModuleListResponse,
    ModuleSummary,
    ModuleUpsertRequest,
)
from .module_store import ModuleStore
from .openai_clients import OpenAISocraticClient, OpenAIVisionClient
from .readiness import calculate_readiness
from .sentinel_runtime import SentinelRuntimeManager
from .sse import SSEBroker, sse_generator
from .state_store import StateStore

app = FastAPI(title="Sentinel Bridge API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.captures_dir.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(settings.captures_dir)), name="captures")
app.mount(
    "/course-documents",
    StaticFiles(directory=str(settings.documents_dir)),
    name="course-documents",
)

store = StateStore(settings.state_file)
broker = SSEBroker()
vision_client = OpenAIVisionClient(settings)
socratic_client = OpenAISocraticClient(settings)
module_store = ModuleStore(settings.modules_dir, vision_client)
runtime_manager = SentinelRuntimeManager(settings)

MATCH_THRESHOLD = 0.22
WEAK_MATCH_THRESHOLD = 0.14
MAX_STUDY_ACTIONS = 5
MODULE_GROUNDING_LIMIT = 3
COURSE_DOC_GROUNDING_LIMIT = 2
GROUNDING_MAX_CONTEXT_CHARS = 6200
NO_ACTIVE_MODULE_WARNING = "No active module selected; response may not be grounded in uploaded materials."
NO_MATCH_WARNING_TEMPLATE = (
    "No close match found in uploaded materials for active module '{module_name}'; response is best-effort."
)
FALLBACK_MODULE_ID = "module-general"
FALLBACK_MODULE_NAME = "General Materials"


def _load_syllabus() -> dict:
    if not settings.syllabus_file.exists():
        return {"concepts": []}
    with settings.syllabus_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_course_id(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9_-]", "-", text)
    cleaned = cleaned.strip("-")
    return cleaned or "all"


def _normalize_module_id(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9_-]", "-", text)
    return cleaned.strip("-")


def _course_display_name(course_id: str) -> str:
    if course_id == "all":
        return "All Courses"
    return course_id.upper()


def _normalize_concept(raw: str) -> str:
    return " ".join(raw.strip().split()).lower()


def _sanitize_filename(raw_name: str) -> str:
    stem = Path(raw_name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)
    return cleaned[:180] or "upload.bin"


def _topic_id_from_name(name: str) -> str:
    compact = " ".join(name.split()).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", compact).strip("-")
    return slug or "topic"


def _topic_name_from_concept(concept: str) -> str:
    compact = " ".join(concept.split())
    if not compact:
        return "General"
    return compact.split(",", 1)[0][:80]


def _optional_text(value: object, max_chars: int = 280) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    return text[:max_chars]


def _normalize_gap_type(raw_value: object) -> str | None:
    value = _optional_text(raw_value, max_chars=32)
    if value is None:
        return None
    normalized = value.lower()
    if normalized in {"concept", "reasoning", "misconception"}:
        return normalized
    return None


def _sanitize_capture_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return (cleaned[:80] or str(uuid4())).strip("-") or str(uuid4())


def _sanitize_thread_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return (cleaned[:80] or str(uuid4())).strip("-") or str(uuid4())


def _normalize_topic(raw: str | None) -> str:
    compact = " ".join((raw or "").strip().split())
    return compact or "General"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _question_visible_for_course(item: QuestionBankItem, course_id: str) -> bool:
    normalized = _normalize_course_id(course_id)
    item_course = _normalize_course_id(item.course_id)
    return normalized == "all" or item_course in {"all", normalized}


def _question_visible_for_module(item: QuestionBankItem, module_id: str | None) -> bool:
    requested = _normalize_module_id(module_id)
    if not requested:
        return True
    item_module = _normalize_module_id(item.module_id)
    return item_module in {"", requested}


def _find_topic_mastery_row(
    state: LearningState,
    *,
    course_id: str,
    topic_name: str,
) -> TopicMasteryItem | None:
    normalized_topic = _normalize_topic(topic_name).lower()
    normalized_course = _normalize_course_id(course_id)
    for row in state.topic_mastery:
        if _normalize_course_id(row.course_id) != normalized_course:
            continue
        if _normalize_topic(row.name).lower() == normalized_topic:
            return row
    return None


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


def _log_bridge_event(
    *,
    event: str,
    endpoint_path: str,
    capture_id: str | None = None,
    reason: str | None = None,
    **fields: object,
) -> None:
    payload: dict[str, object] = {
        "component": "bridge_api",
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "endpoint_path": endpoint_path,
    }
    if capture_id:
        payload["capture_id"] = capture_id
    if reason:
        payload["reason"] = reason
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def _dedupe_text_items(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _count_citations_with_prefix(citations: list[str], prefix: str) -> int:
    return sum(1 for citation in citations if citation.startswith(prefix))


def _score_chunk(query_tokens: set[str], chunk: str) -> int:
    if not query_tokens:
        return 0
    return len(query_tokens & set(tokenize(chunk)))


def _collect_module_grounding(module_id: str | None, query_text: str, limit: int = MODULE_GROUNDING_LIMIT) -> GroundingBundle:
    requested_module_id = (module_id or "").strip()
    if not requested_module_id:
        return GroundingBundle(context_text="", citations=[], warnings=[])

    module = module_store.get_module(requested_module_id)
    if module is None:
        return GroundingBundle(
            context_text="",
            citations=[],
            warnings=[f"Grounding skipped: module '{requested_module_id}' was not found."],
        )

    materials = module_store.list_materials(module.module_id)
    query_tokens = set(tokenize(query_text))
    candidates: list[tuple[int, str, str]] = []
    warnings: list[str] = []

    for material in materials:
        extracted_path = settings.modules_dir / material.extracted_path
        if not extracted_path.exists():
            warnings.append(
                f"Grounding skipped material '{material.material_name}': extracted text file missing."
            )
            continue

        try:
            extracted_text = extracted_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                f"Grounding skipped material '{material.material_name}': read failure ({type(exc).__name__})."
            )
            continue
        if not extracted_text:
            continue

        material_chunks = chunk_text(extracted_text)
        top_chunks = select_top_chunks(query_text, material_chunks, limit=1)
        citation = f"module:{module.module_name}/{material.material_name}"
        for chunk in top_chunks:
            candidates.append((_score_chunk(query_tokens, chunk), chunk, citation))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[: max(1, int(limit))]
    context_parts = [f"[{citation}]\n{chunk}" for _, chunk, citation in selected if chunk.strip()]
    citations = _dedupe_text_items([citation for _, _, citation in selected])
    return GroundingBundle(
        context_text="\n\n---\n\n".join(context_parts),
        citations=citations,
        warnings=_dedupe_text_items(warnings),
    )


def _course_document_path_from_url(file_url: str) -> Path | None:
    marker = "/course-documents/"
    if marker not in file_url:
        return None
    relative = file_url.split(marker, 1)[1].lstrip("/")
    base = settings.documents_dir.resolve()
    candidate = (base / Path(relative)).resolve()
    if base not in candidate.parents and candidate != base:
        return None
    return candidate


def _collect_course_doc_grounding(
    state: LearningState,
    course_id: str,
    module_id: str | None,
    query_text: str,
    limit: int = COURSE_DOC_GROUNDING_LIMIT,
) -> GroundingBundle:
    normalized = _normalize_course_id(course_id)
    target_module_id = _normalize_module_id(module_id)
    if not target_module_id:
        return GroundingBundle(context_text="", citations=[], warnings=[])

    course_scoped_docs = [
        doc
        for doc in state.documents
        if normalized == "all"
        or _normalize_course_id(doc.course_id) in {normalized, "all"}
    ]
    exact_module_docs = [
        doc for doc in course_scoped_docs if _normalize_module_id(doc.module_id) == target_module_id
    ]
    fallback_module_docs = [
        doc for doc in course_scoped_docs if _normalize_module_id(doc.module_id) == FALLBACK_MODULE_ID
    ]
    use_fallback = len(exact_module_docs) == 0 and len(fallback_module_docs) > 0
    eligible_docs = fallback_module_docs if use_fallback else exact_module_docs

    warnings: list[str] = []
    if use_fallback:
        warnings.append(
            f"Grounding used fallback course documents from '{FALLBACK_MODULE_ID}' because no documents matched module '{target_module_id}'."
        )

    anchored = sorted(
        [doc for doc in eligible_docs if doc.is_anchor],
        key=lambda item: item.uploaded_at,
        reverse=True,
    )
    non_anchored = sorted(
        [doc for doc in eligible_docs if not doc.is_anchor],
        key=lambda item: item.uploaded_at,
        reverse=True,
    )
    ordered_docs = [*anchored, *non_anchored]

    query_tokens = set(tokenize(query_text))
    candidates: list[tuple[int, str, str]] = []

    for document in ordered_docs:
        doc_path = _course_document_path_from_url(document.file_url)
        if doc_path is None:
            warnings.append(
                f"Grounding skipped document '{document.name}': unsupported file URL path."
            )
            continue
        if not doc_path.exists():
            warnings.append(
                f"Grounding skipped document '{document.name}': file not found."
            )
            continue

        extracted_text, parse_warning = extract_supported_text(doc_path)
        if parse_warning and parse_warning.startswith("Unsupported document type for grounding"):
            warnings.append(
                f"Grounding skipped document '{document.name}': {parse_warning}"
            )
            continue
        if parse_warning and extracted_text == "No text detected.":
            warnings.append(
                f"Grounding skipped document '{document.name}': {parse_warning}"
            )
            continue

        selected_chunks = select_top_chunks(query_text, chunk_text(extracted_text), limit=1)
        citation = f"course-doc:{document.name}"
        for chunk in selected_chunks:
            candidates.append((_score_chunk(query_tokens, chunk), chunk, citation))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[: max(1, int(limit))]
    context_parts = [f"[{citation}]\n{chunk}" for _, chunk, citation in selected if chunk.strip()]
    citations = _dedupe_text_items([citation for _, _, citation in selected])
    return GroundingBundle(
        context_text="\n\n---\n\n".join(context_parts),
        citations=citations,
        warnings=_dedupe_text_items(warnings),
    )


def _build_grounding_bundle(
    *,
    state: LearningState,
    module_id: str | None,
    course_id: str,
    query_text: str,
) -> GroundingBundle:
    module_bundle = _collect_module_grounding(
        module_id=module_id,
        query_text=query_text,
        limit=MODULE_GROUNDING_LIMIT,
    )
    course_bundle = _collect_course_doc_grounding(
        state=state,
        course_id=course_id,
        module_id=module_id,
        query_text=query_text,
        limit=COURSE_DOC_GROUNDING_LIMIT,
    )

    combined_context = "\n\n".join(
        part
        for part in [module_bundle.context_text.strip(), course_bundle.context_text.strip()]
        if part
    )
    if len(combined_context) > GROUNDING_MAX_CONTEXT_CHARS:
        combined_context = combined_context[: GROUNDING_MAX_CONTEXT_CHARS - 3].rstrip()
        combined_context = f"{combined_context}..."

    combined_citations = _dedupe_text_items([*module_bundle.citations, *course_bundle.citations])
    combined_warnings = _dedupe_text_items([*module_bundle.warnings, *course_bundle.warnings])
    return GroundingBundle(
        context_text=combined_context,
        citations=combined_citations,
        warnings=combined_warnings,
    )


def _merge_warning_messages(base_warning: str | None, extra_warnings: list[str]) -> str | None:
    values = []
    if base_warning:
        values.append(base_warning)
    values.extend(extra_warnings)
    merged = _dedupe_text_items(values)
    if not merged:
        return None
    return " | ".join(merged[:3])


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
    if state.quizzes is None:
        state.quizzes = []

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

    return state.model_copy(
        update={
            "courses": courses,
            "topic_mastery": topic_rows,
            "study_actions": actions,
        }
    )


def _state_payload() -> dict:
    state = _recompute_derived(store.read())
    return state.model_dump(mode="json")


def _require_runtime_control_enabled() -> None:
    if settings.sentinel_runtime_enabled:
        return
    raise HTTPException(
        status_code=403,
        detail="Sentinel runtime control is disabled by server configuration.",
    )


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


def _migrate_document_module_tags() -> None:
    state_path = settings.state_file
    if not state_path.exists():
        return

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _log_bridge_event(
            event="documents_module_migration_failed",
            endpoint_path="/startup",
            reason=f"State file read failure ({type(exc).__name__}).",
        )
        return

    documents_raw = payload.get("documents")
    if not isinstance(documents_raw, list):
        return

    missing_count = 0
    for document in documents_raw:
        if not isinstance(document, dict):
            continue
        if _normalize_module_id(document.get("module_id")):
            continue
        missing_count += 1

    if missing_count == 0:
        return

    active_module = module_store.get_active_module()
    if active_module is not None:
        fallback_module_id = active_module.module_id
        fallback_mode = "active-module"
    else:
        fallback_module = module_store.get_module(FALLBACK_MODULE_ID)
        if fallback_module is None:
            fallback_module = module_store.upsert_module(FALLBACK_MODULE_ID, FALLBACK_MODULE_NAME)
        fallback_module_id = fallback_module.module_id
        fallback_mode = "module-general"

    updated_count = 0
    for document in documents_raw:
        if not isinstance(document, dict):
            continue
        if _normalize_module_id(document.get("module_id")):
            continue
        document["module_id"] = fallback_module_id
        updated_count += 1

    if updated_count == 0:
        return

    try:
        state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log_bridge_event(
            event="documents_module_migration_failed",
            endpoint_path="/startup",
            reason=f"State file write failure ({type(exc).__name__}).",
            migrated_count=updated_count,
            fallback_module_id=fallback_module_id,
        )
        return

    _log_bridge_event(
        event="documents_module_migrated",
        endpoint_path="/startup",
        migrated_count=updated_count,
        fallback_module_id=fallback_module_id,
        fallback_mode=fallback_mode,
    )


_migrate_document_module_tags()


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
            "question_bank": [
                item
                for item in state.question_bank
                if _normalize_course_id(item.course_id) in {"all", normalized}
            ],
            "quizzes": [item for item in state.quizzes if _normalize_course_id(item.course_id) == normalized],
        }
    )
    filtered.readiness_axes = calculate_readiness(filtered.gaps)
    return filtered


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "timestamp_utc": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/sentinel/runtime", response_model=SentinelRuntimeStatus)
def get_sentinel_runtime_status() -> SentinelRuntimeStatus:
    _require_runtime_control_enabled()
    return runtime_manager.get_status()


@app.post("/api/v1/sentinel/runtime/start", response_model=SentinelRuntimeActionResponse)
def start_sentinel_runtime() -> SentinelRuntimeActionResponse:
    _require_runtime_control_enabled()
    try:
        return runtime_manager.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/sentinel/runtime/stop", response_model=SentinelRuntimeActionResponse)
def stop_sentinel_runtime() -> SentinelRuntimeActionResponse:
    _require_runtime_control_enabled()
    try:
        return runtime_manager.stop()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/state")
def get_state() -> dict:
    return _state_payload()


@app.get("/api/v1/brain/overview")
def get_brain_overview(course_id: str = Query(default="all")) -> dict:
    state = _recompute_derived(store.read())
    filtered = _filter_state_for_course(state, course_id)
    return {
        "course_id": _normalize_course_id(course_id),
        "state": filtered.model_dump(mode="json"),
    }


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


@app.post("/api/v1/modules", response_model=ModuleSummary)
def upsert_module(request: ModuleUpsertRequest) -> ModuleSummary:
    module_id = request.module_id.strip()
    module_name = request.module_name.strip()
    if not module_id:
        raise HTTPException(status_code=400, detail="module_id must not be empty.")
    if not module_name:
        raise HTTPException(status_code=400, detail="module_name must not be empty.")
    return module_store.upsert_module(module_id, module_name)


@app.get("/api/v1/modules", response_model=ModuleListResponse)
def list_modules() -> ModuleListResponse:
    modules = module_store.list_modules()
    active_module = module_store.get_active_module()
    return ModuleListResponse(
        modules=modules,
        active_module_id=active_module.module_id if active_module else None,
    )


@app.post("/api/v1/modules/{module_id}/materials", response_model=MaterialSummary)
async def upload_module_material(
    module_id: str,
    file: UploadFile = File(...),
    material_name: str = Form(...),
    material_type: str | None = Form(default=None),
) -> MaterialSummary:
    module = module_store.get_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail=f"Module not found: {module_id}")

    file_bytes = await file.read(settings.material_upload_max_bytes + 1)
    if len(file_bytes) > settings.material_upload_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum size of {settings.material_upload_max_bytes} bytes.",
        )

    try:
        return module_store.add_material(
            module_id=module.module_id,
            material_name=material_name,
            material_type=material_type,
            original_filename=file.filename or "upload.bin",
            file_bytes=file_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/modules/active", response_model=ActiveModuleResponse)
def set_active_module(request: ActiveModuleRequest) -> ActiveModuleResponse:
    module = module_store.set_active_module(request.module_id)
    if module is None:
        raise HTTPException(status_code=404, detail=f"Module not found: {request.module_id}")
    return ActiveModuleResponse(
        active_module_id=module.module_id,
        active_module_name=module.module_name,
    )


@app.get("/api/v1/modules/active", response_model=ActiveModuleResponse)
def get_active_module() -> ActiveModuleResponse:
    module = module_store.get_active_module()
    if module is None:
        return ActiveModuleResponse(active_module_id=None, active_module_name=None)
    return ActiveModuleResponse(
        active_module_id=module.module_id,
        active_module_name=module.module_name,
    )


@app.post("/api/v1/captures", response_model=CaptureResponse)
async def create_capture(payload: CaptureRequest) -> CaptureResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image_base64: {exc}") from exc

    capture_id = _sanitize_capture_id(payload.capture_id or str(uuid4()))
    thread_id = _sanitize_thread_id((payload.thread_id or "").strip() or capture_id)
    response_turn_index = max(0, int(payload.turn_index))
    if (payload.user_input_text or "").strip():
        response_turn_index += 1

    filename = f"{capture_id}.png"
    capture_path = Path(settings.captures_dir) / filename
    capture_path.write_bytes(image_bytes)

    course_id = _normalize_course_id(payload.course_id or payload.module_id)
    existing_state = store.read()

    syllabus = _load_syllabus()
    extraction = vision_client.extract(image_bytes)
    capture_text = " ".join(
        part for part in [extraction.raw_text.strip(), extraction.summary.strip()] if part
    ).strip()
    resolved_module = _resolve_module(payload.module_id or course_id)
    source_context = (
        _build_source_context(resolved_module, capture_text, extraction.tags)
        if resolved_module is not None
        else None
    )
    grounding_query_text = " ".join(
        part
        for part in [
            extraction.raw_text,
            extraction.summary,
            " ".join(extraction.tags),
            payload.user_input_text or "",
            payload.previous_prompt or "",
        ]
        if part and str(part).strip()
    )
    grounding_bundle = _build_grounding_bundle(
        state=existing_state,
        module_id=resolved_module.module_id if resolved_module is not None else None,
        course_id=course_id,
        query_text=grounding_query_text,
    )
    for warning in grounding_bundle.warnings:
        _log_bridge_event(
            event="grounding_warning",
            endpoint_path="/api/v1/captures",
            capture_id=capture_id,
            reason=warning,
            course_id=course_id,
            module_id=resolved_module.module_id if resolved_module is not None else None,
        )

    source_warning = _merge_warning_messages(
        _source_warning_for(resolved_module, source_context),
        grounding_bundle.warnings,
    )
    socratic = socratic_client.generate(
        payload,
        extraction,
        syllabus,
        grounding_context=grounding_bundle.context_text or None,
        grounding_sources=grounding_bundle.citations or None,
    )

    gap_module_id = source_context.module_id if source_context is not None else None
    gap_material_id = source_context.material_id if source_context is not None else None

    new_gaps: list[KnowledgeGap] = []
    for raw_gap in socratic.gaps:
        concept = str(raw_gap.get("concept", "Unknown Concept")).strip() or "Unknown Concept"
        severity = max(0.0, min(1.0, float(raw_gap.get("severity", 0.5))))
        confidence = max(0.0, min(1.0, float(raw_gap.get("confidence", 0.6))))
        basis_question = _optional_text(raw_gap.get("basis_question"), max_chars=320)
        basis_answer_excerpt = _optional_text(raw_gap.get("basis_answer_excerpt"), max_chars=320)
        gap_type = _normalize_gap_type(raw_gap.get("gap_type"))
        deadline_score = _deadline_score_for_concept(concept, syllabus)
        priority_score = max(0.0, min(1.0, (severity * 0.7) + (deadline_score * 0.3)))

        new_gaps.append(
            KnowledgeGap(
                concept=concept,
                severity=severity,
                confidence=confidence,
                basis_question=basis_question,
                basis_answer_excerpt=basis_answer_excerpt,
                gap_type=gap_type,
                course_id=course_id,
                module_id=gap_module_id,
                material_id=gap_material_id,
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
        course_id=course_id,
        module_id=gap_module_id,
        material_id=gap_material_id,
        source_warning=source_warning,
        source_context=source_context,
    )

    merged_gaps = [*existing_state.gaps, *new_gaps]
    readiness = calculate_readiness(merged_gaps)
    state = store.append_capture(event, new_gaps, readiness)

    session_summary = " ".join(socratic.socratic_prompt.split())[:220] or "Socratic turn"
    topic_name = _topic_label_from_gaps(new_gaps) or "General"
    state.sessions.append(
        SessionEvent(
            course_id=course_id,
            thread_id=thread_id,
            turn_index=response_turn_index,
            summary=session_summary,
            topic=topic_name,
            gap_ids=[item.gap_id for item in new_gaps],
            capture_id=capture_id,
        )
    )
    state.readiness_axes = calculate_readiness(state.gaps)
    state = _save_state(state)
    await _publish_state(state)
    _log_bridge_event(
        event="capture_processed",
        endpoint_path="/api/v1/captures",
        capture_id=capture_id,
        course_id=course_id,
        module_id=gap_module_id,
        grounding_citation_count=len(grounding_bundle.citations),
        module_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "module:"),
        course_doc_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "course-doc:"),
        grounding_warning_count=len(grounding_bundle.warnings),
    )

    return CaptureResponse(
        capture_id=capture_id,
        thread_id=thread_id,
        turn_index=response_turn_index,
        socratic_prompt=socratic.socratic_prompt,
        gaps=new_gaps,
        readiness_axes=state.readiness_axes,
        topic_label=topic_name,
        course_id=course_id,
        source_warning=source_warning,
        source_context=source_context,
    )


@app.post("/api/v1/quizzes/submit", response_model=QuizSubmitResponse)
async def submit_quiz(request: QuizSubmitRequest) -> QuizSubmitResponse:
    state = _recompute_derived(store.read())
    if not state.question_bank:
        raise HTTPException(status_code=400, detail="Question bank is empty.")
    if not request.answers:
        raise HTTPException(status_code=400, detail="Quiz answers must not be empty.")

    normalized_course_id = _normalize_course_id(request.course_id)
    normalized_topic = _normalize_topic(request.topic)
    topic_is_all = normalized_topic.lower() == "all topics"
    selected_sources = set(request.sources) if request.sources else {"pyq", "tutorial", "sentinel"}
    selected_module = _resolve_module(request.module_id)
    selected_module_id = selected_module.module_id if selected_module is not None else _normalize_module_id(request.module_id) or None

    question_by_id = {item.question_id: item for item in state.question_bank}
    question_results: list[QuizQuestionResult] = []

    for answer in request.answers:
        item = question_by_id.get(answer.question_id)
        if item is None:
            raise HTTPException(status_code=400, detail=f"Unknown question_id: {answer.question_id}")
        if not _question_visible_for_course(item, normalized_course_id):
            raise HTTPException(status_code=400, detail=f"Question course mismatch for {answer.question_id}.")
        if not _question_visible_for_module(item, selected_module_id):
            raise HTTPException(status_code=400, detail=f"Question module mismatch for {answer.question_id}.")
        if item.source not in selected_sources:
            raise HTTPException(status_code=400, detail=f"Question source mismatch for {answer.question_id}.")
        if not topic_is_all and _normalize_topic(item.topic).lower() != normalized_topic.lower():
            raise HTTPException(status_code=400, detail=f"Question topic mismatch for {answer.question_id}.")

        user_answer = " ".join(answer.user_answer.strip().split())
        correct_answer = " ".join(item.correct_answer.strip().split())
        is_correct = _normalize_concept(user_answer) == _normalize_concept(correct_answer)
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
        raise HTTPException(status_code=400, detail="No quiz results computed.")

    total_questions = len(question_results)
    correct_answers = sum(1 for result in question_results if result.is_correct)
    score = _clamp(correct_answers / total_questions)
    effective_topic = _normalize_topic(question_results[0].topic if topic_is_all else normalized_topic)
    quiz = QuizRecord(
        topic=effective_topic,
        sources=sorted(selected_sources),
        total_questions=total_questions,
        correct_answers=correct_answers,
        score=score,
        results=question_results,
        course_id=normalized_course_id,
        module_id=selected_module_id,
    )

    before_mastery = state.readiness_axes.concept_mastery
    existing_topic = _find_topic_mastery_row(
        state,
        course_id=normalized_course_id,
        topic_name=effective_topic,
    )
    if existing_topic is not None:
        before_mastery = existing_topic.current
    mastery_delta = _clamp((score - 0.6) * 0.18, -0.08, 0.08)
    after_mastery = _clamp(before_mastery + mastery_delta)
    topic_updates = [
        TopicUpdate(
            topic=effective_topic,
            before_mastery=before_mastery,
            after_mastery=after_mastery,
            delta=after_mastery - before_mastery,
        )
    ]

    syllabus = _load_syllabus()
    new_gap_ids: list[str] = []
    new_gaps: list[KnowledgeGap] = []
    seen_concepts: set[str] = set()
    for result in question_results:
        if result.is_correct:
            continue
        concept = f"{result.topic}: {result.concept}".strip(": ")
        concept_key = _normalize_concept(concept)
        if concept_key in seen_concepts:
            continue
        seen_concepts.add(concept_key)

        severity = _clamp(0.5 + (1.0 - score) * 0.4)
        confidence = _clamp(0.65 + (1.0 - score) * 0.2)
        deadline_score = _deadline_score_for_concept(result.concept or result.topic, syllabus)
        priority_score = _clamp((severity * 0.7) + (deadline_score * 0.3))
        gap = KnowledgeGap(
            concept=concept,
            severity=severity,
            confidence=confidence,
            basis_question=f"Quiz miss: {result.question_id}",
            basis_answer_excerpt=(result.user_answer[:320] or None),
            gap_type="concept",
            course_id=normalized_course_id,
            module_id=selected_module_id,
            material_id=None,
            capture_id=f"quiz-{quiz.quiz_id}",
            evidence_url=f"quiz://{result.question_id}",
            deadline_score=deadline_score,
            priority_score=priority_score,
        )
        new_gaps.append(gap)
        new_gap_ids.append(gap.gap_id)

    state.quizzes.append(quiz)
    state.gaps.extend(new_gaps)
    state.readiness_axes = calculate_readiness(state.gaps)
    state = _save_state(state)
    await _publish_state(state)
    _log_bridge_event(
        event="quiz_submitted",
        endpoint_path="/api/v1/quizzes/submit",
        course_id=normalized_course_id,
        module_id=selected_module_id,
        quiz_id=quiz.quiz_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        new_gap_count=len(new_gaps),
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
        raise HTTPException(status_code=404, detail=f"Gap not found: {gap_id}")

    state.readiness_axes = calculate_readiness(state.gaps)
    state = _save_state(state)
    await _publish_state(state)
    return {"ok": True, "gap_id": gap_id, "status": request.status}


@app.get("/api/v1/courses/{course_id}/deadlines")
def list_course_deadlines(course_id: str) -> dict:
    normalized = _normalize_course_id(course_id)
    state = _recompute_derived(store.read())
    if normalized == "all":
        deadlines = state.deadlines
    else:
        deadlines = [item for item in state.deadlines if _normalize_course_id(item.course_id) == normalized]
    return {"course_id": normalized, "deadlines": [item.model_dump(mode="json") for item in deadlines]}


@app.post("/api/v1/courses/{course_id}/deadlines", response_model=CourseDeadline)
async def create_course_deadline(course_id: str, request: CreateDeadlineRequest) -> CourseDeadline:
    normalized = _normalize_course_id(request.course_id or course_id)
    deadline = CourseDeadline(
        course_id=normalized,
        name=request.name.strip(),
        due_date=request.due_date,
        readiness_score=max(0.0, min(1.0, float(request.readiness_score))),
        associated_gap_ids=list(request.associated_gap_ids),
    )
    state = store.read()
    state.deadlines.append(deadline)
    state = _save_state(state)
    await _publish_state(state)
    return deadline


@app.get("/api/v1/courses/{course_id}/documents")
def list_course_documents(course_id: str) -> dict:
    normalized = _normalize_course_id(course_id)
    state = _recompute_derived(store.read())
    if normalized == "all":
        documents = state.documents
    else:
        documents = [item for item in state.documents if _normalize_course_id(item.course_id) == normalized]
    return {"course_id": normalized, "documents": [item.model_dump(mode="json") for item in documents]}


@app.post("/api/v1/courses/{course_id}/documents/upload", response_model=CourseDocument)
async def upload_course_document(
    course_id: str,
    file: UploadFile = File(...),
    module_id: str = Form(...),
    document_name: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
) -> CourseDocument:
    normalized = _normalize_course_id(course_id)
    normalized_module_id = _normalize_module_id(module_id)
    if not normalized_module_id:
        _log_bridge_event(
            event="document_upload_validation_failed",
            endpoint_path="/api/v1/courses/{course_id}/documents/upload",
            course_id=normalized,
            reason="module_id must not be empty.",
        )
        raise HTTPException(status_code=400, detail="module_id must not be empty.")

    module = module_store.get_module(normalized_module_id)
    if module is None:
        _log_bridge_event(
            event="document_upload_validation_failed",
            endpoint_path="/api/v1/courses/{course_id}/documents/upload",
            course_id=normalized,
            module_id=normalized_module_id,
            reason=f"module_id '{normalized_module_id}' was not found.",
        )
        raise HTTPException(status_code=404, detail=f"Module not found: {normalized_module_id}")

    raw_bytes = await file.read(settings.material_upload_max_bytes + 1)
    if len(raw_bytes) > settings.material_upload_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum size of {settings.material_upload_max_bytes} bytes.",
        )
    safe_name = _sanitize_filename(file.filename or "upload.bin")
    doc_id = str(uuid4())
    folder = settings.documents_dir / normalized
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{doc_id}_{safe_name}"
    target = folder / stored_name
    target.write_bytes(raw_bytes)

    display_name = (document_name or "").strip() or safe_name
    doc_type = (document_type or "").strip().lower() or Path(safe_name).suffix.lower().lstrip(".") or "other"
    file_url = f"http://{settings.bridge_host}:{settings.bridge_port}/course-documents/{normalized}/{stored_name}"

    document = CourseDocument(
        doc_id=doc_id,
        course_id=normalized,
        module_id=module.module_id,
        name=display_name,
        size_bytes=len(raw_bytes),
        type=doc_type,
        file_url=file_url,
        is_anchor=False,
    )

    state = store.read()
    state.documents.append(document)
    state = _save_state(state)
    await _publish_state(state)
    return document


@app.post("/api/v1/courses/{course_id}/documents/{doc_id}/anchor")
async def set_course_document_anchor(course_id: str, doc_id: str) -> dict:
    normalized = _normalize_course_id(course_id)
    state = store.read()
    target: CourseDocument | None = None
    for document in state.documents:
        if _normalize_course_id(document.course_id) == normalized:
            document.is_anchor = False
        if _normalize_course_id(document.course_id) == normalized and document.doc_id == doc_id:
            target = document

    if target is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    target.is_anchor = True
    state = _save_state(state)
    await _publish_state(state)
    return {"ok": True, "course_id": normalized, "doc_id": doc_id, "is_anchor": True}


@app.delete("/api/v1/courses/{course_id}/documents/{doc_id}")
async def delete_course_document(course_id: str, doc_id: str) -> dict:
    normalized = _normalize_course_id(course_id)
    state = store.read()
    target = next(
        (
            item
            for item in state.documents
            if _normalize_course_id(item.course_id) == normalized and item.doc_id == doc_id
        ),
        None,
    )
    if target is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    state.documents = [
        item
        for item in state.documents
        if not (_normalize_course_id(item.course_id) == normalized and item.doc_id == doc_id)
    ]

    if target.file_url.startswith(f"http://{settings.bridge_host}:{settings.bridge_port}/course-documents/"):
        relative = target.file_url.split("/course-documents/", 1)[1]
        candidate = settings.documents_dir / relative
        if candidate.exists():
            candidate.unlink(missing_ok=True)

    state = _save_state(state)
    await _publish_state(state)
    return {"ok": True, "course_id": normalized, "doc_id": doc_id}


@app.get("/api/v1/courses/{course_id}/sessions")
def list_course_sessions(course_id: str) -> dict:
    normalized = _normalize_course_id(course_id)
    state = _recompute_derived(store.read())
    if normalized == "all":
        sessions = state.sessions
    else:
        sessions = [item for item in state.sessions if _normalize_course_id(item.course_id) == normalized]
    sessions_sorted = sorted(sessions, key=lambda item: item.timestamp_utc, reverse=True)
    return {"course_id": normalized, "sessions": [item.model_dump(mode="json") for item in sessions_sorted]}


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask_sentinel(request: AskRequest) -> AskResponse:
    normalized = _normalize_course_id(request.course_id)
    thread_id = _sanitize_thread_id((request.thread_id or "").strip() or str(uuid4()))
    next_turn = max(0, int(request.turn_index)) + 1
    state = store.read()
    syllabus = _load_syllabus()
    active_module = _resolve_module(None)
    grounding_bundle = _build_grounding_bundle(
        state=state,
        module_id=active_module.module_id if active_module is not None else None,
        course_id=normalized,
        query_text=request.message,
    )
    for warning in grounding_bundle.warnings:
        _log_bridge_event(
            event="grounding_warning",
            endpoint_path="/api/v1/ask",
            reason=warning,
            course_id=normalized,
            module_id=active_module.module_id if active_module is not None else None,
        )

    prompt = socratic_client.ask(
        message=request.message,
        thread_id=thread_id,
        turn_index=next_turn,
        course_id=normalized,
        grounding_context=grounding_bundle.context_text or None,
        grounding_sources=grounding_bundle.citations or None,
        syllabus=syllabus,
    )

    citations = grounding_bundle.citations[:3]

    state.sessions.append(
        SessionEvent(
            course_id=normalized,
            thread_id=thread_id,
            turn_index=next_turn,
            summary=" ".join(request.message.split())[:220],
            topic="General",
            gap_ids=[],
            capture_id=None,
        )
    )

    state = _save_state(state)
    await _publish_state(state)
    _log_bridge_event(
        event="ask_processed",
        endpoint_path="/api/v1/ask",
        course_id=normalized,
        module_id=active_module.module_id if active_module is not None else None,
        thread_id=thread_id,
        turn_index=next_turn,
        grounding_citation_count=len(grounding_bundle.citations),
        module_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "module:"),
        course_doc_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "course-doc:"),
        grounding_warning_count=len(grounding_bundle.warnings),
    )

    return AskResponse(
        thread_id=thread_id,
        turn_index=next_turn,
        socratic_prompt=prompt,
        citations=citations,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.bridge_host, port=8000, reload=True)
