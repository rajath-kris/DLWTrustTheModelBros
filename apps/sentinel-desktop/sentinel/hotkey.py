from __future__ import annotations

import platform
import threading
import time
from collections.abc import Callable

import keyboard as kb
from pynput import keyboard as pynput_keyboard


class HotkeyManager:
    def __init__(self, capture_combo: str = "alt+s", escape_key: str = "esc") -> None:
        self.capture_combo = capture_combo
        self.escape_key = escape_key
        self._started = False
        self._capture_handle = None
        self._escape_handle = None
        self._listener: pynput_keyboard.Listener | None = None
        self._pressed: set[str] = set()
        self._last_trigger = 0.0
        self._lock = threading.Lock()

    def start(self, on_capture: Callable[[], None], on_escape: Callable[[], None]) -> None:
        with self._lock:
            if self._started:
                return
            if platform.system().lower() == "darwin":
                self._start_macos(on_capture, on_escape)
            else:
                self._start_windows(on_capture, on_escape)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            if platform.system().lower() == "darwin":
                if self._listener:
                    self._listener.stop()
                    self._listener = None
            else:
                if self._capture_handle is not None:
                    kb.remove_hotkey(self._capture_handle)
                if self._escape_handle is not None:
                    kb.remove_hotkey(self._escape_handle)
            self._started = False

    def _start_windows(self, on_capture: Callable[[], None], on_escape: Callable[[], None]) -> None:
        self._capture_handle = kb.add_hotkey(self.capture_combo, on_capture, suppress=False, trigger_on_release=False)
        self._escape_handle = kb.add_hotkey(self.escape_key, on_escape, suppress=False, trigger_on_release=False)

    def _start_macos(self, on_capture: Callable[[], None], on_escape: Callable[[], None]) -> None:
        def normalize(key) -> str:
            if key in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
                return "alt"
            if key == pynput_keyboard.Key.esc:
                return "esc"
            if hasattr(key, "char") and key.char:
                return key.char.lower()
            return str(key)

        def should_fire() -> bool:
            now = time.monotonic()
            if now - self._last_trigger < 0.4:
                return False
            self._last_trigger = now
            return True

        def on_press(key):
            name = normalize(key)
            self._pressed.add(name)

            if name == "esc":
                on_escape()
                return

            if "alt" in self._pressed and "s" in self._pressed and should_fire():
                on_capture()

        def on_release(key):
            self._pressed.discard(normalize(key))

        self._listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()
