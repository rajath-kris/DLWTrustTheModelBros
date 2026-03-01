from __future__ import annotations

import ctypes
import platform
import subprocess

from .types import WindowMetadata


def _windows_foreground_window() -> WindowMetadata:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value.strip() or "Unknown Window"
    app_name = title.split(" - ")[-1] if " - " in title else "Windows App"
    return WindowMetadata(app_name=app_name, window_title=title)


def _mac_foreground_window() -> WindowMetadata:
    script = (
        "tell application \"System Events\"\n"
        "set frontApp to name of first application process whose frontmost is true\n"
        "set frontWindow to value of attribute \"AXTitle\" of front window of first application process whose frontmost is true\n"
        "return frontApp & \"|||\" & frontWindow\n"
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip()
        if "|||" in output:
            app_name, title = output.split("|||", 1)
            return WindowMetadata(app_name=app_name.strip(), window_title=title.strip() or "Untitled")
    except Exception:
        pass
    return WindowMetadata(app_name="macOS App", window_title="Unknown Window")


def get_active_window_metadata() -> WindowMetadata:
    os_name = platform.system().lower()
    if os_name == "windows":
        return _windows_foreground_window()
    if os_name == "darwin":
        return _mac_foreground_window()
    return WindowMetadata(app_name="unknown", window_title="unknown")


def platform_name() -> str:
    os_name = platform.system().lower()
    if os_name == "darwin":
        return "macos"
    return "windows"
