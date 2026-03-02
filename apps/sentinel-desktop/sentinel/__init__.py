
from __future__ import annotations

import os
import platform
from pathlib import Path


def _configure_macos_qt_paths() -> None:
    if platform.system().lower() != "darwin":
        return

    package_root = Path(__file__).resolve().parent
    pyqt_root = package_root.parent / ".venv" / "lib"
    candidates = sorted(pyqt_root.glob("python*/site-packages/PyQt6/Qt6"))
    if not candidates:
        return

    qt_root = candidates[-1]
    plugins_dir = qt_root / "plugins"
    platform_plugins_dir = plugins_dir / "platforms"
    frameworks_dir = qt_root / "lib"

    if plugins_dir.is_dir() and not os.environ.get("QT_PLUGIN_PATH"):
        os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
    if platform_plugins_dir.is_dir() and not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins_dir)
    if frameworks_dir.is_dir():
        existing = [item for item in os.environ.get("DYLD_FRAMEWORK_PATH", "").split(":") if item]
        if str(frameworks_dir) not in existing:
            os.environ["DYLD_FRAMEWORK_PATH"] = ":".join([str(frameworks_dir), *existing])


_configure_macos_qt_paths()
