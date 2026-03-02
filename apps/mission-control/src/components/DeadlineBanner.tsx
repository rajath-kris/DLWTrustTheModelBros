import { getNearestDeadline, type MockDeadline } from "../data/mockDeadlines";
import type { KnowledgeGap, LearningState } from "../types";

interface DeadlineBannerProps {
  dismissed: boolean;
  onDismiss: () => void;
  onViewGaps?: () => void;
  openGapsCount?: number;
  deadlines?: MockDeadline[] | null;
  state?: LearningState | null;
}

function getCriticalGapsSummary(gaps: KnowledgeGap[]): { count: number; topicLabels: string[] } {
  const critical = gaps.filter((g) => g.status !== "closed" && (g.priority_score >= 0.7 || g.severity >= 0.7));
  const topicSet = new Set<string>();
  for (const g of critical) {
    const label = g.concept.split(/[&,]|\band\b/i)[0]?.trim().slice(0, 25) || "Other";
    topicSet.add(label);
  }
  return { count: critical.length, topicLabels: Array.from(topicSet).slice(0, 3) };
}

export function DeadlineBanner({
  dismissed,
  onDismiss,
  onViewGaps,
  openGapsCount = 0,
  deadlines,
  state,
}: DeadlineBannerProps) {
  const nearest = getNearestDeadline(deadlines ?? undefined);
  if (dismissed || !nearest) return null;

  const dueDate = new Date(nearest.due_date);
  const daysLeft = Math.ceil((dueDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  const { count: criticalCount, topicLabels } = state
    ? getCriticalGapsSummary(state.gaps)
    : { count: openGapsCount, topicLabels: [] };
  const topicPhrase =
    topicLabels.length > 0 ? topicLabels.join(" and ") : "your weak areas";
  const narrative =
    daysLeft <= 0
      ? "This deadline has passed."
      : `Upcoming: ${nearest.name} in ${daysLeft} day${daysLeft !== 1 ? "s" : ""}. Your Readiness Radar shows ${criticalCount} critical gap${criticalCount !== 1 ? "s" : ""} in ${topicPhrase}. Focus study time here.`;

  return (
    <aside className="deadline-banner" role="region" aria-label="Nearest deadline">
      <div className="deadline-banner-icon" aria-hidden>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </div>
      <div className="deadline-banner-content">
        <p className="deadline-banner-message">{narrative}</p>
        {onViewGaps && (
          <button type="button" className="deadline-banner-cta" onClick={onViewGaps}>
            View Study Plan →
          </button>
        )}
      </div>
      <button
        type="button"
        className="deadline-banner-dismiss"
        onClick={onDismiss}
        aria-label="Dismiss deadline banner"
      >
        ×
      </button>
    </aside>
  );
}
