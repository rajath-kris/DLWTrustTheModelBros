import { useMemo, useState } from "react";
import { useLearningState } from "../context/LearningStateContext";
import { formatRelativeTime } from "../utils/formatRelativeTime";
import type { KnowledgeGap } from "../types";

function priorityLevel(gap: KnowledgeGap): "CRITICAL" | "HIGH" {
  return gap.priority_score >= 0.75 || gap.severity >= 0.75 ? "CRITICAL" : "HIGH";
}

type FilterId = "all" | "critical" | "high" | "reviewing" | "closed";
type SortId = "priority" | "recency" | "status";

export function KnowledgeGapsPage() {
  const { state, setGapStatus, error, loading } = useLearningState();
  const [filter, setFilter] = useState<FilterId>("all");
  const [sortBy, setSortBy] = useState<SortId>("priority");
  const [search, setSearch] = useState("");
  const [pendingGapId, setPendingGapId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const captureTimestamps = useMemo(
    () => Object.fromEntries(state.captures.map((capture) => [capture.capture_id, capture.timestamp_utc])),
    [state.captures]
  );

  const gaps = state.gaps;
  const activeCount = gaps.filter((gap) => gap.status !== "closed").length;

  const filteredAndSorted = useMemo(() => {
    let list = gaps;
    if (filter === "critical") list = list.filter((gap) => priorityLevel(gap) === "CRITICAL");
    else if (filter === "high") list = list.filter((gap) => priorityLevel(gap) === "HIGH");
    else if (filter === "reviewing") list = list.filter((gap) => gap.status === "reviewing");
    else if (filter === "closed") list = list.filter((gap) => gap.status === "closed");

    const query = search.trim().toLowerCase();
    if (query) {
      list = list.filter((gap) => gap.concept.toLowerCase().includes(query));
    }

    if (sortBy === "priority") {
      list = [...list].sort((a, b) => b.priority_score - a.priority_score);
    } else if (sortBy === "status") {
      list = [...list].sort((a, b) => (a.status === "closed" ? 1 : 0) - (b.status === "closed" ? 1 : 0));
    } else {
      list = [...list].sort((a, b) => {
        const aTime = captureTimestamps[a.capture_id] ?? "";
        const bTime = captureTimestamps[b.capture_id] ?? "";
        return new Date(bTime).getTime() - new Date(aTime).getTime();
      });
    }
    return list;
  }, [gaps, filter, sortBy, search, captureTimestamps]);

  async function markResolved(gapId: string) {
    setMutationError(null);
    setPendingGapId(gapId);
    try {
      await setGapStatus(gapId, "closed");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Could not update gap status.");
    } finally {
      setPendingGapId(null);
    }
  }

  return (
    <div className="page-shell page-fade">
      <header className="gaps-page-header">
        <div className="gaps-page-title-row">
          <h1>Knowledge Gaps</h1>
          <span className="pill pill-gaps-active">{activeCount} Active</span>
        </div>
      </header>

      {loading && <p className="status-line">Loading gaps...</p>}
      {error && <p className="status-line">{error}</p>}
      {mutationError && <p className="status-line error">{mutationError}</p>}

      <div className="gaps-page-controls">
        <div className="gaps-page-filters">
          {(["all", "critical", "high", "reviewing", "closed"] as const).map((id) => (
            <button key={id} type="button" className={`filter ${filter === id ? "active" : ""}`} onClick={() => setFilter(id)}>
              {id === "all" ? "All" : id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
        </div>
        <div className="gaps-page-sort">
          <span className="gaps-sort-label">Sort:</span>
          {(["priority", "recency", "status"] as const).map((id) => (
            <button key={id} type="button" className={`filter ${sortBy === id ? "active" : ""}`} onClick={() => setSortBy(id)}>
              {id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
        </div>
        <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search concepts..." className="gaps-search" />
      </div>

      <div className="gap-list gap-list-full">
        {filteredAndSorted.map((gap) => {
          const relativeTime = captureTimestamps[gap.capture_id] ? formatRelativeTime(captureTimestamps[gap.capture_id]) : "-";
          const priority = priorityLevel(gap);
          return (
            <article key={gap.gap_id} className={`gap-row-card gap-row-card-${priority.toLowerCase()}`}>
              <div className="gap-row-card-accent" aria-hidden />
              <div className="gap-row-card-main">
                <div className="gap-row-card-head">
                  <h4 className="gap-row-card-title">{gap.concept}</h4>
                  <span className={`pill pill-priority-${priority.toLowerCase()}`}>{priority}</span>
                </div>
                <div className="gap-row-card-meta">
                  <span className="gap-relative-time">{relativeTime}</span>
                  <button
                    type="button"
                    className="gap-row-action-btn"
                    disabled={pendingGapId === gap.gap_id || gap.status === "closed"}
                    onClick={() => void markResolved(gap.gap_id)}
                  >
                    {gap.status === "closed" ? "Resolved" : pendingGapId === gap.gap_id ? "Saving..." : "Mark Resolved"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
