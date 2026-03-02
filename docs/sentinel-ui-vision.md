# Sentinel Desktop UI Vision

## 1) Purpose + Scope

This document defines the visual and interaction system for Sentinel desktop UI components in:

- `apps/sentinel-desktop/sentinel/overlay.py`
- `apps/sentinel-desktop/sentinel/region_selector.py`
- `apps/sentinel-desktop/sentinel/main.py` (Journey Control panel)
- `apps/sentinel-desktop/sentinel/ui_theme.py`
- `apps/sentinel-desktop/sentinel/window_effects.py` (composition policy only)

This document explicitly excludes Mission Control (`apps/mission-control/*`).

### Non-goals

- No bridge/API/schema contract changes.
- No capture/hotkey behavior contract changes.
- No changes that violate focus safety or immediate Esc dismiss behavior.

## 2) Design Principles

- Non-intrusive first: UI must assist without stealing focus.
- Immediate status clarity: states must be instantly recognizable.
- Readability over decoration: contrast and typography must remain legible on varied wallpapers.
- Consistent materials: overlay, selector, and control panel must share one visual language.
- Predictable interaction: Esc paths, placement, and action semantics stay stable.

## 3) Visual System Tokens

Use these tokens as target values unless explicitly overridden by component constraints.

### Material Tokens

| Token | Target |
| --- | --- |
| `card.radius` | `16px` |
| `card.border.alpha` | `62-74` |
| `card.fill.alpha.stops` | `112 / 96 / 82` |
| `highlight.rail.height` | `2px` |
| `divider.height` | `1px` |
| `divider.alpha.edges/center` | `14 / 64` |
| `composer.radius` | `11px` |
| `composer.fill.alpha.stops` | `118 / 104` |
| `composer.border.alpha` | `56-62` |

### Typography Tokens

| Token | Target |
| --- | --- |
| `font.family` | from `qss_font_family_stack(...)` |
| `message.size/weight` | `14px / 500` |
| `input.size/weight` | `13px / 450` |
| `loading.size/weight` | `11px / 450` |
| `button.icon.size/weight` | `12px / 600` |

### Spacing Tokens

| Token | Target |
| --- | --- |
| `card.padding` | `15 12 15 12` |
| `card.spacing` | `8px` |
| `action.gap` | `6px` |
| `button.size` | `32-34w x 28h` |
| `button.radius` | `9px` |

### Color Tokens

| Token | Target |
| --- | --- |
| `accent.primary.base` | neutral blue (`#5F9FD8` family) |
| `text.primary` | light cool white (`alpha >= 226`) |
| `text.secondary` | muted cool gray-blue |
| `frost.secondary.button` | near-white low alpha gradient |
| `selection.stroke` | bright green accent (selector) |

### Motion Tokens

| Token | Target |
| --- | --- |
| `overlay.show.duration` | `160-190ms` |
| `overlay.refresh.duration` | `120-150ms` |
| `overlay.hide.duration` | `110-140ms` |
| `easing` | `OutCubic` |
| `escape.hide` | immediate |

## 4) Blur / Composition Policy

Native composition is controlled via `SENTINEL_OVERLAY_BLUR_MODE`.

### Runtime modes

- `dwm_first`: production default, preferred for balanced style fidelity.
- `dwm_only`: tuning mode for style work and screenshot comparisons.
- `acrylic_first`: use only when DWM-only parity is unacceptable on specific machines.
- `acrylic_only`: diagnostic fallback.
- `off`: style-isolation diagnostic mode.

### Rules

- Do not raise acrylic tint alpha to values that mask QSS layers.
- Prefer DWM path first to preserve QSS-authored materials.
- Any blur tuning must preserve readability and avoid warning-noise regressions.

## 5) Component Specs

## 5.1 Overlay Prompt Card (`overlay.py`)

### State matrix

| State | Surface | Actions | Required messaging |
| --- | --- | --- | --- |
| `ANALYZING` | glass card + loading label | none | status + progress text |
| `THINKING` | same material | none | concise thinking text |
| `PROMPT` | same material + composer | submit + dismiss | Socratic prompt text |
| `ERROR` | same material | retry + dismiss | explicit error + hint |

### Contract constraints

- Keep controller API and telemetry events unchanged.
- Keep no-focus-steal default and click-to-focus input mode.
- Keep placement continuity for same capture region.

## 5.2 Region Selector (`region_selector.py`)

### Visual contract

- Dark mask overlay with clear cutout around selection rectangle.
- High-visibility selection border and instruction pill.
- Instruction pill typography aligned with Sentinel tokens.

### Behavior contract

- Drag to select region.
- Esc cancels immediately.
- No regressions in emitted telemetry events.

## 5.3 Journey Control Panel (`main.py`, `JourneyControlPanel`)

### Visual contract

- Same color/material family as overlay, but panel-specific layout.
- Clear title, scenario, hint, and primary trigger control.
- Preserve test-mode semantics and local shortcut behavior.

## 6) Interaction Contracts

- Focus safety:
  - Overlay defaults to non-activating display.
  - Input focus enters only on explicit user intent.
- Esc paths:
  - Selector Esc cancels immediately.
  - Overlay Esc dismisses immediately.
- Pointer behavior:
  - Action controls use pointer cursor.
  - No hidden drag logic in overlay.
- Placement:
  - Near-region anchor with clamp to active screen.
  - No center-jump regressions between thinking and prompt states.

## 7) Accessibility and Legibility

- Minimum size:
  - prompt/message text >= `14px`
  - input text >= `13px`
- Keep tooltips for icon-only buttons:
  - Submit (Enter), Dismiss (Esc), Retry request
- Maintain sufficient text/background contrast on light and dark wallpapers.
- Keep text selectable in message area.

## 8) Quality Gates

Every Sentinel UI slice must satisfy:

### Visual gates

- Component screenshots captured for target states.
- Cross-component token consistency check.
- No readability regressions on bright/dark backgrounds.

### Behavior gates

- Focus safety intact.
- Esc immediate dismissal intact.
- Placement continuity intact.
- Existing signals/method contracts unchanged.

### Warning-noise gates

No increase in:

- `QPainter::begin...`
- `QWindowsWindow::setGeometry...`

Compared in:

- `artifacts/sentinel_ui.log`
- latest `artifacts/overlay-journey/*/raw-sentinel.err.log`

### Required checks

```powershell
Set-Location -LiteralPath 'C:\1Reju\Coding\HACKATHONS\Deep Learning Week 2026'
python -m py_compile .\apps\sentinel-desktop\sentinel\overlay.py .\apps\sentinel-desktop\sentinel\region_selector.py .\apps\sentinel-desktop\sentinel\window_effects.py .\apps\sentinel-desktop\sentinel\main.py
python .\scripts\smoke_check.py
```

## 9) Change Governance

- All Sentinel UI changes must reference this vision doc and one component prompt spec from `docs/sentinel-ui-prompts/*`.
- Changes must be shipped in phased component slices:
  - overlay
  - selector
  - journey panel
  - cross-component harmonization
- One slice per commit when possible.
- Every slice commit must include:
  - what changed
  - verification evidence
  - rollback notes

## Prompt Workflow Reference

Prompt specs and QA templates live in:

- `docs/sentinel-ui-prompts/README.md`
- `docs/sentinel-ui-prompts/component-template.md`
- `docs/sentinel-ui-prompts/overlay.md`
- `docs/sentinel-ui-prompts/region-selector.md`
- `docs/sentinel-ui-prompts/journey-panel.md`
- `docs/sentinel-ui-prompts/qa-review.md`
