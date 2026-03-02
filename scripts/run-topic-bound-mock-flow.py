#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgS4m5n4AAAAASUVORK5CYII="
)


def _json_request(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    body: bytes | None = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _upload_material(
    *,
    base_url: str,
    topic_id: str,
    material_name: str,
    filename: str,
    content: bytes,
    material_type: str | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/topics/{topic_id}/materials"
    boundary = f"----sentinel-boundary-{int(time.time() * 1000)}"
    fields: list[tuple[str, str]] = [("material_name", material_name)]
    if material_type:
        fields.append(("material_type", material_type))

    body = bytearray()
    for key, value in fields:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_capture_payload(thread_id: str, turn_index: int, topic_id: str) -> dict[str, Any]:
    image_bytes = base64.b64decode(ONE_PIXEL_PNG_BASE64)
    return {
        "platform": "windows",
        "app_name": "Topic Match Test",
        "window_title": "Topic Match Test Window",
        "monitor": {"left": 0, "top": 0, "width": 1920, "height": 1080, "scale": 1.0},
        "region": {"x": 100, "y": 120, "width": 320, "height": 180},
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        "thread_id": thread_id,
        "turn_index": turn_index,
        "topic_id": topic_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run topic-bound screenshot flow (matched + unmatched)")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8000")
    parser.add_argument("--thread-id", default="topic-bound-mock-thread")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    bridge_url = args.bridge_url.rstrip("/")

    reference_fixture = (repo_root / "docs/mock-content/laplace_lecture_slide.md").read_text(encoding="utf-8")
    fallback_fixture = (
        "No OpenAI API key configured. Captured study content awaiting cloud interpretation. "
        "No text detected. Could not parse visual content from OpenAI Vision. "
        "capture unparsed vision-error"
    )

    fallback_topic_id = "topic-fallback-grounding"
    reference_topic_id = "topic-reference-grounding"

    _json_request(
        bridge_url,
        "POST",
        "/api/v1/topics",
        {"topic_id": fallback_topic_id, "topic_name": "Fallback Grounding"},
    )
    _json_request(
        bridge_url,
        "POST",
        "/api/v1/topics",
        {"topic_id": reference_topic_id, "topic_name": "Reference Grounding"},
    )

    fallback_material = _upload_material(
        base_url=bridge_url,
        topic_id=fallback_topic_id,
        material_name="OpenAI fallback grounding",
        filename="fallback-grounding.md",
        content=fallback_fixture.encode("utf-8"),
        material_type="text",
    )
    reference_material = _upload_material(
        base_url=bridge_url,
        topic_id=reference_topic_id,
        material_name="Reference lecture slide",
        filename="reference_lecture_slide.md",
        content=reference_fixture.encode("utf-8"),
        material_type="lecture",
    )

    _json_request(
        bridge_url,
        "POST",
        "/api/v1/topics/active",
        {"topic_id": fallback_topic_id},
    )

    matched_response = _json_request(
        bridge_url,
        "POST",
        "/api/v1/captures",
        _build_capture_payload(args.thread_id, 0, fallback_topic_id),
    )

    _json_request(
        bridge_url,
        "POST",
        "/api/v1/topics/active",
        {"topic_id": reference_topic_id},
    )

    unmatched_response = _json_request(
        bridge_url,
        "POST",
        "/api/v1/captures",
        _build_capture_payload(args.thread_id, int(matched_response.get("turn_index", 0)), reference_topic_id),
    )

    summary = {
        "ok": bool(matched_response.get("source_context", {}).get("matched") is True)
        and bool(unmatched_response.get("source_warning")),
        "bridge_url": bridge_url,
        "thread_id": args.thread_id,
        "topics": {
            "fallback_topic_id": fallback_topic_id,
            "reference_topic_id": reference_topic_id,
        },
        "materials": {
            "fallback_material_id": fallback_material.get("material_id"),
            "reference_material_id": reference_material.get("material_id"),
        },
        "matched_path": {
            "capture_id": matched_response.get("capture_id"),
            "source_warning": matched_response.get("source_warning"),
            "source_context": matched_response.get("source_context"),
        },
        "unmatched_path": {
            "capture_id": unmatched_response.get("capture_id"),
            "source_warning": unmatched_response.get("source_warning"),
            "source_context": unmatched_response.get("source_context"),
        },
        "note": (
            "This flow is deterministic when bridge runs without OPENAI_API_KEY, because vision fallback text is stable. "
            "With live OpenAI vision, match scores can vary by image parsing."
        ),
    }

    artifact_dir = repo_root / "artifacts" / "topic-bound-flow"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_file = artifact_dir / f"summary-{int(time.time())}.json"
    artifact_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({"summary": summary, "artifact": str(artifact_file)}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
