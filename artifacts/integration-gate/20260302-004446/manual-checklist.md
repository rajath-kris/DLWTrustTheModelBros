# Manual Integration Checklist

Fill each case with PASS or FAIL and attach evidence paths.

## Environment

- Date/time (local + UTC):
- OS/version:
- Monitor layout + scaling:
- Integration branch commit:

## Overlay + Capture

- [ ] OV-01 Region selection opens.
- [ ] OV-02 Esc cancels selection without capture.
- [ ] OV-03 Happy path capture -> analyzing -> Socratic prompt.
- [ ] OV-04 Esc dismisses overlay immediately.
- [ ] OV-05 Auto-hide behavior is predictable.
- [ ] OV-06 Right-edge placement clamps/flips correctly.
- [ ] OV-07 Bottom-edge placement clamps correctly.
- [ ] OV-08 Bridge-down fallback is actionable.
- [ ] OV-09 Rapid captures (3-5) remain stable.
- [ ] OV-10 Evidence persists to data/captures and data/state.json.

## Turn Loop + Prompting

- [ ] TL-01 Prompt asks learner where they are stuck.
- [ ] TL-02 Learner reply causes follow-up Socratic prompt.
- [ ] TL-03 thread_id remains stable across turns.
- [ ] TL-04 turn_index increments correctly.
- [ ] TL-05 Prompting remains Socratic (no final-answer leakage).

## Mission Control + State

- [ ] MC-01 GET /api/v1/state reflects latest capture.
- [ ] MC-02 SSE stream updates Mission Control without refresh.
- [ ] MC-03 Gap status cycle round-trips to API and UI.
- [ ] MC-04 Latest prompt context is visible and current.

## Decision

- Release ready: YES / NO
- Blocking issues:
- Owner branches for fixes:
