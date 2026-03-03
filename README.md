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

## New User Setup (Windows PowerShell)

Prerequisites:

- Python 3.11+ installed and available as `python`
- Node.js 20+ and `npm`
- Git

1. Get the code and switch to `main`:

```powershell
cd "C:\1Reju\Coding\HACKATHONS"
git clone https://github.com/rajath-kris/DLWTrustTheModelBros.git "Deep Learning Week 2026"
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
git branch --show-current
git checkout main
```

2. Bootstrap all dependencies and virtual environments:

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
.\scripts\bootstrap.ps1
```

3. Configure environment:

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
Copy-Item .env.example .env -Force
```

Set `OPENAI_API_KEY` in `.env` for live OpenAI behavior.  
Without API key, the local fallback path still works for end-to-end testing.

4. Start the full stack (bridge + Mission Control + Sentinel desktop):

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
.\scripts\run-demo-stack.ps1 -Action restart
.\scripts\run-demo-stack.ps1 -Action status
```

5. Seed demo courses/topics/materials/question bank (includes `EEE`):

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
.\services\bridge-api\.venv\Scripts\python.exe .\scripts\seed_demo_courses.py
```

6. Verify the app:

- Open Mission Control at the `mission_control_url` shown by `run-demo-stack -Action status`.
- Open course pages and confirm seeded topics/documents exist (for example `EEE`).
- Press `Alt+S`, capture a region, and confirm prompt + state update.

7. Stop everything when done:

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
.\scripts\run-demo-stack.ps1 -Action stop
```

Notes:

- If port `8000` is busy, the stack can auto-fallback to `18000`.
- If port `5173` is busy, the stack can auto-fallback to `15173`.
- Always use `.\scripts\run-demo-stack.ps1 -Action status` to see active URLs.

## Manual Start (Alternative)

If you prefer separate terminals instead of `run-demo-stack`:

```powershell
cd "C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026"
.\scripts\run-bridge.ps1
.\scripts\run-mission-control.ps1
.\scripts\run-sentinel.ps1
```

## Parallel Workflow

Use `docs/parallel-dev.md` as the team contract.

Recommended branch split:

- `feature/sentinel-*` for desktop capture/overlay.
- `feature/mission-control-*` for dashboard UI/UX.
- `feature/bridge-contract-*` only when payload/state contract changes are required.

## API Surface

- `GET /healthz`
- `GET /api/v1/sentinel/runtime`
- `POST /api/v1/sentinel/runtime/start`
- `POST /api/v1/sentinel/runtime/stop`
- `GET /api/v1/state`
- `GET /api/v1/brain/overview?course_id=<id|all>`
- `GET /api/v1/events/stream`
- `POST /api/v1/captures`
- `POST /api/v1/gaps/{gap_id}/status`
- `GET /api/v1/courses/{course_id}/deadlines`
- `POST /api/v1/courses/{course_id}/deadlines`
- `GET /api/v1/courses/{course_id}/documents`
- `POST /api/v1/courses/{course_id}/documents/upload`
- `POST /api/v1/courses/{course_id}/documents/{doc_id}/anchor`
- `DELETE /api/v1/courses/{course_id}/documents/{doc_id}`
- `GET /api/v1/courses/{course_id}/sessions`
- `POST /api/v1/quizzes/prepare`
- `POST /api/v1/quizzes/submit`
- `POST /api/v1/topics`
- `GET /api/v1/topics`
- `POST /api/v1/topics/{topic_id}/materials`
- `POST /api/v1/topics/active`
- `GET /api/v1/topics/active`

## Sentinel Runtime Control (Windows-First)

Mission Control can toggle Sentinel desktop runtime directly from the TopBar control.

- `POST /api/v1/sentinel/runtime/start` starts Sentinel (idempotent if already running).
- `POST /api/v1/sentinel/runtime/stop` stops all detected Sentinel processes (force-control-all).
- `GET /api/v1/sentinel/runtime` returns runtime status for button state.

Default runtime paths:

- Python: `apps/sentinel-desktop/.venv/Scripts/python.exe`
- Working dir: `apps/sentinel-desktop`

Optional overrides via `.env`:

- `SENTINEL_RUNTIME_ENABLED=1`
- `SENTINEL_RUNTIME_PYTHON=<path>`
- `SENTINEL_RUNTIME_WORKDIR=<path>`
- `SENTINEL_RUNTIME_STOP_TIMEOUT_SECONDS=2.0`

## Environment

Copy `.env.example` to `.env` (done by `bootstrap.ps1` if missing).

- With `OPENAI_API_KEY`: live OpenAI Vision + Socratic pipeline.
- Without `OPENAI_API_KEY`: local fallback prompt/gap path still works end-to-end.
- Optional `SENTINEL_ACTIVE_TOPIC_ID`: desktop capture payload includes this topic context.

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

## Topic-Bound Screenshot Flow (Warn + Continue)

Bridge supports topic/material uploads and active-topic grounding without Mission Control UI changes:

1. Create topic metadata with `POST /api/v1/topics`.
2. Upload topic materials with `POST /api/v1/topics/{topic_id}/materials` (`.pdf`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`).
3. Set active topic with `POST /api/v1/topics/active`.
4. Submit captures to `POST /api/v1/captures`.
5. Capture response includes optional `source_context` and `source_warning`.
   - No active topic warning: response continues with Socratic output.
   - Unmatched active topic warning: response continues with Socratic output.

Deterministic helper:

```powershell
python .\\scripts\\run-topic-bound-mock-flow.py
```

This writes an artifact under `artifacts/topic-bound-flow/` showing one matched and one unmatched path.

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
