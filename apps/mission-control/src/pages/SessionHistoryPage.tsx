import { useState, useMemo } from "react";
import { useCourse } from "../context/CourseContext";
import { formatDistanceToNow } from "date-fns";
import type { MockSession } from "../data/courses";

type DateRange = "today" | "week" | "month" | "all";
type SessionWithCourse = MockSession & { courseName?: string; courseId?: string };

export function SessionHistoryPage() {
  const { courseId, courseData, allCoursesSummary } = useCourse();
  const [dateRange, setDateRange] = useState<DateRange>("all");
  const [topicFilter, setTopicFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const sessions: SessionWithCourse[] = courseId === "all"
    ? allCoursesSummary.flatMap(({ data }) =>
        data.sessions.map((s) => ({ ...s, courseName: data.name, courseId: data.id }))
      ).sort((a, b) => new Date(b.timestamp_utc).getTime() - new Date(a.timestamp_utc).getTime())
    : courseData?.sessions ?? [];

  const filtered = useMemo(() => {
    let list = [...sessions];
    const now = new Date();
    if (dateRange === "today") {
      list = list.filter((s) => new Date(s.timestamp_utc).toDateString() === now.toDateString());
    } else if (dateRange === "week") {
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      list = list.filter((s) => new Date(s.timestamp_utc) >= weekAgo);
    } else if (dateRange === "month") {
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      list = list.filter((s) => new Date(s.timestamp_utc) >= monthAgo);
    }
    if (topicFilter) list = list.filter((s) => s.topic.toLowerCase().includes(topicFilter.toLowerCase()));
    if (search) list = list.filter((s) => s.summary.toLowerCase().includes(search.toLowerCase()) || s.topic.toLowerCase().includes(search.toLowerCase()));
    return list;
  }, [sessions, dateRange, topicFilter, search]);

  const topics = useMemo(() => {
    const set = new Set(sessions.map((s) => s.topic));
    return Array.from(set).sort();
  }, [sessions]);

  const courseBadge = courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

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
      <div className="history-page-controls">
        <div className="history-filters">
          <span className="history-filter-label">Date:</span>
          {(["today", "week", "month", "all"] as const).map((r) => (
            <button
              key={r}
              type="button"
              className={`history-filter-btn ${dateRange === r ? "active" : ""}`}
              onClick={() => setDateRange(r)}
            >
              {r === "today" ? "Today" : r === "week" ? "This Week" : r === "month" ? "This Month" : "All"}
            </button>
          ))}
        </div>
        <select
          className="history-topic-select"
          value={topicFilter}
          onChange={(e) => setTopicFilter(e.target.value)}
          aria-label="Filter by topic"
        >
          <option value="">All topics</option>
          {topics.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Search…"
          className="history-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
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
                    <div className="history-thumb-placeholder">📷</div>
                  )}
                </div>
                <div className="history-card-body">
                  <time className="history-time" dateTime={session.timestamp_utc}>
                    {formatDistanceToNow(new Date(session.timestamp_utc), { addSuffix: true })}
                  </time>
                  <p className="history-summary">{session.summary}</p>
                  <span className="history-topic-tag">{session.topic}</span>
                  {"courseName" in session && session.courseName && <span className="history-course-tag">{session.courseName}</span>}
                  {session.gap_id && <span className="pill pill-gap-created">Gap Created</span>}
                </div>
              </button>
              {expandedId === session.id && (
                <div className="history-expanded">
                  <p className="history-expanded-label">Capture & dialogue</p>
                  <p className="history-expanded-text">Full capture and Socratic dialogue would appear here. (Placeholder.)</p>
                  {session.gap_id && <p className="history-expanded-text">Linked gap: {session.gap_id}</p>}
                </div>
              )}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
