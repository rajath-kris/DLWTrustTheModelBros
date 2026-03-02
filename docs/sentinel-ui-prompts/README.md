# Sentinel UI Prompt Workflow

Use this library to produce consistent, decision-complete UI specs for Sentinel desktop components before coding.

## Goals

- Keep all Sentinel UI reconstruction work aligned to `docs/sentinel-ui-vision.md`.
- Preserve behavior contracts while iterating on visuals.
- Produce repeatable implementation specs and QA reviews.

## Files

- `component-template.md`: base template for any Sentinel component.
- `overlay.md`: prompt spec template for `overlay.py`.
- `region-selector.md`: prompt spec template for `region_selector.py`.
- `journey-panel.md`: prompt spec template for `JourneyControlPanel` in `main.py`.
- `qa-review.md`: validation prompt for reviewing diffs and artifacts.

## Standard workflow

1. Pick the component file.
2. Start from `component-template.md` or component-specific file.
3. Fill in concrete token targets and constraints.
4. Implement manually in code.
5. Run QA prompt (`qa-review.md`) against diff + artifacts.
6. Accept only if visual, behavior, and warning-noise gates pass.

## Required constraints for all prompts

- No API/schema contract changes.
- No focus safety regressions.
- Esc dismiss paths remain immediate.
- Existing telemetry event names remain unchanged.

## Required validation commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\overlay.py .\apps\sentinel-desktop\sentinel\region_selector.py .\apps\sentinel-desktop\sentinel\window_effects.py .\apps\sentinel-desktop\sentinel\main.py
python .\scripts\smoke_check.py
```
