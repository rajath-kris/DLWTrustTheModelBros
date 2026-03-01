from __future__ import annotations

from pathlib import Path
from typing import Final

from PyQt6.QtGui import QFontDatabase

DEFAULT_FADE_IN_MS: Final[int] = 220
DEFAULT_FADE_TEXT_STAGGER_MS: Final[int] = 60

_DEFAULT_UI_FONT: Final[str] = "Segoe UI"
_FALLBACK_FONTS: Final[list[str]] = ["Segoe UI Variable Text", "Segoe UI", "Inter", "sans-serif"]
_ACTOR_FONT_FILE: Final[str] = "Actor-Regular.ttf"

_ui_font_family = _DEFAULT_UI_FONT
_font_load_attempted = False


def _font_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "fonts" / _ACTOR_FONT_FILE


def load_actor_font(use_actor_font: bool = True) -> str:
    global _font_load_attempted
    global _ui_font_family

    if _font_load_attempted:
        return _ui_font_family

    _font_load_attempted = True
    if not use_actor_font:
        _ui_font_family = _DEFAULT_UI_FONT
        return _ui_font_family

    font_path = _font_path()
    if not font_path.exists():
        _ui_font_family = _DEFAULT_UI_FONT
        return _ui_font_family

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        _ui_font_family = _DEFAULT_UI_FONT
        return _ui_font_family

    families = QFontDatabase.applicationFontFamilies(font_id)
    _ui_font_family = families[0] if families else "Actor"
    return _ui_font_family


def get_ui_font_family() -> str:
    return _ui_font_family


def qss_font_family_stack(primary_font: str | None = None) -> str:
    family = (primary_font or _ui_font_family).strip() or _DEFAULT_UI_FONT
    ordered: list[str] = []
    for item in [family, *_FALLBACK_FONTS]:
        if item not in ordered:
            ordered.append(item)
    quoted = [item if item == "sans-serif" else f'"{item}"' for item in ordered]
    return ", ".join(quoted)
