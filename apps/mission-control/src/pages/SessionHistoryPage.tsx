import { useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { API_BASE } from "../api";
import { useBrainState } from "../context/BrainStateContext";
import { useCourse } from "../context/CourseContext";
import type { MockSession } from "../data/courses";

type DateRange = "today" | "week" | "month" | "all";

type SessionWithCourse = {
  id: string;
  timestamp_utc: string;
  summary: string;
  topic: string;
  gap_ids: string[];
  capture_id: string | null;
  thumbnail_url?: string;
  course_id: string;
  course_name?: string;
  thread_id?: string;
  turn_index?: number;
  source: "live" | "fallback";
};

function formatCourseLabel(courseId: string): string {
  if (courseId === "all") {
    return "ALL";
  }
  return courseId.toUpperCase();
}

function mapFallbackSession(session: MockSession, courseId: string, courseName?: string): SessionWithCourse {
  return {
    id: session.id,
    timestamp_utc: session.timestamp_utc,
    summary: session.summary,
    topic: session.topic,
    gap_ids: session.gap_id ? [session.gap_id] : [],
    capture_id: null,
    thumbnail_url: session.thumbnail_url,
    course_id: courseId,
    course_name: courseName,
    source: "fallback",
  };
}

export function SessionHistoryPage() {
  const { state } = useBrainState();
  const { courseId, courseData, allCoursesSummary, courses, liveAvailable, liveError } = useCourse();
  const [dateRange, setDateRange] = useState<DateRange>("all");
  const [topicFilter, setTopicFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const courseNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const course of courses) {
      if (course.id === "all") {
        continue;
      }
      map.set(course.id, course.name);
    }
    for (const row of state.courses) {
      if (row.course_id === "all") {
        continue;
      }
      if (!map.has(row.course_id)) {
        map.set(row.course_id, row.course_name);
      }
    }
    return map;
  }, [courses, state.courses]);

  const liveCaptureSessions = useMemo<SessionWithCourse[]>(
    () =>
      state.sessions
        .filter((session) => Boolean(session.capture_id))
        .filter((session) => courseId === "all" || session.course_id === courseId)
        .sort((a, b) => new Date(b.timestamp_utc).getTime() - new Date(a.timestamp_utc).getTime())
        .map((session) => ({
          id: session.session_id,
          timestamp_utc: session.timestamp_utc,
          summary: session.summary,
          topic: session.topic,
          gap_ids: session.gap_ids,
          capture_id: session.capture_id ?? null,
          thumbnail_url: session.capture_id ? `${API_BASE}/captures/${encodeURIComponent(session.capture_id)}.png` : undefined,
          course_id: session.course_id,
          course_name: courseNameById.get(session.course_id),
          thread_id: session.thread_id,
          turn_index: session.turn_index,
          source: "live",
        })),
    [state.sessions, courseId, courseNameById]
  );

  const fallbackSessions = useMemo<SessionWithCourse[]>(() => {
    if (courseId === "all") {
      return allCoursesSummary
        .flatMap(({ data }) =>
          data.sessions.map((session) => mapFallbackSession(session, data.id, data.name))
        )
        .sort((a, b) => new Date(b.timestamp_utc).getTime() - new Date(a.timestamp_utc).getTime());
    }
    return (courseData?.sessions ?? []).map((session) =>
      mapFallbackSession(session, courseId, courseData?.name)
    );
  }, [allCoursesSummary, courseData, courseId]);

  const sessions = liveCaptureSessions.length > 0 || liveAvailable ? liveCaptureSessions : fallbackSessions;

  const filtered = useMemo(() => {
    let list = [...sessions];
    const now = new Date();
    if (dateRange === "today") {
      list = list.filter((session) => new Date(session.timestamp_utc).toDateString() === now.toDateString());
    } else if (dateRange === "week") {
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      list = list.filter((session) => new Date(session.timestamp_utc) >= weekAgo);
    } else if (dateRange === "month") {
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      list = list.filter((session) => new Date(session.timestamp_utc) >= monthAgo);
    }
    if (topicFilter) {
      list = list.filter((session) => session.topic.toLowerCase().includes(topicFilter.toLowerCase()));
    }
    if (search) {
      list = list.filter(
        (session) =>
          session.summary.toLowerCase().includes(search.toLowerCase()) ||
          session.topic.toLowerCase().includes(search.toLowerCase())
      );
    }
    return list;
  }, [sessions, dateRange, topicFilter, search]);

  const topics = useMemo(() => {
    const set = new Set(sessions.map((session) => session.topic));
    return Array.from(set).sort();
  }, [sessions]);

  const courseBadge = courseId === "all" ? "All" : formatCourseLabel(courseId);

  if (!courseData && courseId !== "all") {
    return (
      <div className="page-shell page-fade">
        <h1>Session History</h1>
        <p className="status-line">Select a course.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-fade">
      <header className="history-page-header">
        <div className="history-page-title-row">
          <h1>Session History</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <span className="pill pill-sessions-count">{sessions.length} sessions</span>
        </div>
      </header>
      {!liveAvailable && (
        <p className="status-line">{liveError ?? "Live state unavailable. Showing fallback sessions."}</p>
      )}
      <div className="history-page-controls">
        <div className="history-filters">
          <span className="history-filter-label">Date:</span>
          {(["today", "week", "month", "all"] as const).map((range) => (
            <button
              key={range}
              type="button"
              className={`history-filter-btn ${dateRange === range ? "active" : ""}`}
              onClick={() => setDateRange(range)}
            >
              {range === "today" ? "Today" : range === "week" ? "This Week" : range === "month" ? "This Month" : "All"}
            </button>
          ))}
        </div>
        <select
          className="history-topic-select"
          value={topicFilter}
          onChange={(event) => setTopicFilter(event.target.value)}
          aria-label="Filter by topic"
        >
          <option value="">All topics</option>
          {topics.map((topic) => (
            <option key={topic} value={topic}>{topic}</option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Search..."
          className="history-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <ul className="history-list">
        {filtered.length === 0 ? (
          <li className="status-line">No sessions match your filters.</li>
        ) : (
          filtered.map((session) => (
            <li key={session.id} className="history-card">
              <button
                type="button"
                className="history-card-main"
                onClick={() => setExpandedId(expandedId === session.id ? null : session.id)}
              >
                <div className="history-thumb">
                  {session.thumbnail_url ? (
                    <img src={session.thumbnail_url} alt="" />
                  ) : (
                    <div className="history-thumb-placeholder">IMG</div>
                  )}
                </div>
                <div className="history-card-body">
                  <time className="history-time" dateTime={session.timestamp_utc}>
                    {formatDistanceToNow(new Date(session.timestamp_utc), { addSuffix: true })}
                  </time>
                  <p className="history-summary">{session.summary}</p>
                  <span className="history-topic-tag">{session.topic}</span>
                  {courseId === "all" && (
                    <span className="history-course-tag">{session.course_name || formatCourseLabel(session.course_id)}</span>
                  )}
                  {session.gap_ids.length > 0 && <span className="pill pill-gap-created">Gap Linked</span>}
                </div>
              </button>
              {expandedId === session.id && (
                <div className="history-expanded">
                  <p className="history-expanded-label">Session metadata</p>
                  <p className="history-expanded-text">Course: {session.course_name || formatCourseLabel(session.course_id)}</p>
                  {session.thread_id && (
                    <p className="history-expanded-text">Thread: {session.thread_id}</p>
                  )}
                  {typeof session.turn_index === "number" && (
                    <p className="history-expanded-text">Turn index: {session.turn_index}</p>
                  )}
                  {session.capture_id && (
                    <p className="history-expanded-text">
                      Capture ID: {session.capture_id}
                    </p>
                  )}
                  {session.capture_id && session.thumbnail_url && (
                    <p className="history-expanded-text">
                      <a href={session.thumbnail_url} target="_blank" rel="noreferrer">
                        Open capture evidence
                      </a>
                    </p>
                  )}
                  {session.gap_ids.length > 0 && (
                    <p className="history-expanded-text">Linked gaps: {session.gap_ids.join(", ")}</p>
                  )}
                  {session.source === "fallback" && (
                    <p className="history-expanded-text">Displayed from fallback data because live bridge state is unavailable.</p>
                  )}
                </div>
              )}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
