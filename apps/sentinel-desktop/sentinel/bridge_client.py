from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import uuid4

import requests

from .types import CaptureRegion, MonitorSnapshot, WindowMetadata


class BridgeClient:
    def __init__(self, base_url: str, timeout_seconds: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def submit_capture(
        self,
        platform_name: str,
        window: WindowMetadata,
        monitor: MonitorSnapshot,
        region: CaptureRegion,
        image_bytes: bytes,
    ) -> dict:
        payload = {
            "capture_id": str(uuid4()),
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "platform": platform_name,
            "app_name": window.app_name,
            "window_title": window.window_title,
            "monitor": {
                "left": monitor.left,
                "top": monitor.top,
                "width": monitor.width,
                "height": monitor.height,
                "scale": monitor.scale,
            },
            "region": {
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
            },
            "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        }

        response = requests.post(
            f"{self.base_url}/api/v1/captures",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
