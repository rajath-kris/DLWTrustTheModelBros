# Manual Integration Checklist

Fill each case with PASS or FAIL and attach evidence paths.

## Environment

* Date/time (local + UTC):
* OS/version:
* Monitor layout + scaling:
* Integration branch commit:

## Overlay + Capture

* \[PASS ] OV-01 Region selection opens.
* \[PASS] OV-02 Esc cancels selection without capture.
* \[ PASS] OV-03 Happy path capture -> analyzing -> Socratic prompt.
* \[PASS ] OV-04 Esc dismisses overlay immediately.
* \[N/A - input\_required=true keeps prompt visible until user action; auto-hide path intentionally inactive in this mode. ] OV-05 Auto-hide behavior is predictable.
* \[ PASS] OV-06 Right-edge placement clamps/flips correctly.
* \[ PASS] OV-07 Bottom-edge placement clamps correctly.
* \[ PASS] OV-08 Bridge-down fallback is actionable.
* \[ PASS] OV-09 Rapid captures (3-5) remain stable.
* \[ PASS] OV-10 Evidence persists to data/captures and data/state.json.
* Evidence: request\_success in artifacts/sentinel\_ui.log line 29; capture\_id=32da1332-b3bb-41aa-8c4f-ea490af80058; data/captures/32da1332-b3bb-41aa-8c4f-ea490af80058.png exists; data/state.json line 305 contains capture\_id.

## Turn Loop + Prompting

* \[ PASS] TL-01 Prompt asks learner where they are stuck.
* \[ PASS] TL-02 Learner reply causes follow-up Socratic prompt.
* Evidence: user\_input\_submitted -> turn\_analysis\_started -> turn\_prompt\_rendered sequence appears twice (for request 6 and 7) at 2026-03-01T18:03:57... and 2026-03-01T18:03:59....
* \[ PASS] TL-03 thread\_id remains stable across turns.
* Evidence: turn\_index increments correctly 0 -> 1 -> 2 across follow-up turns.
* \[PASS ] TL-04 turn\_index increments correctly.
* Evidence: overlay\_dismiss\_clicked + escape\_triggered + overlay\_hidden with "reason": "escape" at 2026-03-01T18:04:00....
* \[PASS ] TL-05 Prompting remains Socratic (no final-answer leakage).

## Mission Control + State

* \[PASS ] MC-01 GET /api/v1/state reflects latest capture.
* \[ PASS] MC-02 SSE stream updates Mission Control without refresh.
* \[ PASS] MC-03 Gap status cycle round-trips to API and UI.
* \[ PASS] MC-04 Latest prompt context is visible and current.

## Decision

* Release ready: YES / NO - YES
* Blocking issues:
* Owner branches for fixes:
