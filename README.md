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
- `POST /api/v1/modules`
- `GET /api/v1/modules`
- `POST /api/v1/modules/{module_id}/materials`
- `POST /api/v1/modules/active`
- `GET /api/v1/modules/active`

## Environment

Copy `.env.example` to `.env` (done by `bootstrap.ps1` if missing).

- With `OPENAI_API_KEY`: live OpenAI Vision + Socratic pipeline.
- Without `OPENAI_API_KEY`: local fallback prompt/gap path still works end-to-end.
- Optional `SENTINEL_ACTIVE_MODULE_ID`: desktop capture payload includes this module context.

## Smoke Check

Run the basic stack check:

```powershell
python .\scripts\smoke_check.py
```

This starts the bridge, posts a capture, verifies state increments, and exits.

## Mock Laplace Flow

Run a deterministic two-turn mock capture flow using one lecture fixture and one tutorial fixture for the same concept:

```powershell
python .\scripts\run-laplace-mock-flow.py
```

Fixtures:

- `docs/mock-content/laplace_lecture_slide.md`
- `docs/mock-content/laplace_tutorial.md`

The script posts both captures to `POST /api/v1/captures`, reuses thread context across turns, and writes a summary artifact under `artifacts/mock-laplace/`.

## Module-Bound Screenshot Flow (Warn + Continue)

Bridge supports module/material uploads and active-module grounding without Mission Control UI changes:

1. Create module metadata with `POST /api/v1/modules`.
2. Upload module materials with `POST /api/v1/modules/{module_id}/materials` (`.pdf`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`).
3. Set active module with `POST /api/v1/modules/active`.
4. Submit captures to `POST /api/v1/captures`.
5. Capture response includes optional `source_context` and `source_warning`.
   - No active module warning: response continues with Socratic output.
   - Unmatched active module warning: response continues with Socratic output.

Deterministic helper:

```powershell
python .\\scripts\\run-module-bound-mock-flow.py
```

This writes an artifact under `artifacts/module-bound-flow/` showing one matched and one unmatched path.

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
