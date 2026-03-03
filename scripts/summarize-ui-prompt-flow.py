#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _iter_json_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw.startswith("{"):
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _pick_thread_id(events: list[dict[str, Any]], preferred: str | None) -> str | None:
    if preferred:
        cleaned = preferred.strip()
        if cleaned:
            return cleaned
    for event in reversed(events):
        thread_id = str(event.get("thread_id", "")).strip()
        if thread_id:
            return thread_id
    return None


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Sentinel UI prompt flow from sentinel_ui.log")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--log-file", default="artifacts/sentinel_ui.log")
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    log_path = (repo_root / args.log_file).resolve()
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    events = _iter_json_events(log_path)
    target_thread = _pick_thread_id(events, args.thread_id)
    if not target_thread:
        summary = {
            "ok": False,
            "log_file": str(log_path),
            "thread_id": None,
            "steps_completed": 0,
            "results": [],
            "errors": ["No thread_id found in log."],
        }
        artifact_dir = repo_root / "artifacts" / "scoratic-prompt-flow"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        output_path = Path(args.out).resolve() if args.out else artifact_dir / f"ui-summary-{int(time.time())}.json"
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"artifact": str(output_path), "summary": summary}, indent=2))
        return 1

    turn_rows: dict[int, dict[str, Any]] = {}

    for event in events:
        if str(event.get("thread_id", "")).strip() != target_thread:
            continue
        turn_index = max(0, _coerce_int(event.get("turn_index"), 0))
        row = turn_rows.setdefault(
            turn_index,
            {
                "turn_index": turn_index,
                "first_timestamp_utc": str(event.get("timestamp_utc", "")).strip() or None,
                "input_prompt_preview": None,
                "input_chars": None,
                "socratic_prompt_preview": None,
                "socratic_prompt_length": None,
                "reply_mode": None,
                "session_ended": None,
                "agent_backend": None,
                "fallback_reason": None,
            },
        )
        if row["first_timestamp_utc"] is None:
            row["first_timestamp_utc"] = str(event.get("timestamp_utc", "")).strip() or None

        event_name = str(event.get("event", "")).strip()
        if event_name == "user_input_submitted":
            row["input_prompt_preview"] = str(event.get("preview", "")).strip() or None
            row["input_chars"] = _coerce_int(event.get("char_count"), 0)
        elif event_name == "bridge_prompt_received":
            row["socratic_prompt_preview"] = str(event.get("prompt_preview", "")).strip() or None
            row["socratic_prompt_length"] = _coerce_int(event.get("prompt_length"), 0)
            row["reply_mode"] = str(event.get("reply_mode", "")).strip() or None
            row["session_ended"] = bool(event.get("session_ended", False))
            row["agent_backend"] = str(event.get("agent_backend", "")).strip() or None
            row["fallback_reason"] = str(event.get("fallback_reason", "")).strip() or None
        elif event_name == "request_success":
            row["reply_mode"] = str(event.get("reply_mode", "")).strip() or row["reply_mode"]
            row["session_ended"] = bool(event.get("session_ended", False))
            row["agent_backend"] = str(event.get("agent_backend", "")).strip() or row["agent_backend"]
            row["fallback_reason"] = str(event.get("fallback_reason", "")).strip() or row["fallback_reason"]

    sorted_rows = [turn_rows[idx] for idx in sorted(turn_rows)]
    steps = [row for row in sorted_rows if row.get("socratic_prompt_preview")]

    summary = {
        "ok": len(steps) > 0,
        "log_file": str(log_path),
        "thread_id": target_thread,
        "steps_completed": len(steps),
        "results": steps,
        "errors": [],
    }

    artifact_dir = repo_root / "artifacts" / "scoratic-prompt-flow"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.out).resolve() if args.out else artifact_dir / f"ui-summary-{int(time.time())}.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(output_path), "summary": summary}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
