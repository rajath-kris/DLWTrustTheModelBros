#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SourceCursor:
    name: str
    path: Path
    offset: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse Sentinel overlay journey logs.")
    parser.add_argument("--sentinel-log", required=True)
    parser.add_argument("--bridge-log", required=True)
    parser.add_argument("--timeline-out")
    parser.add_argument("--report-out")
    parser.add_argument("--scenario", default="")
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=0.25)
    return parser.parse_args()


def _parse_log_line(line: str, source: str) -> dict[str, Any] | None:
    text = line.strip().lstrip("\ufeff")
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {
            "source": source,
            "component": f"{source}_raw",
            "event": "raw_line",
            "timestamp_utc": utc_now_iso(),
            "message": text,
        }
    if not isinstance(payload, dict):
        return None
    payload = dict(payload)
    payload.setdefault("timestamp_utc", utc_now_iso())
    payload.setdefault("component", f"{source}_event")
    payload.setdefault("event", "unknown")
    payload["source"] = source
    return payload


def read_new_events(cursor: SourceCursor) -> list[dict[str, Any]]:
    if not cursor.path.exists():
        return []
    events: list[dict[str, Any]] = []
    with cursor.path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(cursor.offset)
        for line in handle:
            event = _parse_log_line(line, cursor.name)
            if event is not None:
                events.append(event)
        cursor.offset = handle.tell()
    return events


def parse_all_logs(sentinel_log: Path, bridge_log: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source_name, source_path in (("sentinel", sentinel_log), ("mock_bridge", bridge_log)):
        if not source_path.exists():
            continue
        with source_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                event = _parse_log_line(line, source_name)
                if event is not None:
                    events.append(event)
    events.sort(key=lambda item: str(item.get("timestamp_utc", "")))
    return events


def print_event_line(event: dict[str, Any]) -> None:
    stamp = str(event.get("timestamp_utc", ""))
    short_time = stamp[11:19] if len(stamp) >= 19 else stamp
    source = str(event.get("source", ""))
    component = str(event.get("component", ""))
    name = str(event.get("event", ""))
    request_id = event.get("request_id")
    suffix = f" req={request_id}" if request_id is not None else ""
    print(f"[{short_time}] [{source}/{component}] {name}{suffix}", flush=True)


def write_timeline(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events, indent=2), encoding="utf-8")


def _event_time(event: dict[str, Any]) -> datetime | None:
    raw = str(event.get("timestamp_utc", "")).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _duration_ms(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    start = _event_time(a)
    end = _event_time(b)
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds() * 1000.0)


def _find_by_event(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [item for item in events if str(item.get("event")) == name]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_summary(events: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    capture_events = _find_by_event(events, "capture_triggered")
    analyzing_events = _find_by_event(events, "overlay_state_analyzing")
    prompt_events = _find_by_event(events, "overlay_state_prompt")
    turn_prompt_events = _find_by_event(events, "turn_prompt_rendered")
    error_events = _find_by_event(events, "overlay_state_error")
    retry_clicks = _find_by_event(events, "overlay_retry_clicked")
    retry_starts = [item for item in _find_by_event(events, "request_started") if item.get("source_mode") == "retry"]
    successes = _find_by_event(events, "request_success")
    success_ids = {item.get("request_id") for item in successes}
    retry_successes = [item for item in retry_starts if item.get("request_id") in success_ids]
    retry_input_starts = [item for item in retry_starts if _safe_int(item.get("user_input_char_count")) > 0]
    retry_input_successes = [item for item in retry_input_starts if item.get("request_id") in success_ids]
    esc_events = _find_by_event(events, "escape_triggered")
    selector_completed = _find_by_event(events, "selector_completed")
    selector_cancelled = _find_by_event(events, "selector_cancelled")
    user_input_events = _find_by_event(events, "user_input_submitted")
    turn_analysis_started = _find_by_event(events, "turn_analysis_started")
    turn_analysis_completed = _find_by_event(events, "turn_analysis_completed")

    trigger_to_analyzing_ms: list[float] = []
    for trigger in capture_events:
        after = [item for item in analyzing_events if _event_time(item) and _event_time(trigger) and _event_time(item) >= _event_time(trigger)]
        if not after:
            continue
        duration = _duration_ms(trigger, after[0])
        if duration is not None:
            trigger_to_analyzing_ms.append(duration)

    analyzing_to_prompt_ms: list[float] = []
    for start in analyzing_events:
        req_id = start.get("request_id")
        matching = [item for item in prompt_events if item.get("request_id") == req_id]
        if not matching:
            continue
        duration = _duration_ms(start, matching[0])
        if duration is not None:
            analyzing_to_prompt_ms.append(duration)

    submit_to_analyzing_ms: list[float] = []
    for submit in user_input_events:
        submit_time = _event_time(submit)
        if submit_time is None:
            continue
        after = [
            item
            for item in analyzing_events
            if _event_time(item) is not None and _event_time(item) >= submit_time
        ]
        if not after:
            continue
        duration = _duration_ms(submit, after[0])
        if duration is not None:
            submit_to_analyzing_ms.append(duration)

    analyzing_to_next_prompt_ms: list[float] = []
    for start in turn_analysis_started:
        start_time = _event_time(start)
        if start_time is None:
            continue
        thread_id = str(start.get("thread_id", "")).strip()
        next_turn = _safe_int(start.get("turn_index")) + 1
        matching = [
            item
            for item in turn_prompt_events
            if _event_time(item) is not None
            and _event_time(item) >= start_time
            and (not thread_id or str(item.get("thread_id", "")).strip() == thread_id)
            and _safe_int(item.get("turn_index")) == next_turn
        ]
        if not matching:
            matching = [
                item
                for item in prompt_events
                if _event_time(item) is not None and _event_time(item) >= start_time
            ]
        if not matching:
            continue
        duration = _duration_ms(start, matching[0])
        if duration is not None:
            analyzing_to_next_prompt_ms.append(duration)

    scenario_value = scenario.strip() or str(events[-1].get("scenario", "")) if events else scenario

    return {
        "scenario": scenario_value,
        "event_count": len(events),
        "captures": len(capture_events),
        "selector_completed": len(selector_completed),
        "selector_cancelled": len(selector_cancelled),
        "prompts_shown": len(prompt_events),
        "errors_shown": len(error_events),
        "retry_clicks": len(retry_clicks),
        "retry_attempts": len(retry_starts),
        "retry_successes": len(retry_successes),
        "retry_input_attempts": len(retry_input_starts),
        "retry_input_successes": len(retry_input_successes),
        "escape_events": len(esc_events),
        "input_submissions": len(user_input_events),
        "turn_analysis_started": len(turn_analysis_started),
        "turn_analysis_completed": len(turn_analysis_completed),
        "trigger_to_analyzing_ms": trigger_to_analyzing_ms,
        "analyzing_to_prompt_ms": analyzing_to_prompt_ms,
        "submit_to_analyzing_ms": submit_to_analyzing_ms,
        "analyzing_to_next_prompt_ms": analyzing_to_next_prompt_ms,
    }


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def write_report(report_path: Path, summary: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    trigger_avg = _avg(summary["trigger_to_analyzing_ms"])
    analyze_avg = _avg(summary["analyzing_to_prompt_ms"])
    submit_avg = _avg(summary["submit_to_analyzing_ms"])
    turn_prompt_avg = _avg(summary["analyzing_to_next_prompt_ms"])
    retry_attempts = int(summary["retry_attempts"])
    retry_successes = int(summary["retry_successes"])
    retry_rate = (retry_successes / retry_attempts) if retry_attempts else None
    retry_input_attempts = int(summary["retry_input_attempts"])
    retry_input_successes = int(summary["retry_input_successes"])
    retry_input_rate = (retry_input_successes / retry_input_attempts) if retry_input_attempts else None

    checks = [
        ("Latency visibility", int(summary["captures"]) > 0 and len(summary["trigger_to_analyzing_ms"]) > 0),
        ("Prompt or error displayed", int(summary["prompts_shown"]) + int(summary["errors_shown"]) > 0),
        ("Input capture evidence", int(summary["input_submissions"]) > 0),
        ("Dismissibility evidence (Esc)", int(summary["escape_events"]) > 0),
        ("Retry behavior observed", retry_attempts > 0),
    ]

    lines = [
        "# Overlay Journey Session Report",
        "",
        f"- Generated: {utc_now_iso()}",
        f"- Scenario: {summary['scenario'] or 'unspecified'}",
        f"- Total events: {summary['event_count']}",
        "",
        "## Metrics",
        "",
        f"- Captures triggered: {summary['captures']}",
        f"- Selector completed: {summary['selector_completed']}",
        f"- Selector cancelled: {summary['selector_cancelled']}",
        f"- Prompts shown: {summary['prompts_shown']}",
        f"- Errors shown: {summary['errors_shown']}",
        f"- Retry clicks: {summary['retry_clicks']}",
        f"- Retry attempts: {retry_attempts}",
        f"- Retry successes: {retry_successes}",
        f"- Retry attempts after input: {retry_input_attempts}",
        f"- Retry successes after input: {retry_input_successes}",
        f"- Escape dismiss events: {summary['escape_events']}",
        f"- Input submissions: {summary['input_submissions']}",
        f"- Turn analyses started: {summary['turn_analysis_started']}",
        f"- Turn analyses completed: {summary['turn_analysis_completed']}",
        f"- Avg trigger->analyzing: {trigger_avg:.1f} ms" if trigger_avg is not None else "- Avg trigger->analyzing: n/a",
        f"- Avg analyzing->prompt: {analyze_avg:.1f} ms" if analyze_avg is not None else "- Avg analyzing->prompt: n/a",
        f"- Avg submit->analyzing: {submit_avg:.1f} ms" if submit_avg is not None else "- Avg submit->analyzing: n/a",
        (
            f"- Avg turn analyzing->next prompt: {turn_prompt_avg:.1f} ms"
            if turn_prompt_avg is not None
            else "- Avg turn analyzing->next prompt: n/a"
        ),
        (
            f"- Retry success rate: {retry_rate * 100:.1f}%"
            if retry_rate is not None
            else "- Retry success rate: n/a"
        ),
        (
            f"- Retry success after input: {retry_input_rate * 100:.1f}%"
            if retry_input_rate is not None
            else "- Retry success after input: n/a"
        ),
        "",
        "## Quality Gates",
        "",
    ]
    for name, passed in checks:
        lines.append(f"- [{'PASS' if passed else 'FAIL'}] {name}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def follow_logs(args: argparse.Namespace) -> int:
    sentinel_cursor = SourceCursor(name="sentinel", path=Path(args.sentinel_log))
    bridge_cursor = SourceCursor(name="mock_bridge", path=Path(args.bridge_log))
    all_events: list[dict[str, Any]] = []

    print("Following journey logs. Stop this process to end live timeline.", flush=True)
    try:
        while True:
            chunk = read_new_events(sentinel_cursor) + read_new_events(bridge_cursor)
            if chunk:
                chunk.sort(key=lambda item: str(item.get("timestamp_utc", "")))
                for event in chunk:
                    all_events.append(event)
                    print_event_line(event)
                if args.timeline_out:
                    write_timeline(Path(args.timeline_out), all_events)
            time.sleep(max(0.05, float(args.poll_interval)))
    except KeyboardInterrupt:
        pass

    if args.timeline_out:
        write_timeline(Path(args.timeline_out), all_events)
    return 0


def build_artifacts(args: argparse.Namespace) -> int:
    sentinel_log = Path(args.sentinel_log)
    bridge_log = Path(args.bridge_log)
    events = parse_all_logs(sentinel_log, bridge_log)

    timeline_path = Path(args.timeline_out) if args.timeline_out else None
    report_path = Path(args.report_out) if args.report_out else None

    if timeline_path is not None:
        write_timeline(timeline_path, events)

    summary = build_summary(events, args.scenario)
    if report_path is not None:
        write_report(report_path, summary)

    print(json.dumps({"ok": True, "summary": summary}, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    if args.follow:
        return follow_logs(args)
    return build_artifacts(args)


if __name__ == "__main__":
    raise SystemExit(main())
