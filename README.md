# Sentinel AI MVP (Vision Scaffold)

Minimal monorepo scaffold for the `vision.md` loop:

- `apps/sentinel-desktop`: The Sentinel + Overlay (`Alt+S`, region capture, floating Socratic bubble).
- `services/bridge-api`: FastAPI bridge on `127.0.0.1:8000` (capture ingest, gap extraction, readiness state).
- `apps/mission-control`: The Brain dashboard on `127.0.0.1:5173` (radar + gap tracker + live stream).
- `shared/schemas`: shared payload/state contract references.

The goal is to let two developers work in parallel with low merge conflict:

- Dev A owns Sentinel (`apps/sentinel-desktop`).
- Dev B owns Mission Control (`apps/mission-control`).
- Both integrate through the bridge contract (`services/bridge-api` + `shared/schemas`).

## Quick Start

From repo root:

```powershell
.\scripts\bootstrap.ps1
```

Then run in separate terminals:

```powershell
.\scripts\run-bridge.ps1
.\scripts\run-mission-control.ps1
.\scripts\run-sentinel.ps1
```

Manual user test:

1. Press `Alt+S`.
2. Drag a screen region.
3. Verify overlay shows `Analyzing capture...` then a Socratic prompt.
4. Verify Mission Control updates.

## Parallel Workflow

Use `docs/parallel-dev.md` as the team contract.

Recommended branch split:

- `feature/sentinel-*` for desktop capture/overlay.
- `feature/mission-control-*` for dashboard UI/UX.
- `feature/bridge-contract-*` only when payload/state contract changes are required.

## API Surface

- `GET /healthz`
- `GET /api/v1/state`
- `GET /api/v1/events/stream`
- `POST /api/v1/captures`
- `POST /api/v1/gaps/{gap_id}/status`

## Environment

Copy `.env.example` to `.env` (done by `bootstrap.ps1` if missing).

- With Azure keys: live Vision/OpenAI pipeline.
- Without Azure keys: local fallback prompt/gap path still works end-to-end.

## Smoke Check

Run the basic stack check:

```powershell
python .\scripts\smoke_check.py
```

This starts the bridge, posts a capture, verifies state increments, and exits.

## Overlay Isolated Journey (One Command)

Run the overlay in an isolated environment with a mock bridge, live timeline, and session artifacts:

```powershell
.\scripts\run-overlay-journey.ps1
```

Useful options:

```powershell
.\scripts\run-overlay-journey.ps1 -Scenario flaky
.\scripts\run-overlay-journey.ps1 -Scenario success_slow -SkipBootstrap
```

What this does:

1. Starts a local mock bridge on `127.0.0.1:8011`.
2. Starts sentinel desktop in test mode with local Journey Control trigger.
3. Streams timeline events in terminal while you perform capture/escape/retry actions.
4. Writes artifacts to `artifacts/overlay-journey/<timestamp>/`:
   - `raw-sentinel.log`
   - `raw-mock-bridge.log`
   - `timeline.json`
   - `session-report.md`

Prompt-by-prompt input loop (desktop overlay):

1. Trigger a capture (`Alt+S` or Journey Control button).
2. Select region and wait for the first Socratic prompt card.
3. Click input area to enter text mode, type one response, then press `Send` (or Enter).
4. Overlay transitions to analyzing and then returns with next prompt + cleared input box.
5. Retry/Dismiss remain available; `Esc` dismisses selector/overlay.

Input behavior defaults:

- `SENTINEL_OVERLAY_INPUT_REQUIRED=1`
- `SENTINEL_OVERLAY_INPUT_MAX_CHARS=280`
- `SENTINEL_OVERLAY_SHOW_INPUT_CONFIRMATION=1`

See `docs/overlay-test-journey.md` for full scenario matrix and guided steps.
