import { format } from "date-fns";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  API_BASE,
  fetchSentinelRuntimeStatus,
  startSentinelRuntime,
  stopSentinelRuntime,
} from "../api";
import type { SentinelRuntimeStatus } from "../types";

const SEMESTER_WEEK = import.meta.env.VITE_SEMESTER_WEEK ?? "8";
const RUNTIME_STATUS_INTERVAL_MS = 5_000;
type RuntimeMutation = "starting" | "stopping" | null;
const RUNTIME_STOP_URL = `${API_BASE}/api/v1/sentinel/runtime/stop`;

function requestRuntimeStopOnUnload(): void {
  try {
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(RUNTIME_STOP_URL, "");
      return;
    }
  } catch {
    // Fall through to fetch fallback.
  }
  void fetch(RUNTIME_STOP_URL, { method: "POST", keepalive: true }).catch(() => {
    // Best effort only during page unload.
  });
}

export function TopBar({
  onExportReport,
  onUploadDocs,
}: {
  onExportReport?: () => void;
  onUploadDocs?: () => void;
}) {
  const [runtimeStatus, setRuntimeStatus] = useState<SentinelRuntimeStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [mutating, setMutating] = useState<RuntimeMutation>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [bridgeOffline, setBridgeOffline] = useState(false);
  const runtimeRunningRef = useRef(false);

  const refreshRuntimeStatus = useCallback(async () => {
    try {
      const status = await fetchSentinelRuntimeStatus();
      setRuntimeStatus(status);
      setRuntimeError(status.last_error || null);
      setBridgeOffline(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach runtime endpoint.";
      setRuntimeError(message);
      if (error instanceof TypeError) {
        setBridgeOffline(true);
      }
      setRuntimeStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  const handleSentinelToggle = useCallback(async () => {
    if (!runtimeStatus || mutating !== null) {
      return;
    }

    setRuntimeError(null);
    setBridgeOffline(false);
    const running = runtimeStatus.running;
    setMutating(running ? "stopping" : "starting");
    try {
      const actionResponse = running ? await stopSentinelRuntime() : await startSentinelRuntime();
      setRuntimeStatus(actionResponse.status);
      if (!actionResponse.ok || actionResponse.status.last_error) {
        setRuntimeError(actionResponse.status.last_error || actionResponse.message || "Runtime action completed with warnings.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Runtime action failed.";
      setRuntimeError(message);
      if (error instanceof TypeError) {
        setBridgeOffline(true);
        setRuntimeStatus(null);
      }
    } finally {
      setMutating(null);
      await refreshRuntimeStatus();
    }
  }, [runtimeStatus, mutating, refreshRuntimeStatus]);

  useEffect(() => {
    refreshRuntimeStatus();
    const id = setInterval(refreshRuntimeStatus, RUNTIME_STATUS_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refreshRuntimeStatus]);

  useEffect(() => {
    runtimeRunningRef.current = runtimeStatus?.running ?? false;
  }, [runtimeStatus]);

  useEffect(() => {
    const onPageHide = () => {
      if (runtimeRunningRef.current) {
        requestRuntimeStopOnUnload();
      }
    };
    const onBeforeUnload = () => {
      if (runtimeRunningRef.current) {
        requestRuntimeStopOnUnload();
      }
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, []);

  const isRuntimeRunning = runtimeStatus?.running ?? false;
  const runtimeButtonDisabled =
    loadingStatus || mutating !== null || bridgeOffline || runtimeStatus === null;
  const runtimeButtonLabel =
    mutating === "starting"
      ? "Activating Sentinel..."
      : mutating === "stopping"
        ? "Deactivating Sentinel..."
        : bridgeOffline
          ? "Bridge Offline"
          : runtimeStatus === null
            ? "Runtime Unavailable"
            : isRuntimeRunning
              ? "Sentinel Active (Deactivate)"
              : "Activate Sentinel";

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <h1 className="top-bar-title">Mission Control</h1>
        <span className="top-bar-meta">
          <time dateTime={new Date().toISOString()} className="top-bar-date">
            {format(new Date(), "EEEE, d MMMM yyyy")}
          </time>
          <span className="top-bar-week">Week {SEMESTER_WEEK} of Semester</span>
        </span>
      </div>
      <div className="top-bar-right">
        <button
          type="button"
          className={`sentinel-pill ${isRuntimeRunning ? "active" : ""} ${runtimeError ? "error" : ""}`}
          aria-live="polite"
          disabled={runtimeButtonDisabled}
          onClick={() => void handleSentinelToggle()}
          title={runtimeError || undefined}
        >
          <span className="pulse-dot" aria-hidden />
          {runtimeButtonLabel}
        </button>
        <button type="button" className="top-bar-btn" onClick={() => onExportReport?.()}>
          Export Report
        </button>
        <button type="button" className="top-bar-btn primary" onClick={() => onUploadDocs?.()}>
          + Upload Docs
        </button>
        {runtimeError && !bridgeOffline && (
          <span className="top-bar-runtime-error" role="status">
            {runtimeError}
          </span>
        )}
      </div>
    </header>
  );
}
