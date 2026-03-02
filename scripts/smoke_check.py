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
from urllib.parse import urlparse
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


def _wait_for_health(
    bridge_url: str,
    timeout_seconds: float,
    proc: subprocess.Popen[str] | None = None,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            stderr = ""
            if proc.stderr is not None:
                try:
                    stderr = proc.stderr.read()[-1200:]
                except Exception:  # noqa: BLE001
                    stderr = ""
            raise RuntimeError(
                "Bridge process exited before health check passed. "
                f"Exit code: {proc.returncode}. "
                f"Stderr tail: {stderr.strip()}"
            )
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
    parsed = urlparse(args.bridge_url.rstrip('/'))
    bridge_host = parsed.hostname or '127.0.0.1'
    bridge_port = parsed.port or 8000

    proc = subprocess.Popen(
        [bridge_python, '-m', 'uvicorn', 'app.main:app', '--host', bridge_host, '--port', str(bridge_port)],
        cwd=str(bridge_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout_tail = ''
    stderr_tail = ''
    exit_code = 0

    try:
        health = _wait_for_health(args.bridge_url.rstrip('/'), args.startup_timeout, proc=proc)
        time.sleep(0.2)
        if proc.poll() is not None:
            stderr = ''
            if proc.stderr is not None:
                try:
                    stderr = proc.stderr.read()[-1200:]
                except Exception:  # noqa: BLE001
                    stderr = ''
            raise RuntimeError(
                "Bridge process exited after health check. "
                f"Exit code: {proc.returncode}. "
                f"Stderr tail: {stderr.strip()}"
            )
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

        captures_before = len(state_before.get('captures', []))
        captures_after = len(state_after.get('captures', []))

        summary = {
            'ok': captures_after >= captures_before + 1,
            'health_status': health.get('status'),
            'captures_before': captures_before,
            'captures_after': captures_after,
            'gaps_after': len(state_after.get('gaps', [])),
            'returned_capture_id': capture.get('capture_id'),
            'returned_gap_count': len(capture.get('gaps', [])),
        }
        print(json.dumps(summary, indent=2))

        if not summary['ok']:
            exit_code = 1

    except (RuntimeError, URLError, OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2))
        exit_code = 1

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

        lowered_stderr = stderr_tail.lower()
        if 'error while attempting to bind' in lowered_stderr or 'address already in use' in lowered_stderr:
            exit_code = 1
        if proc.returncode not in (None, 0) or exit_code != 0:
            if stdout_tail.strip():
                print('---BRIDGE_STDOUT---')
                print(stdout_tail)
            if stderr_tail.strip():
                print('---BRIDGE_STDERR---')
                print(stderr_tail)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
