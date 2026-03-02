#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


def _request_json(url: str, method: str = "GET", payload: dict | None = None, timeout: float = 12.0) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_fixture(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    return path.read_text(encoding="utf-8")


def _build_capture_payload(
    *,
    fixture_text: str,
    app_name: str,
    window_title: str,
    thread_id: str,
    turn_index: int,
    previous_prompt: str | None = None,
    user_input_text: str | None = None,
) -> dict:
    image_bytes = fixture_text.encode("utf-8")
    payload = {
        "platform": "windows",
        "app_name": app_name,
        "window_title": window_title,
        "monitor": {"left": 0, "top": 0, "width": 1920, "height": 1080, "scale": 1.0},
        "region": {"x": 120, "y": 80, "width": 640, "height": 420},
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        "thread_id": thread_id,
        "turn_index": turn_index,
    }
    if previous_prompt:
        payload["previous_prompt"] = previous_prompt
    if user_input_text:
        payload["user_input_text"] = user_input_text
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic mock Laplace lecture/tutorial capture flow")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8000")
    parser.add_argument("--thread-id", default="mock-laplace-thread")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    bridge_url = args.bridge_url.rstrip("/")

    lecture_text = _read_fixture(repo_root, "docs/mock-content/laplace_lecture_slide.md")
    tutorial_text = _read_fixture(repo_root, "docs/mock-content/laplace_tutorial.md")

    state_before = _request_json(f"{bridge_url}/api/v1/state")
    captures_before = len(state_before.get("captures", []))

    capture_1 = _request_json(
        f"{bridge_url}/api/v1/captures",
        method="POST",
        payload=_build_capture_payload(
            fixture_text=lecture_text,
            app_name="Mock Lecture Slide",
            window_title="Laplace Transform Lecture",
            thread_id=args.thread_id,
            turn_index=0,
        ),
    )

    capture_2 = _request_json(
        f"{bridge_url}/api/v1/captures",
        method="POST",
        payload=_build_capture_payload(
            fixture_text=tutorial_text,
            app_name="Mock Tutorial",
            window_title="Laplace Transform Tutorial",
            thread_id=args.thread_id,
            turn_index=int(capture_1.get("turn_index", 0)),
            previous_prompt=capture_1.get("socratic_prompt", ""),
            user_input_text="I ignored the derivative initial-condition terms and jumped to inverse Laplace.",
        ),
    )

    state_after = _request_json(f"{bridge_url}/api/v1/state")
    captures_after = len(state_after.get("captures", []))

    summary = {
        "ok": captures_after >= captures_before + 2,
        "captures_before": captures_before,
        "captures_after": captures_after,
        "thread_id": args.thread_id,
        "capture_1": {
            "capture_id": capture_1.get("capture_id"),
            "turn_index": capture_1.get("turn_index"),
            "topic_label": capture_1.get("topic_label"),
            "gap_count": len(capture_1.get("gaps", [])),
            "socratic_prompt": capture_1.get("socratic_prompt"),
        },
        "capture_2": {
            "capture_id": capture_2.get("capture_id"),
            "turn_index": capture_2.get("turn_index"),
            "topic_label": capture_2.get("topic_label"),
            "gap_count": len(capture_2.get("gaps", [])),
            "socratic_prompt": capture_2.get("socratic_prompt"),
        },
        "latest_state_updated_at": state_after.get("updated_at"),
    }

    artifact_dir = repo_root / "artifacts" / "mock-laplace"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_file = artifact_dir / f"summary-{int(time.time())}.json"
    artifact_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({"summary": summary, "artifact": str(artifact_file)}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
