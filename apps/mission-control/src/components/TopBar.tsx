import { format } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "../api";

const SEMESTER_WEEK = import.meta.env.VITE_SEMESTER_WEEK ?? "8";
const HEALTH_CHECK_INTERVAL_MS = 30_000;

export function TopBar({
  onExportReport,
  onUploadDocs,
}: {
  onExportReport?: () => void;
  onUploadDocs?: () => void;
}) {
  const [sentinelActive, setSentinelActive] = useState(true);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/healthz`);
      setSentinelActive(res.ok);
    } catch {
      setSentinelActive(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, HEALTH_CHECK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [checkHealth]);

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
        <span className={`sentinel-pill ${sentinelActive ? "active" : ""}`} aria-live="polite">
          <span className="pulse-dot" aria-hidden />
          {sentinelActive ? "Sentinel Active" : "Sentinel Offline"}
        </span>
        <button type="button" className="top-bar-btn" onClick={() => onExportReport?.()}>
          Export Report
        </button>
        <button type="button" className="top-bar-btn primary" onClick={() => onUploadDocs?.()}>
          + Upload Docs
        </button>
      </div>
    </header>
  );
}
