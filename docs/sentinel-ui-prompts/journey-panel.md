# Sentinel Journey Control Panel Reconstruction Prompt

## Goal

Refine `JourneyControlPanel` visual system in `apps/sentinel-desktop/sentinel/main.py` so it matches Sentinel desktop language while preserving test-mode controls and shortcuts.

## In Scope

- Panel color/material system
- Typography hierarchy for title/scenario/hint
- Trigger button material and density
- Fade-in visual consistency

## Out of Scope

- Scenario/test-mode logic changes
- Shortcut behavior changes
- Controller event semantics

## Files Allowed

- `apps/sentinel-desktop/sentinel/main.py` (JourneyControlPanel section)
- `apps/sentinel-desktop/sentinel/ui_theme.py` (if needed for shared style helpers)

## Behavior Constraints (Must Preserve)

- `capture_requested` signal behavior
- local trigger shortcut behavior
- panel fade-in behavior and tool-window semantics
- existing scenario labeling and test-mode hints

## Visual Tokens

- Panel radius and border aligned with overlay tokens
- Text hierarchy:
  - title: strongest
  - scenario: medium
  - hint: supportive
- Trigger button: primary accent treatment consistent with overlay
- padding and spacing aligned with compact Sentinel density

## State Matrix

| State | Visual behavior |
| --- | --- |
| Panel open | clear hierarchy and readable controls |
| Fade-in | smooth non-distracting entrance |
| Trigger pressed | clear active state feedback |

## Failure / Edge Cases

- test mode off (panel absent)
- long scenario labels wrapping awkwardly
- low contrast in unusual desktop themes

## Acceptance Criteria

- Visual language matches overlay/selector
- Trigger action behavior unchanged
- No regressions in shortcut or panel lifecycle

## Validation Commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\main.py .\apps\sentinel-desktop\sentinel\ui_theme.py
python .\scripts\smoke_check.py
```
