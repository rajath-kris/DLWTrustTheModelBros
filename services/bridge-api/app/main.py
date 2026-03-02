from __future__ import annotations

import base64
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .friend_agent_adapter import FriendAgentAdapter, FriendAgentResult
from .grounding import GroundingBundle, chunk_text, extract_supported_text, select_top_chunks, tokenize
from .models import (
    CaptureEvent,
    CaptureRequest,
    CaptureResponse,
    CourseDeadline,
    CourseDocument,
    CourseSummary,
    CreateDeadlineRequest,
    DocumentRetagRequest,
    EventEnvelope,
    GapStatusUpdate,
    KnowledgeGap,
    LearningState,
    QuestionBankItem,
    QuizPrepareRequest,
    QuizPrepareResponse,
    QuizQuestionResult,
    QuizRecord,
    QuizSelectionSummary,
    QuizSubmitRequest,
    QuizSubmitResponse,
    SessionEvent,
    SentinelRuntimeActionResponse,
    SentinelRuntimeStatus,
    SourceContext,
    StudyAction,
    TopicUpdate,
    TopicMasteryItem,
    utc_now_iso,
)
from .topic_models import (
    ActiveTopicRequest,
    ActiveTopicResponse,
    MaterialSummary,
    TopicListResponse,
    TopicSummary,
    TopicUpsertRequest,
)
from .topic_store import TopicStore
from .openai_clients import OpenAISocraticClient, OpenAIVisionClient
from .quiz_seeding import QuizSeeder
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
settings.topics_dir.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(settings.captures_dir)), name="captures")
app.mount(
    "/course-documents",
    StaticFiles(directory=str(settings.documents_dir)),
    name="course-documents",
)
app.mount(
    "/topic-materials",
    StaticFiles(directory=str(settings.topics_dir)),
    name="topic-materials",
)

store = StateStore(settings.state_file)
broker = SSEBroker()
vision_client = OpenAIVisionClient(settings)
socratic_client = OpenAISocraticClient(settings)
quiz_seeder = QuizSeeder(settings)
friend_agent = FriendAgentAdapter(settings)
topic_store = TopicStore(settings.topics_dir, vision_client)
runtime_manager = SentinelRuntimeManager(settings)

MATCH_THRESHOLD = 0.22
WEAK_MATCH_THRESHOLD = 0.14
TOPIC_INFERENCE_MIN_SCORE = MATCH_THRESHOLD
TOPIC_INFERENCE_MIN_MARGIN = 0.0
TOPIC_INFERENCE_STRONG_SCORE = 0.45
MAX_STUDY_ACTIONS = 5
TOPIC_GROUNDING_LIMIT = 2
COURSE_DOC_GROUNDING_LIMIT = 2
GROUNDING_MAX_CONTEXT_CHARS = 6200
NO_ACTIVE_TOPIC_WARNING = (
    "No topic could be inferred from this capture/topic; using course documents and best-effort grounding."
)
NO_MATCH_WARNING_TEMPLATE = (
    "No close match found in topic materials for inferred topic '{topic_name}'; using broader document grounding."
)
FALLBACK_TOPIC_ID = "topic-general"
FALLBACK_TOPIC_NAME = "General Materials"
LEGACY_FALLBACK_TOPIC_IDS = {"module-general"}
INFERENCE_EXCLUDED_TOPIC_IDS = {
    "topic-fallback-grounding",
    "module-fallback-grounding",
    FALLBACK_TOPIC_ID,
    *LEGACY_FALLBACK_TOPIC_IDS,
}
NO_SOURCE_CAPTURE_PROMPT = (
    "I couldn't find a matching source for this capture. "
    "Please capture content from your uploaded topics so I can ground the guidance."
)


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


def _normalize_topic_id(raw: str | None) -> str:
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


def _is_fallback_topic_id(topic_id: str | None) -> bool:
    normalized = _normalize_topic_id(topic_id)
    if not normalized:
        return False
    return normalized in {FALLBACK_TOPIC_ID, *LEGACY_FALLBACK_TOPIC_IDS}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _question_visible_for_course(item: QuestionBankItem, course_id: str) -> bool:
    normalized = _normalize_course_id(course_id)
    item_course = _normalize_course_id(item.course_id)
    return normalized == "all" or item_course in {"all", normalized}


def _question_visible_for_topic(item: QuestionBankItem, topic_id: str | None) -> bool:
    requested = _normalize_topic_id(topic_id)
    if not requested:
        return True
    item_topic = _normalize_topic_id(item.topic_id)
    return item_topic in {"", requested}


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


def _resolve_topic(topic_id: str | None) -> TopicSummary | None:
    requested_topic_id = (topic_id or "").strip()
    if requested_topic_id:
        requested_topic = topic_store.get_topic(requested_topic_id)
        if requested_topic is not None:
            return requested_topic
    return topic_store.get_active_topic()


def _resolve_requested_topic(topic_id: str | None) -> TopicSummary | None:
    requested_topic_id = (topic_id or "").strip()
    if not requested_topic_id:
        return None
    return topic_store.get_topic(requested_topic_id)


def _infer_best_topic_for_signal(
    *,
    signal_text: str,
    signal_tags: list[str] | None = None,
    minimum_score: float = 0.0,
    minimum_margin: float = 0.0,
    strong_score_override: float = 1.0,
) -> tuple[TopicSummary | None, float, int, float]:
    compact_text = " ".join((signal_text or "").split())
    tags = [item for item in (signal_tags or []) if " ".join(item.split())]
    if not compact_text and not tags:
        return None, 0.0, 0, 0.0

    candidates = topic_store.list_topics()
    scored_candidates: list[tuple[float, TopicSummary]] = []
    candidate_count = 0
    for topic in candidates:
        if topic.topic_id in INFERENCE_EXCLUDED_TOPIC_IDS:
            continue
        match = topic_store.match_capture(topic.topic_id, compact_text, tags)
        if match is None:
            continue
        candidate_count += 1
        score = _clamp(float(match.match_score))
        scored_candidates.append((score, topic))

    if not scored_candidates:
        return None, 0.0, candidate_count, 0.0

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_topic = scored_candidates[0]
    runner_up_score = scored_candidates[1][0] if len(scored_candidates) > 1 else 0.0
    if best_score < minimum_score:
        return None, _clamp(best_score), candidate_count, _clamp(runner_up_score)

    if len(scored_candidates) > 1 and minimum_margin > 0.0 and best_score < strong_score_override:
        if (best_score - runner_up_score) < minimum_margin:
            return None, _clamp(best_score), candidate_count, _clamp(runner_up_score)

    return best_topic, _clamp(best_score), candidate_count, _clamp(runner_up_score)


def _build_source_context(topic: TopicSummary, extraction_text: str, extraction_tags: list[str]) -> SourceContext:
    match = topic_store.match_capture(topic.topic_id, extraction_text, extraction_tags)
    if match is None:
        return SourceContext(
            topic_id=topic.topic_id,
            topic_name=topic.topic_name,
            material_id=None,
            material_name=None,
            match_score=0.0,
            matched=False,
        )
    score = max(0.0, min(1.0, float(match.match_score)))
    matched = score >= MATCH_THRESHOLD
    return SourceContext(
        topic_id=topic.topic_id,
        topic_name=topic.topic_name,
        material_id=match.material_id,
        material_name=match.material_name,
        match_score=score,
        matched=matched,
    )


def _source_warning_for(topic: TopicSummary | None, source_context: SourceContext | None) -> str | None:
    if topic is None:
        return NO_ACTIVE_TOPIC_WARNING
    if source_context is None:
        return NO_MATCH_WARNING_TEMPLATE.format(topic_name=topic.topic_name)
    score = max(0.0, min(1.0, source_context.match_score))
    if score >= MATCH_THRESHOLD:
        return None
    if score >= WEAK_MATCH_THRESHOLD:
        return NO_MATCH_WARNING_TEMPLATE.format(topic_name=topic.topic_name)
    return NO_MATCH_WARNING_TEMPLATE.format(topic_name=topic.topic_name)


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


def _collect_topic_grounding(topic_id: str | None, query_text: str, limit: int = TOPIC_GROUNDING_LIMIT) -> GroundingBundle:
    requested_topic_id = (topic_id or "").strip()
    if not requested_topic_id:
        return GroundingBundle(context_text="", citations=[], warnings=[])

    topic = topic_store.get_topic(requested_topic_id)
    if topic is None:
        return GroundingBundle(
            context_text="",
            citations=[],
            warnings=[f"Grounding skipped: topic '{requested_topic_id}' was not found."],
        )

    materials = topic_store.list_materials(topic.topic_id)
    query_tokens = set(tokenize(query_text))
    candidates: list[tuple[int, str, str, str | None, str | None]] = []
    warnings: list[str] = []

    for material in materials:
        extracted_path = settings.topics_dir / material.extracted_path
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
        if not top_chunks:
            continue
        citation = f"topic:{topic.topic_name}/{material.material_name}"
        source_url = _topic_material_url(material.source_path)
        source_label = material.material_name
        for chunk in top_chunks:
            score = _score_chunk(query_tokens, chunk)
            if score <= 0:
                continue
            candidates.append((score, chunk, citation, source_url, source_label))

    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[: max(1, int(limit))]
    if not selected and materials:
        warnings.append(
            f"No relevant topic material snippets matched capture context for topic '{topic.topic_name}'."
        )
    context_parts = [f"[{citation}]\n{chunk}" for _, chunk, citation, _, _ in selected if chunk.strip()]
    citations = _dedupe_text_items([citation for _, _, citation, _, _ in selected])
    primary_source_url = next((source_url for _, _, _, source_url, _ in selected if source_url), None)
    primary_source_label = next(
        (source_label for _, _, _, source_url, source_label in selected if source_url and source_label),
        None,
    )
    return GroundingBundle(
        context_text="\n\n---\n\n".join(context_parts),
        citations=citations,
        warnings=_dedupe_text_items(warnings),
        primary_source_url=primary_source_url,
        primary_source_label=primary_source_label,
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


def _topic_material_url(source_path: str | None) -> str | None:
    raw_path = (source_path or "").strip().replace("\\", "/")
    if not raw_path:
        return None
    path_obj = Path(raw_path)
    if path_obj.is_absolute() or ".." in path_obj.parts:
        return None
    normalized = path_obj.as_posix().lstrip("/")
    if not normalized:
        return None
    return f"http://{settings.bridge_host}:{settings.bridge_port}/topic-materials/{normalized}"


def _collect_course_doc_grounding(
    state: LearningState,
    course_id: str,
    topic_id: str | None,
    query_text: str,
    limit: int = COURSE_DOC_GROUNDING_LIMIT,
) -> GroundingBundle:
    normalized = _normalize_course_id(course_id)
    target_topic_id = _normalize_topic_id(topic_id)

    course_scoped_docs = [
        doc
        for doc in state.documents
        if normalized == "all"
        or _normalize_course_id(doc.course_id) in {normalized, "all"}
    ]

    warnings: list[str] = []
    if target_topic_id:
        exact_topic_docs = [
            doc for doc in course_scoped_docs if _normalize_topic_id(doc.topic_id) == target_topic_id
        ]
        fallback_topic_docs = [
            doc for doc in course_scoped_docs if _is_fallback_topic_id(doc.topic_id)
        ]
        use_fallback = len(exact_topic_docs) == 0 and len(fallback_topic_docs) > 0
        eligible_docs = fallback_topic_docs if use_fallback else exact_topic_docs
        if use_fallback:
            warnings.append(
                f"Grounding used fallback course documents from '{FALLBACK_TOPIC_ID}' because no documents matched topic '{target_topic_id}'."
            )
    else:
        eligible_docs = course_scoped_docs

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
    candidates: list[tuple[int, str, str, str | None, str | None]] = []

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
        if not selected_chunks:
            continue
        citation = f"course-doc:{document.name}"
        for chunk in selected_chunks:
            score = _score_chunk(query_tokens, chunk)
            if score <= 0:
                continue
            candidates.append((score, chunk, citation, document.file_url, document.name))

    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[: max(1, int(limit))]
    if not selected and ordered_docs:
        warnings.append("No relevant course document snippets matched capture context.")
    context_parts = [f"[{citation}]\n{chunk}" for _, chunk, citation, _, _ in selected if chunk.strip()]
    citations = _dedupe_text_items([citation for _, _, citation, _, _ in selected])
    primary_source_url = next((source_url for _, _, _, source_url, _ in selected if source_url), None)
    primary_source_label = next(
        (source_label for _, _, _, source_url, source_label in selected if source_url and source_label),
        None,
    )
    return GroundingBundle(
        context_text="\n\n---\n\n".join(context_parts),
        citations=citations,
        warnings=_dedupe_text_items(warnings),
        primary_source_url=primary_source_url,
        primary_source_label=primary_source_label,
    )


def _build_grounding_bundle(
    *,
    state: LearningState,
    topic_id: str | None,
    course_id: str,
    query_text: str,
) -> GroundingBundle:
    topic_bundle = _collect_topic_grounding(
        topic_id=topic_id,
        query_text=query_text,
        limit=TOPIC_GROUNDING_LIMIT,
    )
    course_bundle = _collect_course_doc_grounding(
        state=state,
        course_id=course_id,
        topic_id=topic_id,
        query_text=query_text,
        limit=COURSE_DOC_GROUNDING_LIMIT,
    )

    combined_context = "\n\n".join(
        part
        for part in [topic_bundle.context_text.strip(), course_bundle.context_text.strip()]
        if part
    )
    if len(combined_context) > GROUNDING_MAX_CONTEXT_CHARS:
        combined_context = combined_context[: GROUNDING_MAX_CONTEXT_CHARS - 3].rstrip()
        combined_context = f"{combined_context}..."

    combined_citations = _dedupe_text_items([*topic_bundle.citations, *course_bundle.citations])
    combined_warnings = _dedupe_text_items([*topic_bundle.warnings, *course_bundle.warnings])
    combined_primary_source_url = topic_bundle.primary_source_url or course_bundle.primary_source_url
    combined_primary_source_label = topic_bundle.primary_source_label or course_bundle.primary_source_label
    return GroundingBundle(
        context_text=combined_context,
        citations=combined_citations,
        warnings=combined_warnings,
        primary_source_url=combined_primary_source_url,
        primary_source_label=combined_primary_source_label,
    )


def _is_pdf_document(document: CourseDocument, file_path: Path | None) -> bool:
    if file_path is not None and file_path.suffix.lower() == ".pdf":
        return True
    if document.type.lower() == "pdf":
        return True
    return document.name.lower().endswith(".pdf")


def _select_friend_notes_path(
    *,
    state: LearningState,
    course_id: str,
    topic_id: str | None,
) -> str | None:
    if settings.friend_agent_notes_path:
        configured_path = Path(settings.friend_agent_notes_path).expanduser()
        if configured_path.exists():
            return str(configured_path.resolve())

    normalized_course = _normalize_course_id(course_id)
    normalized_topic = _normalize_topic_id(topic_id)

    eligible_docs: list[CourseDocument] = []
    for document in state.documents:
        if normalized_course != "all" and _normalize_course_id(document.course_id) not in {normalized_course, "all"}:
            continue
        if normalized_topic and _normalize_topic_id(document.topic_id) != normalized_topic and not _is_fallback_topic_id(
            document.topic_id
        ):
            continue
        eligible_docs.append(document)

    anchored = sorted(
        [doc for doc in eligible_docs if doc.is_anchor],
        key=lambda item: item.uploaded_at,
        reverse=True,
    )
    regular = sorted(
        [doc for doc in eligible_docs if not doc.is_anchor],
        key=lambda item: item.uploaded_at,
        reverse=True,
    )

    for document in [*anchored, *regular]:
        path = _course_document_path_from_url(document.file_url)
        if path is None or not path.exists():
            continue
        if _is_pdf_document(document, path):
            return str(path)
    return None


def _build_friend_capture_user_text(payload: CaptureRequest, extraction: VisionExtraction) -> str:
    if (payload.user_input_text or "").strip():
        return payload.user_input_text.strip()
    summary = extraction.summary.strip()
    raw_text = extraction.raw_text.strip()
    tags = ", ".join(extraction.tags[:5])
    parts = [part for part in [summary, raw_text, tags] if part]
    if parts:
        return f"I need help with this screenshot context: {' | '.join(parts)}"
    return "I need help understanding this screenshot."


def _build_topic_signal_text(payload: CaptureRequest, extraction: VisionExtraction) -> str:
    user_text = " ".join((payload.user_input_text or "").split()).strip()
    if user_text:
        return user_text
    return " ".join(
        part
        for part in [
            extraction.raw_text,
            extraction.summary,
            payload.previous_prompt or "",
        ]
        if part and str(part).strip()
    ).strip()


def _build_grounding_query_text(payload: CaptureRequest, extraction: VisionExtraction) -> str:
    user_text = " ".join((payload.user_input_text or "").split()).strip()
    if user_text:
        return user_text
    return " ".join(
        part
        for part in [
            extraction.raw_text,
            extraction.summary,
            " ".join(extraction.tags),
            payload.previous_prompt or "",
        ]
        if part and str(part).strip()
    ).strip()


def _friend_result_to_gap_payloads(
    *,
    result: FriendAgentResult,
    extraction: VisionExtraction,
    syllabus: dict,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    seen_concepts: set[str] = set()
    dashboard_gaps = result.dashboard_state.get("gaps")
    if isinstance(dashboard_gaps, dict):
        for topic, raw_entry in dashboard_gaps.items():
            if not isinstance(raw_entry, dict):
                continue
            topic_name = " ".join(str(topic).split()).strip() or "General"
            mastery = _clamp(float(raw_entry.get("mastery", 0.5)))
            attempts = max(1, int(raw_entry.get("attempts", 1)))
            confused_about = _optional_text(raw_entry.get("confused_about"), max_chars=200)
            concept = confused_about or topic_name
            concept_key = _normalize_concept(concept)
            if concept_key in seen_concepts:
                continue
            seen_concepts.add(concept_key)
            severity = _clamp(1.0 - mastery)
            confidence = _clamp(0.55 + min(attempts, 8) * 0.05)
            deadline_score = _deadline_score_for_concept(concept, syllabus)
            payloads.append(
                {
                    "concept": concept,
                    "severity": severity,
                    "confidence": confidence,
                    "basis_question": f"Friend agent focus: {topic_name}",
                    "basis_answer_excerpt": result.reply[:320],
                    "gap_type": "concept",
                    "deadline_score": deadline_score,
                    "priority_score": _clamp((severity * 0.7) + (deadline_score * 0.3)),
                }
            )
            if len(payloads) >= 3:
                break

    if payloads:
        return payloads

    seed_concept = extraction.tags[0].replace("_", " ").title() if extraction.tags else "Concept interpretation"
    deadline_score = _deadline_score_for_concept(seed_concept, syllabus)
    return [
        {
            "concept": seed_concept,
            "severity": 0.58,
            "confidence": 0.62,
            "basis_question": "Friend agent fallback",
            "basis_answer_excerpt": result.reply[:320],
            "gap_type": "reasoning",
            "deadline_score": deadline_score,
            "priority_score": _clamp((0.58 * 0.7) + (deadline_score * 0.3)),
        }
    ]


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


def _nearest_deadline_days_for_scope(deadlines: list[CourseDeadline], course_id: str) -> int | None:
    normalized_course = _normalize_course_id(course_id)
    if normalized_course != "all":
        return _nearest_deadline_days(deadlines, normalized_course)

    now = datetime.now(timezone.utc)
    best: int | None = None
    for deadline in deadlines:
        try:
            due = datetime.fromisoformat(deadline.due_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        days = int((due - now).total_seconds() // 86400)
        if best is None or days < best:
            best = days
    return best


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    divisor = max(1, min(len(left_tokens), len(right_tokens)))
    return _clamp(overlap / divisor)


def _topic_matches_filter(question_topic: str, requested_topic: str) -> bool:
    normalized_requested = _normalize_topic(requested_topic).lower()
    if normalized_requested == "all topics":
        return True
    return _normalize_topic(question_topic).lower() == normalized_requested


def _seed_document_topics_and_questions(
    state: LearningState,
    document: CourseDocument,
    file_path: Path,
    *,
    allow_llm: bool = True,
) -> tuple[int, int, list[str]]:
    result = quiz_seeder.seed_document(
        state=state,
        document=document,
        file_path=file_path,
        replace_existing_doc_questions=True,
        allow_llm=allow_llm,
    )
    return result.topics_added, result.questions_added, result.warnings


def _remove_document_seed_artifacts(state: LearningState, *, doc_id: str) -> tuple[int, int]:
    removed_questions = len(
        [item for item in state.question_bank if item.generated and item.origin_doc_id == doc_id]
    )
    state.question_bank = [
        item for item in state.question_bank if not (item.generated and item.origin_doc_id == doc_id)
    ]

    removed_topics = 0
    kept_topics = []
    for topic in state.topics:
        if doc_id in topic.source_doc_ids:
            topic.source_doc_ids = [value for value in topic.source_doc_ids if value != doc_id]
            topic.updated_at = utc_now_iso()
        if topic.source_doc_ids:
            kept_topics.append(topic)
        else:
            removed_topics += 1
    state.topics = kept_topics
    return removed_topics, removed_questions


def _document_has_seed_artifacts(state: LearningState, doc_id: str) -> bool:
    has_topic = any(doc_id in topic.source_doc_ids for topic in state.topics)
    has_question = any(item.generated and item.origin_doc_id == doc_id for item in state.question_bank)
    return has_topic and has_question


def _backfill_document_topic_seeds() -> None:
    state = store.read()
    changed = False
    seeded_count = 0
    warning_count = 0
    for document in state.documents:
        if _document_has_seed_artifacts(state, document.doc_id):
            continue
        doc_path = _course_document_path_from_url(document.file_url)
        if doc_path is None or not doc_path.exists():
            _log_bridge_event(
                event="topic_seed_skipped",
                endpoint_path="/startup",
                doc_id=document.doc_id,
                topic_id=document.topic_id,
                reason="file_missing_or_unresolvable",
            )
            warning_count += 1
            continue
        topics_added, questions_added, warnings = _seed_document_topics_and_questions(
            state,
            document,
            doc_path,
            allow_llm=False,
        )
        if topics_added > 0 or questions_added > 0:
            changed = True
            seeded_count += 1
            _log_bridge_event(
                event="topic_seed_generated",
                endpoint_path="/startup",
                doc_id=document.doc_id,
                topic_id=document.topic_id,
                topics_added=topics_added,
                questions_added=questions_added,
            )
        for warning in warnings:
            warning_count += 1
            _log_bridge_event(
                event="topic_seed_skipped",
                endpoint_path="/startup",
                doc_id=document.doc_id,
                topic_id=document.topic_id,
                reason=warning,
            )

    if not changed:
        return

    state = _save_state(state)
    _log_bridge_event(
        event="topic_seed_backfill_completed",
        endpoint_path="/startup",
        seeded_documents=seeded_count,
        warning_count=warning_count,
    )


def _build_recent_quiz_miss_scores(
    state: LearningState,
    *,
    course_id: str,
    topic_id: str | None,
) -> dict[str, float]:
    normalized_course = _normalize_course_id(course_id)
    normalized_topic = _normalize_topic_id(topic_id)
    miss_scores: dict[str, float] = {}
    recent_quizzes = sorted(state.quizzes, key=lambda item: item.timestamp_utc, reverse=True)[:10]
    for index, quiz in enumerate(recent_quizzes):
        if normalized_course != "all" and _normalize_course_id(quiz.course_id) not in {normalized_course, "all"}:
            continue
        if normalized_topic and _normalize_topic_id(quiz.topic_id) not in {"", normalized_topic}:
            continue
        decay = 0.82**index
        for result in quiz.results:
            if result.is_correct:
                continue
            miss_scores[result.question_id] = miss_scores.get(result.question_id, 0.0) + decay
    return miss_scores


def _build_recent_question_seen_counts(
    state: LearningState,
    *,
    course_id: str,
    topic_id: str | None,
) -> dict[str, int]:
    normalized_course = _normalize_course_id(course_id)
    normalized_topic = _normalize_topic_id(topic_id)
    seen_counts: dict[str, int] = {}
    recent_quizzes = sorted(state.quizzes, key=lambda item: item.timestamp_utc, reverse=True)[:10]
    for quiz in recent_quizzes:
        if normalized_course != "all" and _normalize_course_id(quiz.course_id) not in {normalized_course, "all"}:
            continue
        if normalized_topic and _normalize_topic_id(quiz.topic_id) not in {"", normalized_topic}:
            continue
        for result in quiz.results:
            seen_counts[result.question_id] = seen_counts.get(result.question_id, 0) + 1
    return seen_counts


def _build_quiz_candidates(
    *,
    state: LearningState,
    course_id: str,
    topic_id: str | None,
    topic: str,
    selected_sources: set[str],
    syllabus: dict,
) -> list[dict[str, object]]:
    normalized_course = _normalize_course_id(course_id)
    normalized_topic = _normalize_topic_id(topic_id)
    open_gaps = [
        gap
        for gap in state.gaps
        if gap.status != "closed"
        and (normalized_course == "all" or _normalize_course_id(gap.course_id) in {"all", normalized_course})
        and (not normalized_topic or _normalize_topic_id(gap.topic_id) in {"", normalized_topic})
    ]
    miss_scores = _build_recent_quiz_miss_scores(
        state,
        course_id=normalized_course,
        topic_id=normalized_topic or None,
    )
    seen_counts = _build_recent_question_seen_counts(
        state,
        course_id=normalized_course,
        topic_id=normalized_topic or None,
    )

    candidates: list[dict[str, object]] = []
    for item in state.question_bank:
        if not _question_visible_for_course(item, normalized_course):
            continue
        if not _question_visible_for_topic(item, normalized_topic or None):
            continue
        if item.source not in selected_sources:
            continue
        if not _topic_matches_filter(item.topic, topic):
            continue

        concept_signal = f"{item.topic} {item.concept}".strip()
        best_gap_match = 0.0
        for gap in open_gaps:
            score = _token_overlap_score(concept_signal, gap.concept)
            if score > best_gap_match:
                best_gap_match = score

        gap_score = min(0.45, best_gap_match * 0.45)
        wrong_repeat_score = min(0.30, miss_scores.get(item.question_id, 0.0) * 0.30)
        deadline_component = min(0.20, _deadline_score_for_concept(item.concept or item.topic, syllabus) * 0.20)

        seen = seen_counts.get(item.question_id, 0)
        freshness_penalty = 0.0
        if seen >= 3:
            freshness_penalty = -0.15
        elif seen == 2:
            freshness_penalty = -0.10
        elif seen == 1:
            freshness_penalty = -0.05
        if deadline_component >= 0.15 and freshness_penalty < -0.03:
            freshness_penalty = -0.03

        base_score = gap_score + wrong_repeat_score + deadline_component + freshness_penalty
        candidates.append(
            {
                "question": item,
                "concept_key": _normalize_concept(item.concept or item.topic),
                "gap_score": gap_score,
                "wrong_repeat_score": wrong_repeat_score,
                "deadline_component": deadline_component,
                "base_score": base_score,
            }
        )
    return candidates


def _prepare_quiz_questions(
    *,
    state: LearningState,
    course_id: str,
    topic_id: str | None,
    topic: str,
    selected_sources: set[str],
    question_count: int,
    syllabus: dict,
) -> tuple[list[QuestionBankItem], QuizSelectionSummary]:
    candidates = _build_quiz_candidates(
        state=state,
        course_id=course_id,
        topic_id=topic_id,
        topic=topic,
        selected_sources=selected_sources,
        syllabus=syllabus,
    )
    if not candidates:
        return [], QuizSelectionSummary()

    nearest_deadline_days = _nearest_deadline_days_for_scope(state.deadlines, course_id)
    deadline_mode = nearest_deadline_days is not None and nearest_deadline_days <= 14

    desired_count = max(1, min(25, int(question_count)))
    gap_target = min(
        len([entry for entry in candidates if float(entry["gap_score"]) > 0.0]),
        int(math.ceil(desired_count * 0.4)),
    )
    wrong_target = 0
    if deadline_mode:
        wrong_target = min(
            len([entry for entry in candidates if float(entry["wrong_repeat_score"]) > 0.0]),
            int(math.ceil(desired_count * 0.2)),
        )

    selected: list[QuestionBankItem] = []
    selected_ids: set[str] = set()
    concept_counts: dict[str, int] = {}
    gap_selected = 0
    wrong_selected = 0
    coverage_selected = 0
    non_gap_available = any(float(entry["gap_score"]) == 0.0 for entry in candidates)

    def try_add(entry: dict[str, object], *, track: str, relax_concept_cap: bool = False) -> bool:
        nonlocal gap_selected, wrong_selected, coverage_selected
        question = entry["question"]
        assert isinstance(question, QuestionBankItem)
        if question.question_id in selected_ids:
            return False
        concept_key = str(entry["concept_key"])
        concept_count = concept_counts.get(concept_key, 0)
        if not relax_concept_cap and concept_count >= 2:
            return False

        selected.append(question)
        selected_ids.add(question.question_id)
        concept_counts[concept_key] = concept_count + 1
        if track == "gap":
            gap_selected += 1
        elif track == "wrong":
            wrong_selected += 1
        else:
            coverage_selected += 1
        return True

    ranked_gap = sorted(
        [entry for entry in candidates if float(entry["gap_score"]) > 0.0],
        key=lambda item: float(item["base_score"]),
        reverse=True,
    )
    ranked_wrong = sorted(
        [entry for entry in candidates if float(entry["wrong_repeat_score"]) > 0.0],
        key=lambda item: float(item["base_score"]),
        reverse=True,
    )

    for entry in ranked_gap:
        if len(selected) >= desired_count or gap_selected >= gap_target:
            break
        try_add(entry, track="gap")

    for entry in ranked_wrong:
        if len(selected) >= desired_count or wrong_selected >= wrong_target:
            break
        try_add(entry, track="wrong")

    def has_non_gap_selected() -> bool:
        selected_ids_local = {item.question_id for item in selected}
        for entry in candidates:
            question = entry["question"]
            assert isinstance(question, QuestionBankItem)
            if question.question_id not in selected_ids_local:
                continue
            if float(entry["gap_score"]) == 0.0:
                return True
        return False

    remaining = [entry for entry in candidates if isinstance(entry.get("question"), QuestionBankItem)]
    while len(selected) < desired_count and remaining:
        best_entry: dict[str, object] | None = None
        best_score = -10_000.0
        for entry in remaining:
            question = entry["question"]
            assert isinstance(question, QuestionBankItem)
            if question.question_id in selected_ids:
                continue
            concept_key = str(entry["concept_key"])
            if concept_counts.get(concept_key, 0) >= 2:
                continue
            diversity_bonus = 0.10 if concept_counts.get(concept_key, 0) == 0 else 0.0
            non_gap_balance_bonus = 0.0
            if non_gap_available and not has_non_gap_selected() and float(entry["gap_score"]) == 0.0:
                non_gap_balance_bonus = 0.25
            candidate_score = float(entry["base_score"]) + diversity_bonus
            candidate_score += non_gap_balance_bonus
            if candidate_score > best_score:
                best_score = candidate_score
                best_entry = entry
        if best_entry is None:
            break
        try_add(best_entry, track="coverage")
        remaining = [entry for entry in remaining if entry["question"] != best_entry["question"]]

    if len(selected) < desired_count:
        relaxed_ranked = sorted(candidates, key=lambda item: float(item["base_score"]), reverse=True)
        for entry in relaxed_ranked:
            if len(selected) >= desired_count:
                break
            try_add(entry, track="coverage", relax_concept_cap=True)

    if non_gap_available and not has_non_gap_selected():
        best_non_gap = None
        best_non_gap_score = -10_000.0
        for entry in candidates:
            question = entry["question"]
            assert isinstance(question, QuestionBankItem)
            if question.question_id in selected_ids:
                continue
            if float(entry["gap_score"]) != 0.0:
                continue
            score = float(entry["base_score"])
            if score > best_non_gap_score:
                best_non_gap_score = score
                best_non_gap = entry

        if best_non_gap is not None:
            if len(selected) < desired_count:
                try_add(best_non_gap, track="coverage", relax_concept_cap=True)
            else:
                replace_index = -1
                replace_score = 10_000.0
                for idx, item in enumerate(selected):
                    candidate_entry = next((entry for entry in candidates if entry["question"] == item), None)
                    if candidate_entry is None:
                        continue
                    if float(candidate_entry["gap_score"]) == 0.0:
                        continue
                    candidate_score = float(candidate_entry["base_score"])
                    if candidate_score < replace_score:
                        replace_index = idx
                        replace_score = candidate_score
                if replace_index >= 0:
                    replaced_question = selected[replace_index]
                    selected_ids.remove(replaced_question.question_id)
                    replacement_question = best_non_gap["question"]
                    assert isinstance(replacement_question, QuestionBankItem)
                    selected[replace_index] = replacement_question
                    selected_ids.add(replacement_question.question_id)
                    coverage_selected += 1

    deadline_boosted_count = 0
    for entry in candidates:
        question = entry["question"]
        assert isinstance(question, QuestionBankItem)
        if question.question_id not in selected_ids:
            continue
        if float(entry["deadline_component"]) >= 0.10:
            deadline_boosted_count += 1

    summary = QuizSelectionSummary(
        gap_matched_count=gap_selected,
        wrong_repeat_count=wrong_selected,
        deadline_boosted_count=deadline_boosted_count,
        coverage_count=coverage_selected,
    )
    return selected, summary


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


def _migrate_document_topic_tags() -> None:
    state_path = settings.state_file
    if not state_path.exists():
        return

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _log_bridge_event(
            event="documents_topic_migration_failed",
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
        if _normalize_topic_id(document.get("topic_id")):
            continue
        missing_count += 1

    if missing_count == 0:
        return

    active_topic = topic_store.get_active_topic()
    if active_topic is not None:
        fallback_topic_id = active_topic.topic_id
        fallback_mode = "active-topic"
    else:
        fallback_topic = topic_store.get_topic(FALLBACK_TOPIC_ID)
        if fallback_topic is None:
            for legacy_topic_id in LEGACY_FALLBACK_TOPIC_IDS:
                fallback_topic = topic_store.get_topic(legacy_topic_id)
                if fallback_topic is not None:
                    break
        if fallback_topic is None:
            fallback_topic = topic_store.upsert_topic(FALLBACK_TOPIC_ID, FALLBACK_TOPIC_NAME)
        fallback_topic_id = fallback_topic.topic_id
        fallback_mode = "topic-general"

    updated_count = 0
    for document in documents_raw:
        if not isinstance(document, dict):
            continue
        if _normalize_topic_id(document.get("topic_id")):
            continue
        document["topic_id"] = fallback_topic_id
        updated_count += 1

    if updated_count == 0:
        return

    try:
        state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log_bridge_event(
            event="documents_topic_migration_failed",
            endpoint_path="/startup",
            reason=f"State file write failure ({type(exc).__name__}).",
            migrated_count=updated_count,
            fallback_topic_id=fallback_topic_id,
        )
        return

    _log_bridge_event(
        event="documents_topic_migrated",
        endpoint_path="/startup",
        migrated_count=updated_count,
        fallback_topic_id=fallback_topic_id,
        fallback_mode=fallback_mode,
    )


_migrate_document_topic_tags()
_backfill_document_topic_seeds()
_log_bridge_event(
    event="ask_endpoint_removed",
    endpoint_path="/startup",
    reason="POST /api/v1/ask removed from public API surface.",
)

if friend_agent.configured:
    if friend_agent.enabled:
        _log_bridge_event(
            event="friend_agent_enabled",
            endpoint_path="/startup",
            reason="Friend agent backend is active.",
            script_path=friend_agent.script_path,
        )
    else:
        _log_bridge_event(
            event="friend_agent_unavailable",
            endpoint_path="/startup",
            reason=friend_agent.load_error or "Failed to initialize friend agent.",
            script_path=friend_agent.script_path,
        )


def _filter_state_for_course(state: LearningState, course_id: str) -> LearningState:
    normalized = _normalize_course_id(course_id)
    if normalized == "all":
        return state

    filtered = state.model_copy(
        update={
            "captures": [item for item in state.captures if _normalize_course_id(item.course_id) == normalized],
            "gaps": [item for item in state.gaps if _normalize_course_id(item.course_id) == normalized],
            "topic_mastery": [item for item in state.topic_mastery if _normalize_course_id(item.course_id) == normalized],
            "topics": [item for item in state.topics if _normalize_course_id(item.course_id) == normalized],
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


@app.post("/api/v1/topics", response_model=TopicSummary)
def upsert_topic(request: TopicUpsertRequest) -> TopicSummary:
    topic_id = request.topic_id.strip()
    topic_name = request.topic_name.strip()
    if not topic_id:
        raise HTTPException(status_code=400, detail="topic_id must not be empty.")
    if not topic_name:
        raise HTTPException(status_code=400, detail="topic_name must not be empty.")
    return topic_store.upsert_topic(topic_id, topic_name)


@app.get("/api/v1/topics", response_model=TopicListResponse)
def list_topics() -> TopicListResponse:
    topics = topic_store.list_topics()
    active_topic = topic_store.get_active_topic()
    return TopicListResponse(
        topics=topics,
        active_topic_id=active_topic.topic_id if active_topic else None,
    )


@app.post("/api/v1/topics/{topic_id}/materials", response_model=MaterialSummary)
async def upload_topic_material(
    topic_id: str,
    file: UploadFile = File(...),
    material_name: str = Form(...),
    material_type: str | None = Form(default=None),
) -> MaterialSummary:
    topic = topic_store.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Topic not found: {topic_id}")

    file_bytes = await file.read(settings.material_upload_max_bytes + 1)
    if len(file_bytes) > settings.material_upload_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum size of {settings.material_upload_max_bytes} bytes.",
        )

    try:
        return topic_store.add_material(
            topic_id=topic.topic_id,
            material_name=material_name,
            material_type=material_type,
            original_filename=file.filename or "upload.bin",
            file_bytes=file_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/topics/active", response_model=ActiveTopicResponse)
def set_active_topic(request: ActiveTopicRequest) -> ActiveTopicResponse:
    topic = topic_store.set_active_topic(request.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Topic not found: {request.topic_id}")
    return ActiveTopicResponse(
        active_topic_id=topic.topic_id,
        active_topic_name=topic.topic_name,
    )


@app.get("/api/v1/topics/active", response_model=ActiveTopicResponse)
def get_active_topic() -> ActiveTopicResponse:
    topic = topic_store.get_active_topic()
    if topic is None:
        return ActiveTopicResponse(active_topic_id=None, active_topic_name=None)
    return ActiveTopicResponse(
        active_topic_id=topic.topic_id,
        active_topic_name=topic.topic_name,
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

    course_id = _normalize_course_id(payload.course_id)
    existing_state = store.read()

    syllabus = _load_syllabus()
    extraction = vision_client.extract(image_bytes)
    capture_text = " ".join(
        part for part in [extraction.raw_text.strip(), extraction.summary.strip()] if part
    ).strip()
    requested_topic_id = _normalize_topic_id(payload.topic_id)
    requested_topic = _resolve_requested_topic(payload.topic_id)
    topic_signal_text = _build_topic_signal_text(payload, extraction)
    grounding_query_text = _build_grounding_query_text(payload, extraction)
    inferred_topic, inferred_score, topic_candidate_count, inferred_runner_up_score = _infer_best_topic_for_signal(
        signal_text=topic_signal_text,
        signal_tags=extraction.tags,
        minimum_score=TOPIC_INFERENCE_MIN_SCORE,
        minimum_margin=TOPIC_INFERENCE_MIN_MARGIN,
        strong_score_override=TOPIC_INFERENCE_STRONG_SCORE,
    )
    context_topic = requested_topic
    source_resolution_mode = "explicit"
    source_resolution_score = 0.0
    if context_topic is None:
        source_resolution_mode = "unresolved"
        if inferred_topic is not None:
            context_topic = inferred_topic
            source_resolution_mode = "inferred"
            source_resolution_score = inferred_score
    source_context = (
        _build_source_context(context_topic, grounding_query_text, extraction.tags)
        if context_topic is not None
        else SourceContext(
            topic_id="",
            topic_name="Unresolved",
            material_id=None,
            material_name=None,
            match_score=0.0,
            matched=False,
        )
    )
    if context_topic is not None and source_resolution_mode == "explicit":
        source_resolution_score = _clamp(source_context.match_score)
    topic_grounded = context_topic is not None and source_context.matched

    grounding_topic = None
    if requested_topic is not None and topic_grounded:
        grounding_topic = requested_topic
    elif inferred_topic is not None and topic_grounded and inferred_score >= TOPIC_INFERENCE_MIN_SCORE:
        grounding_topic = inferred_topic
    if grounding_topic is None:
        grounding_bundle = GroundingBundle(context_text="", citations=[], warnings=[])
    else:
        grounding_bundle = _build_grounding_bundle(
            state=existing_state,
            topic_id=grounding_topic.topic_id if grounding_topic is not None else None,
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
            topic_id=context_topic.topic_id if context_topic is not None else None,
        )

    topic_warning = _source_warning_for(context_topic, source_context)
    if requested_topic_id and requested_topic is None:
        topic_warning = _merge_warning_messages(
            topic_warning,
            f"Requested topic '{requested_topic_id}' was not found; using inferred/broader grounding.",
        )
    source_warning = _merge_warning_messages(topic_warning, grounding_bundle.warnings)
    agent_backend_used = "bridge"
    socratic_prompt: str
    raw_gap_payloads: list[dict[str, object]]

    if not topic_grounded or not grounding_bundle.citations:
        source_warning = _merge_warning_messages(
            source_warning,
            ["Capture did not match uploaded topic material."],
        )
        socratic_prompt = NO_SOURCE_CAPTURE_PROMPT
        raw_gap_payloads = []
        agent_backend_used = "bridge-no-source"
    else:
        if friend_agent.enabled:
            try:
                friend_notes_path = _select_friend_notes_path(
                    state=existing_state,
                    course_id=course_id,
                    topic_id=grounding_topic.topic_id if grounding_topic is not None else None,
                )
                friend_result = friend_agent.chat(
                    thread_id=thread_id,
                    user_text=_build_friend_capture_user_text(payload, extraction),
                    notes_path=friend_notes_path,
                    image_bytes=image_bytes,
                )
                socratic_prompt = friend_result.reply
                raw_gap_payloads = _friend_result_to_gap_payloads(
                    result=friend_result,
                    extraction=extraction,
                    syllabus=syllabus,
                )
                agent_backend_used = "friend"
            except Exception as exc:  # noqa: BLE001
                _log_bridge_event(
                    event="friend_agent_fallback",
                    endpoint_path="/api/v1/captures",
                    capture_id=capture_id,
                    reason=f"{type(exc).__name__}: {exc}",
                    course_id=course_id,
                    topic_id=context_topic.topic_id if context_topic is not None else None,
                )
                socratic = socratic_client.generate(
                    payload,
                    extraction,
                    syllabus,
                    grounding_context=grounding_bundle.context_text or None,
                    grounding_sources=grounding_bundle.citations or None,
                )
                if socratic_client.last_backend_warning:
                    _log_bridge_event(
                        event="bridge_agent_fallback",
                        endpoint_path="/api/v1/captures",
                        capture_id=capture_id,
                        reason=socratic_client.last_backend_warning,
                        agent_backend="bridge",
                        course_id=course_id,
                        topic_id=context_topic.topic_id if context_topic is not None else None,
                    )
                socratic_prompt = socratic.socratic_prompt
                raw_gap_payloads = socratic.gaps
        else:
            socratic = socratic_client.generate(
                payload,
                extraction,
                syllabus,
                grounding_context=grounding_bundle.context_text or None,
                grounding_sources=grounding_bundle.citations or None,
            )
            if socratic_client.last_backend_warning:
                _log_bridge_event(
                    event="bridge_agent_fallback",
                    endpoint_path="/api/v1/captures",
                    capture_id=capture_id,
                    reason=socratic_client.last_backend_warning,
                    agent_backend="bridge",
                    course_id=course_id,
                    topic_id=context_topic.topic_id if context_topic is not None else None,
                )
            socratic_prompt = socratic.socratic_prompt
            raw_gap_payloads = socratic.gaps

    gap_topic_id = source_context.topic_id if source_context is not None and source_context.matched else None
    gap_material_id = source_context.material_id if source_context is not None and source_context.matched else None

    new_gaps: list[KnowledgeGap] = []
    for raw_gap in raw_gap_payloads:
        concept = str(raw_gap.get("concept", "Unknown Concept")).strip() or "Unknown Concept"
        severity = max(0.0, min(1.0, float(raw_gap.get("severity", 0.5))))  # type: ignore[arg-type]
        confidence = max(0.0, min(1.0, float(raw_gap.get("confidence", 0.6))))  # type: ignore[arg-type]
        basis_question = _optional_text(raw_gap.get("basis_question"), max_chars=320)
        basis_answer_excerpt = _optional_text(raw_gap.get("basis_answer_excerpt"), max_chars=320)
        gap_type = _normalize_gap_type(raw_gap.get("gap_type"))
        deadline_score = _clamp(float(raw_gap.get("deadline_score", _deadline_score_for_concept(concept, syllabus))))  # type: ignore[arg-type]
        priority_score = _clamp(float(raw_gap.get("priority_score", (severity * 0.7) + (deadline_score * 0.3))))  # type: ignore[arg-type]

        new_gaps.append(
            KnowledgeGap(
                concept=concept,
                severity=severity,
                confidence=confidence,
                basis_question=basis_question,
                basis_answer_excerpt=basis_answer_excerpt,
                gap_type=gap_type,
                course_id=course_id,
                topic_id=gap_topic_id,
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
        socratic_prompt=socratic_prompt,
        gaps=[item.gap_id for item in new_gaps],
        course_id=course_id,
        topic_id=gap_topic_id,
        material_id=gap_material_id,
        source_warning=source_warning,
        source_context=source_context,
    )

    merged_gaps = [*existing_state.gaps, *new_gaps]
    readiness = calculate_readiness(merged_gaps)
    state = store.append_capture(event, new_gaps, readiness)

    session_summary = " ".join(socratic_prompt.split())[:220] or "Socratic turn"
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
        topic_id=gap_topic_id,
        agent_backend=agent_backend_used,
        source_resolution_mode=source_resolution_mode,
        source_resolution_score=round(source_resolution_score, 4),
        topic_candidate_count=topic_candidate_count,
        topic_runner_up_score=round(inferred_runner_up_score, 4),
        context_topic_id=context_topic.topic_id if context_topic is not None else None,
        grounding_topic_id=grounding_topic.topic_id if grounding_topic is not None else None,
        topic_grounded=topic_grounded,
        grounding_citation_count=len(grounding_bundle.citations),
        topic_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "topic:"),
        course_doc_grounding_count=_count_citations_with_prefix(grounding_bundle.citations, "course-doc:"),
        grounding_warning_count=len(grounding_bundle.warnings),
    )

    return CaptureResponse(
        capture_id=capture_id,
        thread_id=thread_id,
        turn_index=response_turn_index,
        socratic_prompt=socratic_prompt,
        gaps=new_gaps,
        readiness_axes=state.readiness_axes,
        topic_label=topic_name,
        course_id=course_id,
        source_warning=source_warning,
        source_context=source_context,
        source_material_url=grounding_bundle.primary_source_url,
        source_material_label=grounding_bundle.primary_source_label,
    )


@app.post("/api/v1/quizzes/prepare", response_model=QuizPrepareResponse)
async def prepare_quiz(request: QuizPrepareRequest) -> QuizPrepareResponse:
    state = _recompute_derived(store.read())
    if not state.question_bank:
        raise HTTPException(status_code=400, detail="Question bank is empty.")

    normalized_course_id = _normalize_course_id(request.course_id)
    normalized_topic = _normalize_topic(request.topic)
    selected_sources = set(request.sources) if request.sources else {"pyq", "tutorial", "sentinel"}
    selected_topic = _resolve_topic(request.topic_id)
    selected_topic_id = (
        selected_topic.topic_id if selected_topic is not None else _normalize_topic_id(request.topic_id) or None
    )

    syllabus = _load_syllabus()
    selected_questions, summary = _prepare_quiz_questions(
        state=state,
        course_id=normalized_course_id,
        topic_id=selected_topic_id,
        topic=normalized_topic,
        selected_sources=selected_sources,
        question_count=request.question_count,
        syllabus=syllabus,
    )
    if not selected_questions:
        raise HTTPException(
            status_code=400,
            detail="No questions matched the requested course/topic/source filters.",
        )

    session_id = str(uuid4())
    _log_bridge_event(
        event="quiz_prepared",
        endpoint_path="/api/v1/quizzes/prepare",
        course_id=normalized_course_id,
        topic_id=selected_topic_id,
        topic=normalized_topic,
        question_count=len(selected_questions),
        gap_matched_count=summary.gap_matched_count,
        wrong_repeat_count=summary.wrong_repeat_count,
        deadline_boosted_count=summary.deadline_boosted_count,
        coverage_count=summary.coverage_count,
    )

    return QuizPrepareResponse(
        session_id=session_id,
        topic=normalized_topic,
        questions=selected_questions,
        selection_summary=summary,
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
    selected_topic = _resolve_topic(request.topic_id)
    selected_topic_id = selected_topic.topic_id if selected_topic is not None else _normalize_topic_id(request.topic_id) or None

    question_by_id = {item.question_id: item for item in state.question_bank}
    question_results: list[QuizQuestionResult] = []

    for answer in request.answers:
        item = question_by_id.get(answer.question_id)
        if item is None:
            raise HTTPException(status_code=400, detail=f"Unknown question_id: {answer.question_id}")
        if not _question_visible_for_course(item, normalized_course_id):
            raise HTTPException(status_code=400, detail=f"Question course mismatch for {answer.question_id}.")
        if not _question_visible_for_topic(item, selected_topic_id):
            raise HTTPException(status_code=400, detail=f"Question topic mismatch for {answer.question_id}.")
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
        topic_id=selected_topic_id,
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
            topic_id=selected_topic_id,
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
        topic_id=selected_topic_id,
        session_id=request.session_id,
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
    topic_id: str = Form(...),
    document_name: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
) -> CourseDocument:
    normalized = _normalize_course_id(course_id)
    normalized_topic_id = _normalize_topic_id(topic_id)
    if not normalized_topic_id:
        _log_bridge_event(
            event="document_upload_validation_failed",
            endpoint_path="/api/v1/courses/{course_id}/documents/upload",
            course_id=normalized,
            reason="topic_id must not be empty.",
        )
        raise HTTPException(status_code=400, detail="topic_id must not be empty.")

    topic = topic_store.get_topic(normalized_topic_id)
    if topic is None:
        _log_bridge_event(
            event="document_upload_validation_failed",
            endpoint_path="/api/v1/courses/{course_id}/documents/upload",
            course_id=normalized,
            topic_id=normalized_topic_id,
            reason=f"topic_id '{normalized_topic_id}' was not found.",
        )
        raise HTTPException(status_code=404, detail=f"Topic not found: {normalized_topic_id}")

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
        topic_id=topic.topic_id,
        name=display_name,
        size_bytes=len(raw_bytes),
        type=doc_type,
        file_url=file_url,
        is_anchor=False,
    )

    state = store.read()
    state.documents.append(document)

    topics_added = 0
    questions_added = 0
    try:
        topics_added, questions_added, seed_warnings = _seed_document_topics_and_questions(
            state,
            document,
            target,
        )
        if topics_added > 0 or questions_added > 0:
            _log_bridge_event(
                event="topic_seed_generated",
                endpoint_path="/api/v1/courses/{course_id}/documents/upload",
                course_id=normalized,
                topic_id=document.topic_id,
                doc_id=document.doc_id,
                topics_added=topics_added,
                questions_added=questions_added,
            )
        for warning in seed_warnings:
            _log_bridge_event(
                event="topic_seed_skipped",
                endpoint_path="/api/v1/courses/{course_id}/documents/upload",
                course_id=normalized,
                topic_id=document.topic_id,
                doc_id=document.doc_id,
                reason=warning,
            )
    except Exception as exc:  # noqa: BLE001
        _log_bridge_event(
            event="topic_seed_skipped",
            endpoint_path="/api/v1/courses/{course_id}/documents/upload",
            course_id=normalized,
            topic_id=document.topic_id,
            doc_id=document.doc_id,
            reason=f"llm_error:{type(exc).__name__}",
        )

    state = _save_state(state)
    await _publish_state(state)
    return document


@app.patch("/api/v1/courses/{course_id}/documents/{doc_id}", response_model=CourseDocument)
async def retag_course_document(course_id: str, doc_id: str, request: DocumentRetagRequest) -> CourseDocument:
    normalized = _normalize_course_id(course_id)
    normalized_topic_id = _normalize_topic_id(request.topic_id)
    if not normalized_topic_id:
        raise HTTPException(status_code=400, detail="topic_id must not be empty.")

    topic = topic_store.get_topic(normalized_topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Topic not found: {normalized_topic_id}")

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

    previous_topic_id = target.topic_id
    if _normalize_topic_id(previous_topic_id) == topic.topic_id:
        return target

    target.topic_id = topic.topic_id
    removed_topics, removed_questions = _remove_document_seed_artifacts(state, doc_id=doc_id)
    doc_path = _course_document_path_from_url(target.file_url)
    topics_added = 0
    questions_added = 0
    if doc_path is not None and doc_path.exists():
        try:
            topics_added, questions_added, seed_warnings = _seed_document_topics_and_questions(
                state,
                target,
                doc_path,
            )
            if topics_added > 0 or questions_added > 0:
                _log_bridge_event(
                    event="topic_seed_generated",
                    endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
                    course_id=normalized,
                    topic_id=target.topic_id,
                    doc_id=target.doc_id,
                    topics_added=topics_added,
                    questions_added=questions_added,
                )
            for warning in seed_warnings:
                _log_bridge_event(
                    event="topic_seed_skipped",
                    endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
                    course_id=normalized,
                    topic_id=target.topic_id,
                    doc_id=target.doc_id,
                    reason=warning,
                )
        except Exception as exc:  # noqa: BLE001
            _log_bridge_event(
                event="topic_seed_skipped",
                endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
                course_id=normalized,
                topic_id=target.topic_id,
                doc_id=target.doc_id,
                reason=f"llm_error:{type(exc).__name__}",
            )
    else:
        _log_bridge_event(
            event="topic_seed_skipped",
            endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
            course_id=normalized,
            topic_id=target.topic_id,
            doc_id=target.doc_id,
            reason="file_missing_for_reseed",
        )

    state = _save_state(state)
    await _publish_state(state)
    _log_bridge_event(
        event="document_retagged",
        endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
        course_id=normalized,
        doc_id=doc_id,
        old_topic_id=previous_topic_id,
        new_topic_id=target.topic_id,
        removed_topics=removed_topics,
        removed_questions=removed_questions,
        topics_added=topics_added,
        questions_added=questions_added,
    )
    return target


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
    removed_topics, removed_questions = _remove_document_seed_artifacts(state, doc_id=doc_id)

    if target.file_url.startswith(f"http://{settings.bridge_host}:{settings.bridge_port}/course-documents/"):
        relative = target.file_url.split("/course-documents/", 1)[1]
        candidate = settings.documents_dir / relative
        if candidate.exists():
            candidate.unlink(missing_ok=True)

    state = _save_state(state)
    await _publish_state(state)
    _log_bridge_event(
        event="topic_seed_cleanup",
        endpoint_path="/api/v1/courses/{course_id}/documents/{doc_id}",
        course_id=normalized,
        topic_id=target.topic_id,
        doc_id=doc_id,
        removed_topics=removed_topics,
        removed_questions=removed_questions,
    )
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.bridge_host, port=8000, reload=True)

