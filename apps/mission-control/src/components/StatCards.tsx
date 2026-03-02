import { differenceInDays } from "date-fns";
import { getNearestDeadline, type MockDeadline } from "../data/mockDeadlines";
import type { LearningState } from "../types";

function formatPercent(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

/* Mock trends until bridge provides them */
const MOCK_TREND_MASTERY = "↑+8% this week";
const MOCK_TREND_GAPS = "↑+2 since yesterday";
const MOCK_TREND_SESSIONS = "↑+6 vs last week";

interface StatCardsProps {
  state: LearningState;
  deadlines?: MockDeadline[] | null;
}

export function StatCards({ state, deadlines }: StatCardsProps) {
  const mastery = state.readiness_axes.concept_mastery;
  const openGaps = state.gaps.filter((g) => g.status !== "closed");
  const activeGaps = openGaps.length;
  const criticalCount = openGaps.filter((g) => g.priority_score >= 0.7 || g.severity >= 0.7).length;
  const highCount = activeGaps - criticalCount;
  const sessions = state.captures.length;
  const nearest = getNearestDeadline(deadlines ?? undefined);
  const topicCount = new Set(state.gaps.map((g) => g.concept.trim().slice(0, 20))).size || 6;

  const daysUntil = nearest
    ? Math.max(0, differenceInDays(new Date(nearest.due_date), new Date()))
    : null;
  const raw = nearest?.readiness_score;
  const pct =
    raw == null ? 61 : raw <= 1 ? Math.round(raw * 100) : Math.round(raw);
  const readinessPct = Math.min(100, Math.max(0, pct));
  const readinessWarning = nearest != null && readinessPct < 70;

  return (
    <section className="metrics-grid stat-cards-four" aria-label="Key metrics">
      <article className="stat-card stat-card-mastery">
        <p className="stat-card-title">OVERALL MASTERY</p>
        <h2>{formatPercent(mastery)}</h2>
        <p className="stat-subtext">Across {topicCount} active topics</p>
        <p className="stat-trend">{MOCK_TREND_MASTERY}</p>
      </article>
      <article className="stat-card stat-card-gaps">
        <p className="stat-card-title">ACTIVE KNOWLEDGE GAPS</p>
        <h2>{activeGaps}</h2>
        <p className="stat-subtext">
          {criticalCount} critical, {highCount} high priority
        </p>
        <p className="stat-trend stat-trend-warn">{MOCK_TREND_GAPS}</p>
      </article>
      <article className="stat-card stat-card-sessions">
        <p className="stat-card-title">SENTINEL SESSIONS</p>
        <h2>{sessions}</h2>
        <p className="stat-subtext">This week</p>
        <p className="stat-trend">{MOCK_TREND_SESSIONS}</p>
      </article>
      <article className="stat-card stat-card-deadline">
        <p className="stat-card-title">NEAREST DEADLINE</p>
        <h2>{daysUntil != null ? `${daysUntil}d` : "—"}</h2>
        <p className="stat-subtext">{nearest?.name ?? "No upcoming deadline"}</p>
        {nearest && (
          <p className={readinessWarning ? "stat-trend stat-readiness-warn" : "stat-trend stat-trend-warn"}>
            {readinessWarning ? "⚠" : "▲"} Readiness: {readinessPct}%
          </p>
        )}
      </article>
    </section>
  );
}
