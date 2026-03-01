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
4. Observe overlay state transitions (`analyzing` -> `prompt` or `error`).
5. Press `Esc` to verify dismissibility.
6. Force an error scenario and click `Retry`.
7. Press Enter in launcher to end session.
8. Open `session-report.md` and `timeline.json` in the generated artifact directory.

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
