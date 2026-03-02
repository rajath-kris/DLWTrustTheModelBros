# Sentinel UI Component Prompt Template

## Goal

Define the target visual and interaction behavior for `[COMPONENT_NAME]` in Sentinel desktop.

## In Scope

- `[LIST VISUAL/MATERIAL/TYPO/SPACING CHANGES]`
- `[LIST ANIMATION OR TRANSITION TUNING]`

## Out of Scope

- API/schema changes
- Mission Control changes
- Capture/hotkey contract changes
- Behavior rewrites outside listed component

## Files Allowed

- `[PRIMARY FILES]`

## Behavior Constraints (Must Preserve)

- `Alt+S` capture flow unchanged
- Esc dismiss/cancel path unchanged
- Non-focus-stealing behavior preserved
- Existing telemetry event names unchanged
- Existing public method/signal contracts unchanged

## Visual Tokens

- Card/surface alpha targets: `[VALUES]`
- Border/radius targets: `[VALUES]`
- Typography scale/weights: `[VALUES]`
- Spacing and control density: `[VALUES]`
- Motion timings/easing: `[VALUES]`
- Blur mode during tuning/runtime: `[VALUES]`

## State Matrix

| State | Visual behavior | Action controls | Notes |
| --- | --- | --- | --- |
| `[STATE_1]` | `[TARGET]` | `[ACTIONS]` | `[NOTES]` |
| `[STATE_2]` | `[TARGET]` | `[ACTIONS]` | `[NOTES]` |

## Failure / Edge Cases

- Mixed DPI / multi-monitor behavior
- Bright and dark wallpaper readability
- Windows composition unavailable
- Stale process rendering old style

## Acceptance Criteria

- Visual parity against token targets in all relevant states
- No regressions in keyboard/focus/placement contracts
- No warning-noise increase in known signatures

## Validation Commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\overlay.py .\apps\sentinel-desktop\sentinel\region_selector.py .\apps\sentinel-desktop\sentinel\window_effects.py .\apps\sentinel-desktop\sentinel\main.py
python .\scripts\smoke_check.py
```

Optional overlay behavioral runs:

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
& .\scripts\run-overlay-journey.ps1 -Scenario success_fast
& .\scripts\run-overlay-journey.ps1 -Scenario flaky
```
