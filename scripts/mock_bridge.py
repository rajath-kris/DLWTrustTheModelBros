#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4


VALID_SCENARIOS = {
    "success_fast",
    "success_slow",
    "http_500",
    "timeout",
    "malformed",
    "flaky",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class MockState:
    scenario: str
    timeout_seconds: float
    request_count: int = 0
    flaky_should_fail: bool = True
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "scenario": self.scenario,
                "request_count": self.request_count,
                "flaky_should_fail": self.flaky_should_fail,
                "timeout_seconds": self.timeout_seconds,
            }

    def set_scenario(self, scenario: str) -> None:
        with self.lock:
            self.scenario = scenario
            self.flaky_should_fail = True

    def bump_request(self) -> tuple[int, str, bool]:
        with self.lock:
            self.request_count += 1
            request_number = self.request_count
            scenario = self.scenario
            fail_now = False
            if scenario == "flaky":
                fail_now = self.flaky_should_fail
                self.flaky_should_fail = not self.flaky_should_fail
            return request_number, scenario, fail_now


def emit(event: str, **fields: Any) -> None:
    payload = {
        "component": "mock_bridge",
        "event": event,
        "timestamp_utc": utc_now_iso(),
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=True), flush=True)


class MockBridgeHandler(BaseHTTPRequestHandler):
    server_version = "SentinelMockBridge/1.0"
    protocol_version = "HTTP/1.1"

    def _json_response(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    @property
    def state(self) -> MockState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: Any) -> None:
        # Keep stdout clean for structured event output.
        return

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json_response(200, {"status": "ok", "timestamp_utc": utc_now_iso()})
            return

        if self.path == "/__scenario":
            self._json_response(200, self.state.snapshot())
            return

        self._json_response(404, {"detail": "Not found"})

    def do_POST(self) -> None:
        if self.path == "/__scenario":
            payload = self._read_json()
            scenario = str(payload.get("scenario", "")).strip()
            if scenario not in VALID_SCENARIOS:
                self._json_response(
                    400,
                    {
                        "detail": "Invalid scenario",
                        "valid_scenarios": sorted(VALID_SCENARIOS),
                    },
                )
                return
            self.state.set_scenario(scenario)
            emit("scenario_updated", scenario=scenario)
            self._json_response(200, self.state.snapshot())
            return

        if self.path != "/api/v1/captures":
            self._json_response(404, {"detail": "Not found"})
            return

        payload = self._read_json()
        capture_id = str(payload.get("capture_id", "")).strip() or str(uuid4())
        request_number, scenario, flaky_fail_now = self.state.bump_request()

        emit(
            "capture_received",
            request_number=request_number,
            scenario=scenario,
            capture_id=capture_id,
            app_name=str(payload.get("app_name", "")),
        )

        if scenario == "success_fast":
            time.sleep(random.uniform(0.2, 0.4))
            self._json_response(200, self._success_payload(capture_id, scenario, request_number))
            return

        if scenario == "success_slow":
            time.sleep(random.uniform(2.0, 4.0))
            self._json_response(200, self._success_payload(capture_id, scenario, request_number))
            return

        if scenario == "http_500":
            self._json_response(500, {"detail": "Mock bridge forced HTTP 500"})
            return

        if scenario == "timeout":
            time.sleep(self.state.timeout_seconds)
            self._json_response(200, self._success_payload(capture_id, scenario, request_number))
            return

        if scenario == "malformed":
            self._json_response(200, {"capture_id": capture_id, "unexpected": "shape"})
            return

        if scenario == "flaky":
            if flaky_fail_now:
                self._json_response(500, {"detail": "Mock bridge flaky failure"})
                return
            time.sleep(random.uniform(0.2, 0.5))
            self._json_response(200, self._success_payload(capture_id, scenario, request_number))
            return

        self._json_response(500, {"detail": "Unhandled scenario"})

    def _success_payload(self, capture_id: str, scenario: str, request_number: int) -> dict[str, Any]:
        return {
            "capture_id": capture_id,
            "socratic_prompt": (
                f"[{scenario}] What first principle explains this step? "
                f"(mock request #{request_number})"
            ),
            "gaps": [
                {
                    "gap_id": str(uuid4()),
                    "concept": f"{scenario.replace('_', ' ').title()} Concept",
                    "severity": 0.56,
                    "confidence": 0.68,
                    "status": "open",
                    "capture_id": capture_id,
                    "evidence_url": "http://127.0.0.1:8011/mock/evidence.png",
                    "deadline_score": 0.44,
                    "priority_score": 0.52,
                }
            ],
            "readiness_axes": {
                "concept_mastery": 0.62,
                "deadline_pressure": 0.41,
                "retention_risk": 0.36,
                "problem_transfer": 0.58,
                "consistency": 0.73,
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sentinel overlay mock bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--scenario", choices=sorted(VALID_SCENARIOS), default="success_fast")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Used for timeout scenario; keep above desktop request timeout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = MockState(scenario=args.scenario, timeout_seconds=args.timeout_seconds)
    server = ThreadingHTTPServer((args.host, args.port), MockBridgeHandler)
    server.state = state  # type: ignore[attr-defined]

    emit(
        "server_started",
        host=args.host,
        port=args.port,
        scenario=args.scenario,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        emit("server_stopped", reason="keyboard_interrupt")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
