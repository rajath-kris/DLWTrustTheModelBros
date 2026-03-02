import { useMemo, useState } from "react";
import { useCourse } from "../context/CourseContext";
import { useBrainState } from "../context/BrainStateContext";
import { formatRelativeTime } from "../utils/formatRelativeTime";
import type { KnowledgeGap } from "../types";

function topicLabel(concept: string): string {
  const c = concept.trim();
  if (/binary|tree|bst|avl|traversal|inorder|stack/i.test(c)) return "Binary Trees";
  if (/dynamic|memo|tabulation|dp/i.test(c)) return "Dynamic Programming";
  if (/graph|bfs|dfs|dijkstra|relaxation/i.test(c)) return "Graph Algorithms";
  if (/sort|search|quicksort|partition|pivot/i.test(c)) return "Sorting";
  if (/recur|backtrack|base case/i.test(c)) return "Recursion";
  if (/hash|map|set|collision|chain/i.test(c)) return "Hash Maps";
  if (/phasor|ac circuit|voltage/i.test(c)) return "AC Circuits";
  if (/thevenin|norton|equivalent/i.test(c)) return "Thevenin/Norton";
  if (/filter|cutoff|band/i.test(c)) return "Filters";
  return c.split(/[,.]/)[0]?.trim().slice(0, 20) || "Other";
}

function priorityLevel(gap: KnowledgeGap): "CRITICAL" | "HIGH" {
  return gap.priority_score >= 0.75 || gap.severity >= 0.75 ? "CRITICAL" : "HIGH";
}

type FilterId = "all" | "critical" | "high" | "reviewing" | "closed";
type SortId = "priority" | "recency" | "status";

export function KnowledgeGapsPage() {
  const { courseId, courseData, liveAvailable, liveError } = useCourse();
  const { setGapStatus } = useBrainState();
  const [filter, setFilter] = useState<FilterId>("all");
  const [sortBy, setSortBy] = useState<SortId>("priority");
  const [search, setSearch] = useState("");
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [pendingGapId, setPendingGapId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const gaps = courseData?.gaps ?? [];
  const captureTimestamps = courseData?.captureTimestamps ?? {};
  const activeCount = gaps.filter((g) => g.status !== "closed").length;

  const filteredAndSorted = useMemo(() => {
    let list = gaps;
    if (filter === "critical") list = list.filter((g) => priorityLevel(g) === "CRITICAL");
    else if (filter === "high") list = list.filter((g) => priorityLevel(g) === "HIGH");
    else if (filter === "reviewing") list = list.filter((g) => g.status === "reviewing");
    else if (filter === "closed") list = list.filter((g) => g.status === "closed");
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((g) => g.concept.toLowerCase().includes(q));
    if (sortBy === "priority") list = [...list].sort((a, b) => b.priority_score - a.priority_score);
    else if (sortBy === "status") list = [...list].sort((a, b) => (a.status === "closed" ? 1 : 0) - (b.status === "closed" ? 1 : 0));
    else if (sortBy === "recency") {
      list = [...list].sort((a, b) => {
        const aTs = captureTimestamps[a.capture_id] ?? "";
        const bTs = captureTimestamps[b.capture_id] ?? "";
        return new Date(bTs).getTime() - new Date(aTs).getTime();
      });
    } else {
      list = [...list].sort((a, b) => b.priority_score - a.priority_score);
    }
    return list;
  }, [gaps, filter, search, sortBy, captureTimestamps]);

  async function handleResolve(gap: KnowledgeGap) {
    setMutationError(null);
    setPendingGapId(gap.gap_id);
    try {
      await setGapStatus(gap.gap_id, "closed");
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : "Could not update gap status.");
    } finally {
      setPendingGapId(null);
    }
  }

  const selectedGap = selectedGapId ? gaps.find((g) => g.gap_id === selectedGapId) : null;

  if (courseId === "all" || !courseData) {
    return (
      <div className="page-shell page-fade">
        <h1>Knowledge Gaps</h1>
        <p className="status-line">Select a course to view knowledge gaps.</p>
      </div>
    );
  }

  const courseBadge = courseData.id === "cs2040" ? "CS2040" : courseData.id === "ee2001" ? "EE2001" : courseData.id;

  return (
    <div className="page-shell page-fade">
      <header className="gaps-page-header">
        <div className="gaps-page-title-row">
          <h1>Knowledge Gaps</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <span className="pill pill-gaps-active">{activeCount} Active</span>
        </div>
      </header>
      {!liveAvailable && <p className="status-line">{liveError ?? "Live data unavailable. Showing fallback gaps."}</p>}
      {mutationError && <p className="status-line error">{mutationError}</p>}

      <div className="gaps-page-controls">
        <div className="gaps-page-filters">
          {(["all", "critical", "high", "reviewing", "closed"] as const).map((id) => (
            <button
              key={id}
              type="button"
              className={`filter ${filter === id ? "active" : ""}`}
              onClick={() => setFilter(id)}
            >
              {id === "all" ? "All" : id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
        </div>
        <div className="gaps-page-sort">
          <span className="gaps-sort-label">Sort:</span>
          {(["priority", "recency", "status"] as const).map((id) => (
            <button
              key={id}
              type="button"
              className={`filter ${sortBy === id ? "active" : ""}`}
              onClick={() => setSortBy(id)}
            >
              {id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
        </div>
        <input
          type="search"
          placeholder="Search concepts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="gaps-search"
          aria-label="Search gaps"
        />
      </div>

      <div className="gaps-page-layout">
        <div className="gap-list gap-list-full">
          {filteredAndSorted.map((gap) => {
            const timestamp = captureTimestamps[gap.capture_id];
            const relativeTime = timestamp ? formatRelativeTime(timestamp) : "-";
            const priority = priorityLevel(gap);
            const topic = topicLabel(gap.concept);
            return (
              <article
                key={gap.gap_id}
                className={`gap-row-card gap-row-card-${priority.toLowerCase()} gap-row-card-clickable`}
                onClick={() => setSelectedGapId(gap.gap_id)}
              >
                <div className="gap-row-card-accent" aria-hidden />
                <div className="gap-row-card-main">
                  <div className="gap-row-card-head">
                    <h4 className="gap-row-card-title">{gap.concept}</h4>
                    <span className={`pill pill-priority-${priority.toLowerCase()}`}>{priority}</span>
                  </div>
                  <div className="gap-row-card-meta">
                    <span className="gap-topic-tag"><span aria-hidden>🚀</span> {topic}</span>
                    <span className="gap-relative-time"><span className="gap-time-dot" aria-hidden>⚪</span> {relativeTime}</span>
                    <a href={gap.evidence_url} target="_blank" rel="noreferrer" className="gap-view-capture-btn" onClick={(e) => e.stopPropagation()}>
                      <span aria-hidden>📷</span> View Capture
                    </a>
                    <button
                      type="button"
                      className="gap-row-action-btn"
                      disabled={pendingGapId === gap.gap_id || gap.status === "closed"}
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleResolve(gap);
                      }}
                    >
                      {gap.status === "closed" ? "Resolved" : pendingGapId === gap.gap_id ? "Saving..." : "Mark Resolved"}
                    </button>
                    <button type="button" className="gap-row-action-btn" onClick={(e) => { e.stopPropagation(); }}>Add Note</button>
                    <button type="button" className="gap-row-action-btn" onClick={(e) => { e.stopPropagation(); }}>View Related Document</button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        {selectedGap && (
          <>
            <div
              className="gap-detail-backdrop"
              onClick={() => setSelectedGapId(null)}
              aria-hidden
            />
            <div className="gap-detail-panel" role="dialog" aria-label="Gap detail">
            <div className="gap-detail-panel-inner">
              <button
                type="button"
                className="gap-detail-close"
                onClick={() => setSelectedGapId(null)}
                aria-label="Close"
              >
                ×
              </button>
              <h2 className="gap-detail-title">{selectedGap.concept}</h2>
              <p className="gap-detail-description">
                Full description and context for this knowledge gap. The AI identified this area as needing review based on your capture and syllabus alignment.
              </p>
              <div className="gap-detail-capture">
                <div className="gap-detail-capture-placeholder">Capture screenshot</div>
              </div>
              <div className="gap-detail-section">
                <h3>Suggested resources</h3>
                <p className="gap-detail-muted">From your uploaded documents (placeholder).</p>
              </div>
              <div className="gap-detail-section">
                <label htmlFor="gap-notes">Notes</label>
                <textarea id="gap-notes" className="gap-detail-notes" rows={3} placeholder="Add notes..." />
              </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
