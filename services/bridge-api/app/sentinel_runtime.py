from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import psutil

from .config import Settings
from .models import SentinelRuntimeActionResponse, SentinelRuntimeStatus, utc_now_iso


class SentinelRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._metadata_path = settings.sentinel_runtime_metadata_file
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings.sentinel_runtime_logs_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_metadata()

    def get_status(self) -> SentinelRuntimeStatus:
        with self._lock:
            metadata = self._load_metadata()
            detected_pids = self._discover_sentinel_pids()
            if self._prune_managed_pids(metadata, detected_pids):
                self._save_metadata(metadata)
            return self._build_status(metadata, detected_pids)

    def start(self) -> SentinelRuntimeActionResponse:
        with self._lock:
            metadata = self._load_metadata()
            detected_pids = self._discover_sentinel_pids()
            self._prune_managed_pids(metadata, detected_pids)

            if detected_pids:
                metadata["last_action"] = "start"
                metadata["last_action_at"] = utc_now_iso()
                metadata["last_error"] = None
                self._save_metadata(metadata)
                return SentinelRuntimeActionResponse(
                    ok=True,
                    action="start",
                    message="Sentinel already running.",
                    status=self._build_status(metadata, detected_pids),
                )

            python_path = self._resolve_python_path()
            workdir = self._resolve_workdir()

            if not python_path.exists():
                message = f"Sentinel runtime python not found: {python_path}"
                metadata["last_action"] = "start"
                metadata["last_action_at"] = utc_now_iso()
                metadata["last_error"] = message
                self._save_metadata(metadata)
                raise RuntimeError(message)
            if not workdir.exists():
                message = f"Sentinel runtime workdir not found: {workdir}"
                metadata["last_action"] = "start"
                metadata["last_action_at"] = utc_now_iso()
                metadata["last_error"] = message
                self._save_metadata(metadata)
                raise RuntimeError(message)

            timestamp = utc_now_iso().replace(":", "").replace("-", "")
            log_path = self._settings.sentinel_runtime_logs_dir / f"sentinel-{timestamp}.log"
            creationflags = 0
            if os.name == "nt":
                creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
                creationflags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
                creationflags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
            bridge_url = f"http://{self._settings.bridge_host}:{self._settings.bridge_port}"
            launch_env = os.environ.copy()
            launch_env["SENTINEL_BRIDGE_URL"] = bridge_url
            launch_env["BRIDGE_HOST"] = self._settings.bridge_host
            launch_env["BRIDGE_PORT"] = str(self._settings.bridge_port)

            with log_path.open("a", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    [str(python_path), "-m", "sentinel.main"],
                    cwd=str(workdir),
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=log_handle,
                    env=launch_env,
                    creationflags=creationflags,
                    close_fds=True,
                )

            time.sleep(0.7)
            detected_after = self._discover_sentinel_pids()
            managed = set(self._coerce_pid_list(metadata.get("managed_pids")))
            managed.add(int(process.pid))
            metadata["managed_pids"] = sorted(pid for pid in managed if pid in detected_after)
            metadata["last_action"] = "start"
            metadata["last_action_at"] = utc_now_iso()
            metadata["last_error"] = None
            self._save_metadata(metadata)

            status = self._build_status(metadata, detected_after)
            if not status.running:
                message = "Sentinel process did not appear after launch. Check artifacts/sentinel-runtime logs."
                metadata["last_error"] = message
                self._save_metadata(metadata)
                raise RuntimeError(message)

            return SentinelRuntimeActionResponse(
                ok=True,
                action="start",
                message="Sentinel started.",
                status=status,
            )

    def stop(self) -> SentinelRuntimeActionResponse:
        with self._lock:
            metadata = self._load_metadata()
            detected_pids = self._discover_sentinel_pids()
            self._prune_managed_pids(metadata, detected_pids)

            if not detected_pids:
                metadata["managed_pids"] = []
                metadata["last_action"] = "stop"
                metadata["last_action_at"] = utc_now_iso()
                metadata["last_error"] = None
                self._save_metadata(metadata)
                return SentinelRuntimeActionResponse(
                    ok=True,
                    action="stop",
                    message="Sentinel is not running.",
                    stopped_count=0,
                    failed_count=0,
                    status=self._build_status(metadata, []),
                )

            processes: list[psutil.Process] = []
            stopped_count = 0
            failed_pids: list[int] = []
            for pid in detected_pids:
                try:
                    processes.append(psutil.Process(pid))
                except psutil.NoSuchProcess:
                    stopped_count += 1
                except psutil.Error:
                    failed_pids.append(pid)

            for process in processes:
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    stopped_count += 1
                except psutil.Error:
                    failed_pids.append(int(process.pid))

            timeout_seconds = max(0.2, float(self._settings.sentinel_runtime_stop_timeout_seconds))
            gone, alive = psutil.wait_procs(processes, timeout=timeout_seconds)
            stopped_count += len(gone)

            if alive:
                for process in alive:
                    try:
                        process.kill()
                    except psutil.NoSuchProcess:
                        stopped_count += 1
                    except psutil.Error:
                        failed_pids.append(int(process.pid))

                gone_after_kill, alive_after_kill = psutil.wait_procs(alive, timeout=1.0)
                stopped_count += len(gone_after_kill)
                for process in alive_after_kill:
                    failed_pids.append(int(process.pid))

            failed_unique = sorted(set(failed_pids))
            detected_after = self._discover_sentinel_pids()
            metadata["managed_pids"] = [
                pid for pid in self._coerce_pid_list(metadata.get("managed_pids")) if pid in detected_after
            ]
            metadata["last_action"] = "stop"
            metadata["last_action_at"] = utc_now_iso()
            if failed_unique:
                metadata["last_error"] = f"Failed to stop Sentinel PIDs: {failed_unique}"
            else:
                metadata["last_error"] = None
            self._save_metadata(metadata)

            status = self._build_status(metadata, detected_after)
            failed_count = len(failed_unique)
            ok = failed_count == 0
            if ok:
                message = "Sentinel stopped."
            else:
                message = "Sentinel stop completed with partial failures."

            return SentinelRuntimeActionResponse(
                ok=ok,
                action="stop",
                message=message,
                stopped_count=stopped_count,
                failed_count=failed_count,
                status=status,
            )

    def _ensure_metadata(self) -> None:
        if self._metadata_path.exists():
            return
        self._save_metadata(self._default_metadata())

    def _default_metadata(self) -> dict[str, Any]:
        return {
            "managed_pids": [],
            "last_action": "none",
            "last_action_at": None,
            "last_error": None,
        }

    def _load_metadata(self) -> dict[str, Any]:
        if not self._metadata_path.exists():
            return self._default_metadata()
        try:
            payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_metadata()

        metadata = self._default_metadata()
        metadata["managed_pids"] = self._coerce_pid_list(payload.get("managed_pids"))
        action = str(payload.get("last_action", "none")).strip().lower()
        metadata["last_action"] = action if action in {"none", "start", "stop"} else "none"
        metadata["last_action_at"] = payload.get("last_action_at")
        metadata["last_error"] = payload.get("last_error")
        return metadata

    def _save_metadata(self, metadata: dict[str, Any]) -> None:
        payload = {
            "managed_pids": self._coerce_pid_list(metadata.get("managed_pids")),
            "last_action": metadata.get("last_action", "none"),
            "last_action_at": metadata.get("last_action_at"),
            "last_error": metadata.get("last_error"),
        }
        tmp_path = self._metadata_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._metadata_path)

    def _resolve_python_path(self) -> Path:
        configured = (self._settings.sentinel_runtime_python or "").strip()
        if configured:
            candidate = Path(configured).expanduser()
        else:
            candidate = self._settings.sentinel_runtime_default_python

        # Prefer pythonw on Windows so Sentinel launches without a console window.
        if os.name == "nt" and candidate.name.lower() == "python.exe":
            pythonw = candidate.with_name("pythonw.exe")
            if pythonw.exists():
                return pythonw
        return candidate

    def _resolve_workdir(self) -> Path:
        configured = (self._settings.sentinel_runtime_workdir or "").strip()
        if configured:
            return Path(configured).expanduser()
        return self._settings.sentinel_runtime_default_workdir

    def _build_status(self, metadata: dict[str, Any], detected_pids: list[int]) -> SentinelRuntimeStatus:
        managed_alive = [pid for pid in self._coerce_pid_list(metadata.get("managed_pids")) if pid in detected_pids]
        return SentinelRuntimeStatus(
            running=bool(detected_pids),
            process_count=len(detected_pids),
            detected_pids=detected_pids,
            managed_pids=managed_alive,
            last_action=str(metadata.get("last_action", "none")),
            last_action_at=metadata.get("last_action_at"),
            last_error=metadata.get("last_error"),
        )

    def _prune_managed_pids(self, metadata: dict[str, Any], detected_pids: list[int]) -> bool:
        previous = self._coerce_pid_list(metadata.get("managed_pids"))
        pruned = [pid for pid in previous if pid in detected_pids]
        if pruned == previous:
            return False
        metadata["managed_pids"] = pruned
        return True

    def _discover_sentinel_pids(self) -> list[int]:
        detected: set[int] = set()
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pid = int(process.info.get("pid") or 0)
                if pid <= 0:
                    continue
                process_name = str(process.info.get("name") or "").strip().lower()
                is_python_like = process_name in {"python.exe", "pythonw.exe", "py.exe", "python", "py"}
                cmdline_parts = process.info.get("cmdline") or []
                cmdline = " ".join(str(part) for part in cmdline_parts).lower()
                normalized_cmdline = cmdline.replace("\\", "/")
                if (
                    "sentinel.main" in normalized_cmdline
                    or "-m sentinel.main" in normalized_cmdline
                    or (is_python_like and "apps/sentinel-desktop" in normalized_cmdline)
                ):
                    detected.add(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
        return sorted(detected)

    @staticmethod
    def _coerce_pid_list(raw_value: Any) -> list[int]:
        if not isinstance(raw_value, list):
            return []
        pids: list[int] = []
        for item in raw_value:
            try:
                pid = int(item)
            except (TypeError, ValueError):
                continue
            if pid > 0 and pid not in pids:
                pids.append(pid)
        pids.sort()
        return pids
