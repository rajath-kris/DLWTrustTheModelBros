# Sentinel Overlay Reconstruction Prompt

## Goal

Reconstruct Sentinel overlay prompt card visuals in `apps/sentinel-desktop/sentinel/overlay.py` so the component remains non-intrusive and readable while matching `docs/sentinel-ui-vision.md`.

## In Scope

- Glass material tokens in `_apply_stylesheet()`
- Typography and spacing tuning
- Prompt/analyzing/thinking/error state visual consistency
- Action control visual treatment (including icon-only where specified)
- Blur call-site tuning in overlay (`apply_blur_behind_for_widget(...)`)

## Out of Scope

- `OverlayBubble` public method/signature changes
- Signal name or event name changes
- `main.py` controller flow changes
- Capture/hotkey/bridge behavior changes

## Files Allowed

- `apps/sentinel-desktop/sentinel/overlay.py`
- `apps/sentinel-desktop/sentinel/window_effects.py` (only if blur/tint adjustments are required)

## Behavior Constraints (Must Preserve)

- Signals:
  - `retry_requested`
  - `dismiss_requested`
  - `user_input_submitted`
- Methods:
  - `show_analyzing_state`
  - `show_thinking_state`
  - `show_prompt_input_state`
  - `show_error_state`
  - `hide_prompt`
  - `set_retry_enabled`
  - `set_telemetry_callback`
  - `reset_manual_position`
  - `reset_topic`
- Esc dismissal immediate
- Placement continuity and clamp behavior preserved
- No-focus-steal default preserved

## Visual Tokens

- Card alpha stops: `112/96/82`
- Composer alpha stops: `118/104`
- Divider alpha edges/center: `14/64`
- Message/input/loading sizes: `14/13/11`
- Action button size: `32-34w x 28h`
- Action button radius: `9`
- Primary accent family: `#5F9FD8`
- Tuning mode: `dwm_only`
- Runtime mode target: `dwm_first`

## State Matrix

| State | Visual behavior | Actions |
| --- | --- | --- |
| `ANALYZING` | status + loading text, no composer | none |
| `THINKING` | compact thinking text, no composer | none |
| `PROMPT` | message + divider + composer + action row | submit + dismiss |
| `ERROR` | message + action row, no composer | retry + dismiss |

## Failure / Edge Cases

- Busy wallpaper reduces contrast
- DWM not available and acrylic fallback tint masks QSS
- icon-only controls lose clarity if tooltips are missing
- stale process renders prior style snapshot

## Acceptance Criteria

- All four overlay states visually aligned with token targets
- No contract or behavior regressions
- Warning signatures do not increase:
  - `QPainter::begin...`
  - `QWindowsWindow::setGeometry...`

## Validation Commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\overlay.py .\apps\sentinel-desktop\sentinel\window_effects.py
python .\scripts\smoke_check.py
& .\scripts\run-overlay-journey.ps1 -Scenario success_fast
& .\scripts\run-overlay-journey.ps1 -Scenario flaky
```
