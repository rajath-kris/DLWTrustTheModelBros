# Sentinel UI QA Review Prompt

## Goal

Review a Sentinel UI slice diff and artifact set for visual quality, behavior safety, and warning-noise regressions.

## Inputs

- Git diff for target slice
- Screenshot artifacts (before/after)
- Logs:
  - `artifacts/sentinel_ui.log`
  - latest `artifacts/overlay-journey/*/raw-sentinel.err.log`
- Validation outputs from compile/smoke checks

## Review Focus

1. Visual fidelity to `docs/sentinel-ui-vision.md` tokens
2. Behavior contract preservation
3. Warning-noise regression detection
4. Edge-case handling quality

## Must-Check Behavior Contracts

- No focus steal regression
- Esc immediate dismissal
- Stable placement/clamp behavior
- Unchanged public methods/signals and telemetry event names

## Warning Signatures

Track before/after counts for:

- `QPainter::begin...`
- `QWindowsWindow::setGeometry...`

Reject if increased without explicit, justified exception.

## Output Format

### Findings (ordered by severity)

- `Critical`: behavior contract breaks
- `Major`: clear UX regression
- `Minor`: polish inconsistency

### Decision

- `Pass` only if all required gates are satisfied.
- `Fail` with concrete remediation items otherwise.

### Evidence Summary

- file paths
- command outputs
- warning signature deltas

## Validation Commands

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\overlay.py .\apps\sentinel-desktop\sentinel\region_selector.py .\apps\sentinel-desktop\sentinel\window_effects.py .\apps\sentinel-desktop\sentinel\main.py
python .\scripts\smoke_check.py
```
