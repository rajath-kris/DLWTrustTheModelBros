import type { KnowledgeGap, LearningState } from "../types";
import { formatRelativeTime } from "../utils/formatRelativeTime";
import { MOCK_CAPTURE_TIMESTAMPS, MOCK_GAPS } from "../data/mockGaps";

/** Derive a short topic label from gap concept. */
function topicLabel(concept: string): string {
  const c = concept.trim();
  if (/binary|tree|bst|avl|traversal|inorder|stack/i.test(c)) return "Binary Trees";
  if (/dynamic|memo|tabulation|dp/i.test(c)) return "Dynamic Programming";
  if (/graph|bfs|dfs|dijkstra|relaxation/i.test(c)) return "Graph Algorithms";
  if (/sort|search|quicksort|partition|pivot/i.test(c)) return "Sorting";
  if (/recur|backtrack|base case/i.test(c)) return "Recursion";
  if (/hash|map|set|collision|chain/i.test(c)) return "Hash Maps";
  return c.split(/[,.]/)[0]?.trim().slice(0, 20) || "Other";
}

function priorityLevel(gap: KnowledgeGap): "CRITICAL" | "HIGH" {
  return gap.priority_score >= 0.75 || gap.severity >= 0.75 ? "CRITICAL" : "HIGH";
}

interface GapListProps {
  state: LearningState;
  loading: boolean;
  error: string | null;
  onCycleStatus: (gap: KnowledgeGap) => Promise<void>;
  /** When provided (e.g. from course context), use instead of MOCK_GAPS. */
  gaps?: KnowledgeGap[];
  /** When provided, use for relative time; keys are capture_id. */
  captureTimestamps?: Record<string, string>;
}

export function GapList({ state, loading, error, onCycleStatus, gaps: gapsProp, captureTimestamps }: GapListProps) {
  const gaps = gapsProp ?? MOCK_GAPS;
  const activeCount = gaps.filter((g) => g.status !== "closed").length;

  const captureTimestampMap = new Map<string, string>();
  if (captureTimestamps) {
    Object.entries(captureTimestamps).forEach(([id, ts]) => captureTimestampMap.set(id, ts));
  } else {
    Object.entries(MOCK_CAPTURE_TIMESTAMPS).forEach(([id, ts]) => captureTimestampMap.set(id, ts));
  }

  return (
    <article className="card gaps-card">
      <header className="gaps-head-new">
        <h3>Knowledge Gap Tracker</h3>
        <span className="pill pill-gaps-active">{activeCount} Active</span>
      </header>

      <div className="gap-list gap-list-scroll">
        {gaps.map((gap) => {
          const timestamp = captureTimestampMap.get(gap.capture_id);
          const relativeTime = timestamp ? formatRelativeTime(timestamp) : "-";
          const priority = priorityLevel(gap);
          const topic = topicLabel(gap.concept);
          return (
            <article
              key={gap.gap_id}
              className={`gap-row-card gap-row-card-${priority.toLowerCase()}`}
            >
              <div className="gap-row-card-accent" aria-hidden />
              <div className="gap-row-card-main">
                <div className="gap-row-card-head">
                  <h4 className="gap-row-card-title">{gap.concept}</h4>
                  <span className={`pill pill-priority-${priority.toLowerCase()}`}>
                    {priority}
                  </span>
                </div>
                <div className="gap-row-card-meta">
                  <span className="gap-topic-tag">
                    <span aria-hidden>🚀</span> {topic}
                  </span>
                  <span className="gap-relative-time">
                    <span className="gap-time-dot" aria-hidden>⚪</span> {relativeTime}
                  </span>
                  <a
                    href={gap.evidence_url}
                    target="_blank"
                    rel="noreferrer"
                    className="gap-view-capture-btn"
                  >
                    <span aria-hidden>📷</span> View Capture
                  </a>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </article>
  );
}
