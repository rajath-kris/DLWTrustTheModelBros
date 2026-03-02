#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ONE_PIXEL_PNG_BASE64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgS4m5n4AAAAASUVORK5CYII='
)


def _request_json(url: str, method: str = 'GET', payload: dict | None = None, timeout: float = 12.0) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _wait_for_health(bridge_url: str, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return _request_json(f'{bridge_url}/healthz', timeout=2.5)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f'Bridge did not become healthy in time. Last error: {last_error}')


def _resolve_bridge_python(repo_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit

    candidates = [
        repo_root / 'services/bridge-api/.venv/Scripts/python.exe',
        repo_root / 'services/bridge-api/.venv/bin/python',
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description='Basic Sentinel stack smoke check')
    parser.add_argument('--repo-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--bridge-url', default='http://127.0.0.1:8000')
    parser.add_argument('--bridge-python', default=None)
    parser.add_argument('--startup-timeout', type=float, default=15.0)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    bridge_dir = repo_root / 'services/bridge-api'
    bridge_python = _resolve_bridge_python(repo_root, args.bridge_python)

    proc = subprocess.Popen(
        [bridge_python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
        cwd=str(bridge_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout_tail = ''
    stderr_tail = ''

    try:
        health = _wait_for_health(args.bridge_url.rstrip('/'), args.startup_timeout)
        state_before = _request_json(f"{args.bridge_url.rstrip('/')}/api/v1/state")

        sample_path = repo_root / 'data/captures/smoke-test-capture.png'
        if sample_path.exists():
            image_bytes = sample_path.read_bytes()
        else:
            image_bytes = base64.b64decode(ONE_PIXEL_PNG_BASE64)

        payload = {
            'platform': 'windows',
            'app_name': 'Smoke Check',
            'window_title': 'Smoke Check Window',
            'monitor': {'left': 0, 'top': 0, 'width': 1920, 'height': 1080, 'scale': 1.0},
            'region': {'x': 100, 'y': 100, 'width': 320, 'height': 200},
            'image_base64': base64.b64encode(image_bytes).decode('utf-8'),
        }

        capture = _request_json(
            f"{args.bridge_url.rstrip('/')}/api/v1/captures",
            method='POST',
            payload=payload,
        )
        state_after = _request_json(f"{args.bridge_url.rstrip('/')}/api/v1/state")

        state_schema_ok = int(state_after.get("schema_version", -1)) == 1
        capture_schema_ok = int(capture.get("schema_version", -1)) == 1

        captures_before = len(state_before.get('captures', []))
        captures_after = len(state_after.get('captures', []))

        summary = {
            'ok': captures_after >= captures_before + 1 and state_schema_ok and capture_schema_ok,
            'health_status': health.get('status'),
            'captures_before': captures_before,
            'captures_after': captures_after,
            'gaps_after': len(state_after.get('gaps', [])),
            'returned_capture_id': capture.get('capture_id'),
            'returned_gap_count': len(capture.get('gaps', [])),
            'state_schema_version': state_after.get('schema_version'),
            'capture_schema_version': capture.get('schema_version'),
        }
        print(json.dumps(summary, indent=2))

        if not summary['ok']:
            return 1
        return 0

    except (RuntimeError, URLError, OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2))
        return 1

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate(timeout=3)
            stdout_tail = out[-800:]
            stderr_tail = err[-1200:]
        else:
            out, err = proc.communicate(timeout=2)
            stdout_tail = out[-800:]
            stderr_tail = err[-1200:]

        if proc.returncode not in (None, 0):
            if stdout_tail.strip():
                print('---BRIDGE_STDOUT---')
                print(stdout_tail)
            if stderr_tail.strip():
                print('---BRIDGE_STDERR---')
                print(stderr_tail)


if __name__ == '__main__':
    raise SystemExit(main())
