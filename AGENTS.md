# AGENTS.md

## Purpose

Define how Codex should execute work in this repository.
Treat this file as the operational playbook for implementing `vision.md`.

## Source of Truth

1. Product specification: `vision.md`
2. API/data contract: `services/bridge-api/app/models.py` and `shared/schemas/*`
3. Runtime wiring/config: `.env.example`, `services/bridge-api/app/config.py`, `apps/sentinel-desktop/sentinel/config.py`

If implementation and docs conflict, align code to `vision.md` and update stale docs in the same change.

## Non-Negotiable Engineering Rules

- Use tight iteration loops: implement -> run -> verify -> commit.
- Make small, reversible changes: avoid giant multi-system dumps in one commit.
- Prioritize observable behavior: logs, smoke checks, and reproducible outcomes.
- Use goal completion criteria, not time-based language. Do not mention hours.

## Product Goals (From vision.md)

### Goal 1: App-Agnostic Capture Trigger

Deliver reliable user-triggered capture from any desktop app.

Required behavior:

- Global hotkey (`Alt+S`) opens region capture.
- User can cancel quickly with `Esc`.
- Capture payload includes platform, active app/window, monitor, region, and image.

Primary files:

- `apps/sentinel-desktop/sentinel/hotkey.py`
- `apps/sentinel-desktop/sentinel/region_selector.py`
- `apps/sentinel-desktop/sentinel/capture.py`
- `apps/sentinel-desktop/sentinel/bridge_client.py`

### Goal 2: Non-Intrusive Socratic Overlay

Deliver a floating prompt overlay that helps without interrupting focus.

Required behavior:

- Overlay does not steal focus from the study app.
- Overlay appears near selected region, clamps on-screen.
- `Esc` dismisses overlay immediately.
- Overlay auto-hide remains predictable.

Primary files:

- `apps/sentinel-desktop/sentinel/overlay.py`
- `apps/sentinel-desktop/sentinel/main.py`

### Goal 3: Multimodal Interpretation + Socratic Guidance

Convert screenshot context into Socratic guidance and structured gaps.

Required behavior:

- Use Azure Vision for OCR/caption/tag extraction when configured.
- Use Socratic prompting for guided questions (not final answers).
- Enforce syllabus anchor in prompt generation.
- Return strict structured output (`socratic_prompt`, `gaps`).

Primary files:

- `services/bridge-api/app/azure_clients.py`
- `services/bridge-api/app/prompting.py`
- `syllabus.json`

### Goal 4: Knowledge Gap + Readiness State

Persist learning events and compute readiness axes used by dashboard.

Required behavior:

- Save capture evidence to `data/captures`.
- Append capture events and gaps to `data/state.json`.
- Recompute readiness axes after state mutations.

Primary files:

- `services/bridge-api/app/main.py`
- `services/bridge-api/app/state_store.py`
- `services/bridge-api/app/readiness.py`

### Goal 5: Mission Control Live Visibility

Expose real-time learning state to the dashboard.

Required behavior:

- `GET /api/v1/state` provides canonical state.
- SSE stream pushes state updates.
- Dashboard renders readiness radar and gap tracker.
- Gap status updates round-trip to API.

Primary files:

- `services/bridge-api/app/sse.py`
- `apps/mission-control/src/api.ts`
- `apps/mission-control/src/App.tsx`

## Risk-Control Goals (No Time Language)

Implement these as ongoing quality gates:

- Focus safety gate: overlay must remain non-focus-stealing and always dismissible.
- DPI fidelity gate: region-to-screenshot mapping must remain correct across scale factors.
- Latency gate: send cropped regions, not full-screen captures when avoidable.
- Hallucination gate: keep gap detection bounded by syllabus anchor.
- Bridge reliability gate: CORS/port defaults must keep local apps connected (`127.0.0.1:8000`).

## Iteration Protocol

For each change set:

1. Define one target behavior and one measurable check.
2. Edit the smallest viable surface area.
3. Run relevant checks immediately.
4. Inspect outputs/logs and confirm observable behavior.
5. Commit only when the change is reversible and verified.

Preferred check order:

1. `python scripts/smoke_check.py`
2. `npm run build` in `apps/mission-control`
3. targeted python syntax or module checks for changed files
4. manual run: `scripts/run-bridge.ps1`, `scripts/run-sentinel.ps1`, `scripts/run-mission-control.ps1`

## Change Size Policy

- Prefer narrow PRs by lane:
  - Sentinel lane: `apps/sentinel-desktop/*`
  - Mission-control lane: `apps/mission-control/*`
  - Contract lane: `services/bridge-api/*` + `shared/schemas/*`
- If changing contract fields, update both producer and consumers in one PR.
- Avoid unrelated refactors while implementing feature work.

## Observability Requirements

Every meaningful behavior change should include at least one of:

- A deterministic smoke check path.
- Machine-readable API response verification.
- Visible UI behavior verification.
- Logs that identify capture flow context (`capture_id`, endpoint path, failure reason).

Minimum must-pass before merge:

- Bridge health endpoint responds.
- Capture POST succeeds and increments state.
- Dashboard build passes.

## Commit Quality Standard

Each commit message should answer:

- What behavior changed?
- How was it verified?
- How to rollback if needed?

Keep commits atomic and reviewable.

## Definition of Done (MVP)

The MVP is done when all are true:

- A user can trigger capture from any app with `Alt+S`.
- Overlay returns a Socratic prompt and closes with `Esc`.
- Bridge persists capture and gap data.
- Mission Control updates readiness/gaps from bridge state.
- Local smoke checks pass on a clean clone with documented setup.
