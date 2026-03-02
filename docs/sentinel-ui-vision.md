# Sentinel Desktop UI Vision

## 1) Purpose + Scope

This document defines the visual and interaction system for Sentinel desktop UI components in:

- `apps/sentinel-desktop/sentinel/overlay.py`
- `apps/sentinel-desktop/sentinel/region_selector.py`
- `apps/sentinel-desktop/sentinel/main.py` (Journey Control panel)
- `apps/sentinel-desktop/sentinel/ui_theme.py`
- `apps/sentinel-desktop/sentinel/window_effects.py` (diagnostic utility; not active in overlay runtime)

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
| `card.border.alpha` | `88` |
| `card.fill` | solid black tint `rgba(8,11,15,166)` (no gradient) |
| `highlight.rail.height` | `2px` |
| `divider.height` | `1px` |
| `divider.alpha` | `56` |
| `composer.radius` | `11px` |
| `composer.fill` | solid black `rgba(0,0,0,214)` (more opaque than card) |
| `composer.border.alpha` | `74` |

### Typography Tokens

| Token | Target |
| --- | --- |
| `font.family` | from `qss_font_family_stack(...)` |
| `message.size/weight` | `13px / 500` |
| `input.size/weight` | `12px / 450` |
| `loading.size/weight` | `10px / 450` |
| `button.icon.size/weight` | `11px / 600` |

### Spacing Tokens

| Token | Target |
| --- | --- |
| `card.padding` | `14 10 14 10` |
| `card.spacing` | `6px` |
| `composer.padding` | `8 5 8 5` |
| `action.gap` | `6px` |
| `button.size` | `32-34w x 28h` |
| `button.radius` | `9px` |

### Color Tokens

| Token | Target |
| --- | --- |
| `card.base` | near-black translucent (`rgba(8,11,15,166)`) |
| `composer.base` | black, higher-opacity than card (`rgba(0,0,0,214)`) |
| `accent.primary.base` | muted neutral blue (`rgba(86,124,156,230)`) |
| `text.primary` | light cool white (`alpha 236+`) |
| `text.secondary` | muted cool gray-blue (`alpha ~190`) |
| `secondary.button.base` | opaque desaturated blue-gray (`rgba(62,83,103,222)`) |
| `selection.stroke` | bright green accent (selector) |

### Motion Tokens

| Token | Target |
| --- | --- |
| `overlay.show.duration` | `160-190ms` |
| `overlay.refresh.duration` | `120-150ms` |
| `overlay.hide.duration` | `110-140ms` |
| `easing` | `OutCubic` |
| `escape.hide` | immediate |

## 4) Composition Policy

Overlay materials are QSS-authored only for this UI baseline. Runtime blur injection is not called from `overlay.py`.

### Rules

- Keep card/composer legibility by tuning QSS alpha values, not native acrylic composition.
- Keep `window_effects.py` available for diagnostics and controlled experiments only.
- Any future blur reintroduction must pass warning-noise gates and preserve focus/placement behavior.

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
  - prompt/message text >= `13px`
  - input text >= `12px`
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
