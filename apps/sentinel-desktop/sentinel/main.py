from __future__ import annotations

import sys
import threading
import traceback

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from .bridge_client import BridgeClient
from .capture import capture_region
from .config import settings
from .hotkey import HotkeyManager
from .overlay import OverlayBubble
from .platform import get_active_window_metadata, platform_name
from .region_selector import select_region
from .types import CaptureRegion


class SentinelController(QObject):
    capture_requested = pyqtSignal()
    escape_requested = pyqtSignal()
    analysis_ready = pyqtSignal(str, object)

    def __init__(self, overlay: OverlayBubble, bridge: BridgeClient) -> None:
        super().__init__()
        self.overlay = overlay
        self.bridge = bridge
        self._last_region: CaptureRegion | None = None

        self.capture_requested.connect(self._on_capture_requested)
        self.escape_requested.connect(self.overlay.hide_prompt)
        self.analysis_ready.connect(self._on_analysis_ready)

    def trigger_capture(self) -> None:
        self.capture_requested.emit()

    def trigger_escape(self) -> None:
        self.escape_requested.emit()

    def _on_capture_requested(self) -> None:
        region = select_region()
        if region is None:
            return

        self._last_region = region
        self.overlay.show_prompt("Analyzing capture...", region, ttl_ms=12000)

        try:
            image_bytes, monitor = capture_region(region)
            window = get_active_window_metadata()
            platform = platform_name()
        except Exception:
            self.overlay.show_prompt("Capture failed. Try selecting a smaller region.", region)
            traceback.print_exc()
            return

        def worker() -> None:
            try:
                result = self.bridge.submit_capture(platform, window, monitor, region, image_bytes)
                prompt = result.get("socratic_prompt", "What concept feels least clear in this capture?")
                self.analysis_ready.emit(prompt, region)
            except Exception:
                self.analysis_ready.emit("Bridge request failed. Check FastAPI on port 8000.", region)
                traceback.print_exc()

        threading.Thread(target=worker, daemon=True).start()

    def _on_analysis_ready(self, prompt: str, region: CaptureRegion) -> None:
        self.overlay.show_prompt(prompt, region)


def main() -> None:
    app = QApplication(sys.argv)

    overlay = OverlayBubble()
    bridge = BridgeClient(settings.bridge_url)
    controller = SentinelController(overlay, bridge)

    hotkeys = HotkeyManager(settings.capture_hotkey, settings.escape_hotkey)
    hotkeys.start(controller.trigger_capture, controller.trigger_escape)

    print("Sentinel running. Press Alt+S to capture region. Press Esc to close overlay.")
    print(f"Bridge: {settings.bridge_url}")

    try:
        app.exec()
    finally:
        hotkeys.stop()


if __name__ == "__main__":
    main()
