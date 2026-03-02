# Sentinel Region Selector Reconstruction Prompt

## Goal

Reconstruct selector visuals in `apps/sentinel-desktop/sentinel/region_selector.py` so mask, selection box, and instruction pill match Sentinel UI vision while preserving region-capture behavior.

## In Scope

- Mask opacity and cutout clarity
- Selection border color, thickness, and anti-aliasing presentation
- Instruction pill typography/material
- Selector visual consistency with overlay card language

## Out of Scope

- Region math behavior changes
- Telemetry event semantic changes
- Capture payload contract changes
- Hotkey trigger behavior changes

## Files Allowed

- `apps/sentinel-desktop/sentinel/region_selector.py`
- `apps/sentinel-desktop/sentinel/ui_theme.py` (if shared typography/token helper needed)

## Behavior Constraints (Must Preserve)

- Drag selection behavior
- Esc immediate cancel
- `selector_opened`, `selector_completed`, `selector_cancelled` event flow
- selected region normalization logic

## Visual Tokens

- Mask base alpha: tuned for readability with visible context
- Selection stroke: high-visibility accent, width `2px`
- Pill radius: >= `20px`
- Pill text hierarchy:
  - heading ~`14px`
  - hint ~`11px`
- Fade-in easing aligned with UI motion tokens

## State Matrix

| State | Visual behavior | Notes |
| --- | --- | --- |
| Idle | full-screen dim mask + instruction pill | no cutout |
| Dragging | clear cutout + selection border | live update |
| Escape | close immediately | no lingering paint artifacts |

## Failure / Edge Cases

- 4K/high DPI coordinate rendering
- mixed monitor scale factors
- insufficient contrast on bright wallpapers
- composition mode artifacts

## Acceptance Criteria

- Selection rectangle is precise and visually obvious
- Instruction pill remains readable on light/dark scenes
- No behavior regression in cancel/complete paths
- No warning-noise increase

## Validation Commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\region_selector.py .\apps\sentinel-desktop\sentinel\ui_theme.py
python .\scripts\smoke_check.py
```
