#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgS4m5n4AAAAASUVORK5CYII="
)


def _load_capture_image_base64(repo_root: Path) -> str:
    sample = repo_root / "data" / "captures" / "smoke-test-capture.png"
    if sample.exists():
        return base64.b64encode(sample.read_bytes()).decode("utf-8")
    return ONE_PIXEL_PNG_BASE64


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_json(url: str, method: str = "GET", payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_prompts(path: Path) -> list[str]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON prompts file must be an array.")
        prompts: list[str] = []
        for item in payload:
            text = " ".join(str(item).split()).strip()
            if text:
                prompts.append(text)
        return prompts

    prompts: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        prompts.append(trimmed)
    return prompts


def _build_capture_payload(
    *,
    prompt_text: str,
    thread_id: str,
    turn_index: int,
    previous_prompt: str | None,
    course_id: str | None,
    topic_id: str | None,
    image_base64: str,
) -> dict:
    payload: dict[str, object] = {
        "platform": "windows",
        "app_name": "Scoratic Prompt Flow",
        "window_title": f"Scoratic Prompt Turn {turn_index}",
        "monitor": {"left": 0, "top": 0, "width": 1920, "height": 1080, "scale": 1.0},
        "region": {"x": 140, "y": 90, "width": 760, "height": 420},
        "image_base64": image_base64,
        "thread_id": thread_id,
        "turn_index": max(0, int(turn_index)),
        "user_input_text": prompt_text,
    }
    if previous_prompt:
        payload["previous_prompt"] = previous_prompt
    if course_id:
        payload["course_id"] = course_id
    if topic_id:
        payload["topic_id"] = topic_id
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic scoratic prompt flow and log outputs.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--prompts-file",
        default="docs/mock-content/scoratic-prompts.txt",
        help="Path to .txt or .json prompt list",
    )
    parser.add_argument("--thread-id", default=f"scoratic-flow-{int(time.time())}")
    parser.add_argument("--course-id", default="")
    parser.add_argument("--topic-id", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--request-timeout", type=float, default=60.0)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    prompts_path = (repo_root / args.prompts_file).resolve()
    if not prompts_path.exists():
        raise FileNotFoundError(f"Prompts file not found: {prompts_path}")

    prompts = _load_prompts(prompts_path)
    if not prompts:
        raise ValueError("Prompts file produced zero prompts.")

    bridge_url = args.bridge_url.rstrip("/")
    capture_image_base64 = _load_capture_image_base64(repo_root)
    previous_prompt: str | None = None
    turn_index = 0
    results: list[dict[str, object]] = []

    errors: list[dict[str, object]] = []

    for index, prompt_text in enumerate(prompts, start=1):
        payload = _build_capture_payload(
            prompt_text=prompt_text,
            thread_id=args.thread_id,
            turn_index=turn_index,
            previous_prompt=previous_prompt,
            course_id=args.course_id.strip() or None,
            topic_id=args.topic_id.strip() or None,
            image_base64=capture_image_base64,
        )
        started = time.perf_counter()
        try:
            response = _request_json(
                f"{bridge_url}/api/v1/captures",
                method="POST",
                payload=payload,
                timeout=max(5.0, float(args.request_timeout)),
            )
        except (TimeoutError, URLError, OSError, ValueError) as exc:
            duration_ms = int((time.perf_counter() - started) * 1000.0)
            errors.append(
                {
                    "step": index,
                    "timestamp_utc": _utc_now_iso(),
                    "latency_ms": duration_ms,
                    "input_prompt": prompt_text,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            break
        duration_ms = int((time.perf_counter() - started) * 1000.0)

        output_prompt = str(response.get("socratic_prompt", "")).strip()
        previous_prompt = output_prompt or previous_prompt
        turn_index = int(response.get("turn_index", turn_index + 1))

        results.append(
            {
                "step": index,
                "timestamp_utc": _utc_now_iso(),
                "latency_ms": duration_ms,
                "input_prompt": prompt_text,
                "capture_id": response.get("capture_id"),
                "thread_id": response.get("thread_id"),
                "turn_index": response.get("turn_index"),
                "socratic_prompt": output_prompt,
                "reply_mode": response.get("reply_mode"),
                "session_ended": bool(response.get("session_ended", False)),
                "agent_backend": response.get("agent_backend"),
                "fallback_reason": response.get("fallback_reason"),
            }
        )
        if bool(response.get("session_ended", False)):
            break

    artifact_dir = repo_root / "artifacts" / "scoratic-prompt-flow"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.out).resolve() if args.out else artifact_dir / f"summary-{int(time.time())}.json"

    summary = {
        "ok": len(results) > 0 and len(errors) == 0,
        "bridge_url": bridge_url,
        "thread_id": args.thread_id,
        "prompt_count": len(prompts),
        "steps_completed": len(results),
        "results": results,
        "errors": errors,
    }
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(output_path), "summary": summary}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
