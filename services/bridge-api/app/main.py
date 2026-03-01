from __future__ import annotations

import base64
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


def _sanitize_thread_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return (cleaned[:80] or str(uuid4())).strip("-") or str(uuid4())


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
        raise HTTPException(status_code=400, detail=f"Invalid image_base64: {exc}") from exc

    capture_id = _sanitize_capture_id(payload.capture_id or str(uuid4()))
    thread_id = _sanitize_thread_id((payload.thread_id or "").strip() or capture_id)
    response_turn_index = max(0, int(payload.turn_index))
    if (payload.user_input_text or "").strip():
        response_turn_index += 1
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
    await broker.publish(envelope.model_dump(mode="json"))

    return CaptureResponse(
        capture_id=capture_id,
        thread_id=thread_id,
        turn_index=response_turn_index,
        socratic_prompt=socratic.socratic_prompt,
        gaps=new_gaps,
        readiness_axes=readiness,
    )


@app.post("/api/v1/gaps/{gap_id}/status")
async def update_gap_status(gap_id: str, request: GapStatusUpdate) -> dict:
    state = store.update_gap_status(gap_id, request.status)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Gap not found: {gap_id}")

    state.readiness_axes = calculate_readiness(state.gaps)
    store.write(state)

    envelope = EventEnvelope(
        type="gap_updated",
        payload={"gap_id": gap_id, "status": request.status, "state": state.model_dump(mode="json")},
    )
    await broker.publish(envelope.model_dump(mode="json"))

    return {"ok": True, "gap_id": gap_id, "status": request.status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.bridge_host, port=8000, reload=True)
