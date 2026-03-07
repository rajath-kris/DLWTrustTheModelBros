# Sentinel AI MVP 

## Demo Note

For judging clarity: we could not reliably fit every feature into a strict two-minute live demo. The system is still hard to run end-to-end on macOS, and setup/stack orchestration on Windows is also non-trivial. Because of that, we recorded and shared an uncut demo video so reviewers can see all implemented features and full runtime behavior without cuts. We also want to acknowledge that parts of this project were built while some team members who were operating from an active war zone and we would like to appreciate their committment to this hackathon even while in potential danger. The demo video is below ( just click on the embedded image ).

[![Watch the demo](https://img.youtube.com/vi/ZSyA_XS9AMg/hqdefault.jpg)](https://youtu.be/ZSyA_XS9AMg)


## New User Setup (Windows PowerShell)

Prerequisites:

- Python 3.11+ installed and available as `python`
- Node.js 20+ and `npm`
- Git

1. Get the code and switch to `main`:

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
