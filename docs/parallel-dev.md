# Parallel Development Guide

Use this guide to keep two-person development fast and conflict-light.

## Vision Scope

This scaffold implements the `vision.md` core loop:

1. Sentinel captures study context from any app.
2. Bridge API extracts signals and generates Socratic guidance.
3. Mission Control visualizes readiness and knowledge gaps.

## Team Split

### Track A: Sentinel Desktop

Primary ownership:

- `apps/sentinel-desktop/sentinel/*`

Responsibilities:

- Global trigger (`Alt+S`), region selection, capture fidelity.
- Overlay UX (positioning, readability, `Esc` dismissal, non-focus-stealing behavior).
- Capture payload correctness to `/api/v1/captures`.
- Sentinel UI reconstruction workflow defined in `docs/sentinel-ui-vision.md`.

Sentinel UI docs:

- `docs/sentinel-ui-vision.md` (source of truth for desktop visual system and interaction contracts)
- `docs/sentinel-ui-prompts/*` (prompt templates for component-level reconstruction and QA)

### Track B: Mission Control

Primary ownership:

- `apps/mission-control/src/*`

Responsibilities:

- Readiness radar and gap tracker UX.
- Poll + SSE state hydration from bridge API.
- Gap status updates and evidence rendering.

### Shared Contract (Joint Ownership)

Joint ownership (change only when necessary):

- `services/bridge-api/app/models.py`
- `shared/schemas/*`
- API behavior in `services/bridge-api/app/main.py`

Contract rules:

- Do not rename payload fields without updating both apps and schemas in the same PR.
- Keep values normalized to `[0,1]` for readiness/severity/confidence scores.
- Keep `capture_id`, `gap_id`, and timestamps stable and machine-readable.

## Branch Strategy

Recommended branch naming:

- `feature/sentinel-<topic>`
- `feature/mission-control-<topic>`
- `feature/bridge-contract-<topic>`

Keep PR scope narrow:

- One lane per PR when possible.
- If contract changes are required, include both consumers in the same PR.

## Local Run Pattern

From repo root:

```powershell
.\scripts\bootstrap.ps1
```

Then separate terminals:

```powershell
.\scripts\run-bridge.ps1
.\scripts\run-sentinel.ps1
.\scripts\run-mission-control.ps1
```

## Definition of Done (MVP)

- Sentinel capture reaches bridge (`POST /api/v1/captures` success).
- Bridge writes capture and updated state.
- Mission Control reflects state changes in near real time.
- Overlay shows Socratic prompt and closes on `Esc`.
- `python .\scripts\smoke_check.py` passes.
