from __future__ import annotations

import ctypes
import os
import platform
from ctypes import wintypes

from PyQt6.QtWidgets import QWidget


def apply_blur_behind_for_widget(widget: QWidget, blur_strength: int = 12) -> bool:
    if platform.system().lower() != "windows":
        return False
    if not widget.isVisible():
        return False
    if widget.width() <= 1 or widget.height() <= 1:
        return False
    try:
        hwnd = int(widget.winId())
    except Exception:
        return False
    if hwnd <= 0:
        return False

    mode = (os.getenv("SENTINEL_OVERLAY_BLUR_MODE") or "dwm_first").strip().lower()
    if mode in {"off", "none", "0"}:
        return False
    if mode == "dwm_only":
        return _try_dwm_blur(hwnd)
    if mode == "acrylic_only":
        return _try_set_window_acrylic(hwnd, blur_strength)
    if mode == "acrylic_first":
        return _try_set_window_acrylic(hwnd, blur_strength) or _try_dwm_blur(hwnd)

    # Default: prefer DWM blur to preserve QSS-authored glass colors.
    return _try_dwm_blur(hwnd) or _try_set_window_acrylic(hwnd, blur_strength)


def _try_set_window_acrylic(hwnd: int, blur_strength: int) -> bool:
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception:
        return False
    set_comp_attr = getattr(user32, "SetWindowCompositionAttribute", None)
    if set_comp_attr is None:
        return False

    class AccentPolicy(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_uint32),
            ("AnimationId", ctypes.c_int),
        ]

    class WindowCompositionAttribData(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.c_void_p),
            ("SizeOfData", ctypes.c_size_t),
        ]

    # WCA_ACCENT_POLICY and ACCENT_ENABLE_ACRYLICBLURBEHIND.
    wca_accent_policy = 19
    accent_enable_acrylic = 4

    # Keep acrylic tint light so stylesheet glass layers remain visible.
    alpha = max(26, min(84, 24 + int(blur_strength * 2)))
    # ABGR color format expected by AccentPolicy.GradientColor.
    tint_red = 28
    tint_green = 38
    tint_blue = 52
    gradient_color = (alpha << 24) | (tint_blue << 16) | (tint_green << 8) | tint_red

    accent = AccentPolicy()
    accent.AccentState = accent_enable_acrylic
    accent.AccentFlags = 0
    accent.GradientColor = gradient_color
    accent.AnimationId = 0

    data = WindowCompositionAttribData()
    data.Attribute = wca_accent_policy
    data.Data = ctypes.cast(ctypes.byref(accent), ctypes.c_void_p)
    data.SizeOfData = ctypes.sizeof(accent)

    try:
        set_comp_attr.argtypes = [wintypes.HWND, ctypes.POINTER(WindowCompositionAttribData)]
        set_comp_attr.restype = wintypes.BOOL
        result = set_comp_attr(wintypes.HWND(hwnd), ctypes.byref(data))
    except Exception:
        return False
    return bool(result)


def _try_dwm_blur(hwnd: int) -> bool:
    class DwmBlurBehind(ctypes.Structure):
        _fields_ = [
            ("dwFlags", ctypes.c_uint),
            ("fEnable", wintypes.BOOL),
            ("hRgnBlur", wintypes.HRGN),
            ("fTransitionOnMaximized", wintypes.BOOL),
        ]

    try:
        dwmapi = getattr(ctypes.windll, "dwmapi", None)  # type: ignore[attr-defined]
    except Exception:
        return False
    if dwmapi is None:
        return False
    is_composition_enabled = getattr(dwmapi, "DwmIsCompositionEnabled", None)
    if is_composition_enabled is not None:
        enabled = wintypes.BOOL()
        try:
            status = is_composition_enabled(ctypes.byref(enabled))
        except Exception:
            return False
        if int(status) != 0 or not bool(enabled.value):
            return False
    enable_blur_flag = 0x00000001
    blur = DwmBlurBehind()
    blur.dwFlags = enable_blur_flag
    blur.fEnable = True
    blur.hRgnBlur = None
    blur.fTransitionOnMaximized = False
    try:
        status = dwmapi.DwmEnableBlurBehindWindow(wintypes.HWND(hwnd), ctypes.byref(blur))
    except Exception:
        return False
    return int(status) == 0
