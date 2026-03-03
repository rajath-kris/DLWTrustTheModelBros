# Overlay Test Journey

This runbook validates the Sentinel overlay UX in isolation from the real bridge/Mission Control.

## One-command launch

```powershell
.\scripts\run-overlay-journey.ps1
```

The launcher starts:

1. `scripts/mock_bridge.py` on `http://127.0.0.1:8011`
2. `sentinel.main` with test mode enabled
3. `scripts/overlay_journey_report.py --follow` for live timeline output

When you finish, press Enter in the launcher terminal to stop processes and generate reports.

## Scenarios

Valid `-Scenario` values:

1. `success_fast`
2. `success_slow`
3. `http_500`
4. `timeout`
5. `malformed`
6. `flaky`

Switch scenario at runtime:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8011/__scenario -ContentType 'application/json' -Body '{"scenario":"http_500"}'
```

## Guided user journey

1. Start the script.
2. Trigger capture using `Alt+S` or the Journey Control panel.
3. Select a region and confirm selector completion in timeline output.
4. Observe first overlay prompt in glass card style with composer input area.
5. Click the composer, type a learner response, and press `Send`.
6. Confirm timeline shows `input_mode_entered`, `user_input_submitted`, `turn_analysis_started`.
7. Verify transition `prompt -> analyzing -> prompt` with cleared input.
8. Press `Esc` to verify dismissibility.
9. Force an error scenario and click `Retry` to validate retry after input.
10. For bridge-backed runs (not `mock_bridge.py`), validate reply policy turns:
    - on-track learner response -> `request_success` has `reply_mode=right_path_intuition`.
    - confused learner response -> `request_success` has `reply_mode=gentle_correction`.
    - unrelated learner response -> `request_success` has `reply_mode=off_topic_redirect`.
11. For bridge-backed runs, submit `got it` or `understood` and confirm `session_completed` event and immediate collapse to launcher.
12. Press Enter in launcher to end session.
13. Open `session-report.md` and `timeline.json` in the generated artifact directory.

## Artifacts

Each run writes:

1. `raw-sentinel.log`
2. `raw-sentinel.err.log`
3. `raw-mock-bridge.log`
4. `raw-mock-bridge.err.log`
5. `timeline.json`
6. `session-report.md`

Default path:

`artifacts/overlay-journey/<timestamp>/`

## Coverage checklist

1. Focus safety: overlay should not steal focus while shown.
2. Dismissibility: `Esc` closes selector or overlay immediately.
3. Latency visibility: analyzing state appears immediately after capture.
4. State consistency: timeline event order matches user-visible states.
5. Failure transparency: errors display actionable hints.
6. Input-required loop: `Send` requires non-empty text and logs submission telemetry.
7. Turn loop continuity: same thread progresses across turns until recapture.
8. Reply policy visibility: `request_success` telemetry carries `reply_mode` and `session_ended` fields on learner-input turns.
9. Completion closure: completion intents (`got it`, `understood`) trigger `session_completed` and collapse overlay to launcher.

## Quick validation commands

```powershell
# Success two-turn loop
.\scripts\run-overlay-journey.ps1 -Scenario success_fast

# Slow analysis visibility during input turns
.\scripts\run-overlay-journey.ps1 -Scenario success_slow

# Flaky fail-then-retry with same thread context
.\scripts\run-overlay-journey.ps1 -Scenario flaky
```
