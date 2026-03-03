import { format } from "date-fns";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  API_BASE,
  fetchSentinelRuntimeStatus,
  fetchTopicsForCourse,
  startSentinelRuntime,
  stopSentinelRuntime,
} from "../api";
import { useCourse } from "../context/CourseContext";
import type { SentinelRuntimeStatus, TopicSummary } from "../types";
import { SentinelActivationModal } from "./SentinelActivationModal";

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

export function TopBar() {
  const navigate = useNavigate();
  const { courses, courseId } = useCourse();
  const selectableCourses = useMemo(
    () => courses.filter((course) => course.id !== "all"),
    [courses]
  );

  const [runtimeStatus, setRuntimeStatus] = useState<SentinelRuntimeStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [mutating, setMutating] = useState<RuntimeMutation>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [bridgeOffline, setBridgeOffline] = useState(false);
  const runtimeRunningRef = useRef(false);

  const [activationModalOpen, setActivationModalOpen] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);

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

  const openActivationModal = useCallback(() => {
    setActivationError(null);
    setTopics([]);
    setSelectedTopicId("");
    const preferredCourseId =
      (courseId !== "all" && selectableCourses.some((course) => course.id === courseId) ? courseId : "") ||
      selectableCourses[0]?.id ||
      "";
    setSelectedCourseId(preferredCourseId);
    setActivationModalOpen(true);
  }, [courseId, selectableCourses]);

  const handleSentinelToggle = useCallback(async () => {
    if (!runtimeStatus || mutating !== null || activating) {
      return;
    }

    setRuntimeError(null);
    setBridgeOffline(false);
    const running = runtimeStatus.running;

    if (!running) {
      openActivationModal();
      return;
    }

    setMutating("stopping");
    try {
      const actionResponse = await stopSentinelRuntime();
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
  }, [activating, mutating, openActivationModal, refreshRuntimeStatus, runtimeStatus]);

  const handleActivate = useCallback(async () => {
    const courseSelection = selectedCourseId.trim();
    const topicSelection = selectedTopicId.trim();
    if (!courseSelection || !topicSelection) {
      return;
    }

    setActivating(true);
    setActivationError(null);
    setRuntimeError(null);
    try {
      const actionResponse = await startSentinelRuntime(courseSelection, topicSelection);
      setRuntimeStatus(actionResponse.status);
      if (!actionResponse.ok || actionResponse.status.last_error) {
        const message = actionResponse.status.last_error || actionResponse.message || "Runtime activation completed with warnings.";
        setActivationError(message);
        setRuntimeError(message);
      } else {
        setActivationModalOpen(false);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Runtime activation failed.";
      setActivationError(message);
      setRuntimeError(message);
      if (error instanceof TypeError) {
        setBridgeOffline(true);
        setRuntimeStatus(null);
      }
    } finally {
      setActivating(false);
      await refreshRuntimeStatus();
    }
  }, [refreshRuntimeStatus, selectedCourseId, selectedTopicId]);

  useEffect(() => {
    if (!activationModalOpen) {
      return;
    }
    if (!selectedCourseId) {
      setTopics([]);
      setSelectedTopicId("");
      return;
    }
    let active = true;
    setLoadingTopics(true);
    setActivationError(null);
    void fetchTopicsForCourse(selectedCourseId)
      .then((response) => {
        if (!active) {
          return;
        }
        setTopics(response.topics);
        setSelectedTopicId((current) =>
          (current && response.topics.some((topic) => topic.topic_id === current)
            ? current
            : "") ||
          response.active_topic_id ||
          response.topics[0]?.topic_id ||
          ""
        );
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setTopics([]);
        setSelectedTopicId("");
        setActivationError(error instanceof Error ? error.message : "Could not load topics for selected course.");
      })
      .finally(() => {
        if (active) {
          setLoadingTopics(false);
        }
      });
    return () => {
      active = false;
    };
  }, [activationModalOpen, selectedCourseId]);

  useEffect(() => {
    refreshRuntimeStatus();
    const id = setInterval(refreshRuntimeStatus, RUNTIME_STATUS_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refreshRuntimeStatus]);

  useEffect(() => {
    runtimeRunningRef.current = runtimeStatus?.running ?? false;
  }, [runtimeStatus]);

  useEffect(() => {
    if (runtimeStatus?.running) {
      setActivationModalOpen(false);
    }
  }, [runtimeStatus?.running]);

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
    loadingStatus || mutating !== null || bridgeOffline || runtimeStatus === null || activating;
  const runtimeButtonLabel =
    mutating === "stopping"
      ? "Deactivating Sentinel..."
      : bridgeOffline
        ? "Bridge Offline"
        : runtimeStatus === null
          ? "Runtime Unavailable"
          : isRuntimeRunning
            ? "Sentinel Active (Deactivate)"
            : "Activate Sentinel";

  return (
    <>
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
          {runtimeError && !bridgeOffline && (
            <span className="top-bar-runtime-error" role="status">
              {runtimeError}
            </span>
          )}
        </div>
      </header>

      <SentinelActivationModal
        open={activationModalOpen}
        courses={selectableCourses.map((course) => ({ id: course.id, name: course.name }))}
        selectedCourseId={selectedCourseId}
        selectedTopicId={selectedTopicId}
        topics={topics}
        loadingTopics={loadingTopics}
        activating={activating}
        error={activationError}
        onClose={() => {
          if (!activating) {
            setActivationModalOpen(false);
          }
        }}
        onSelectCourse={(nextCourseId) => {
          setSelectedCourseId(nextCourseId);
          setSelectedTopicId("");
        }}
        onSelectTopic={setSelectedTopicId}
        onActivate={() => void handleActivate()}
        onOpenDocumentHub={() => {
          setActivationModalOpen(false);
          navigate("/documents");
        }}
      />
    </>
  );
}
