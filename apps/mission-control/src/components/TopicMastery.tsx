import type { KnowledgeGap } from "../types";
import type { TopicScore } from "../data/topicRadar";
import { MOCK_TOPIC_SCORES } from "../data/topicRadar";
import { deriveTopicMastery } from "../utils/deriveTopicMastery";

function formatPercent(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

/** Map mastery (0–1) to tier for progress bar color. First image: 74% blue, 82% green. */
function getMasteryTier(score: number): string {
  const pct = Math.round(score * 100);
  if (pct < 55) return "tier-low";
  if (pct < 67) return "tier-mid-low";
  if (pct < 74) return "tier-mid";
  if (pct < 82) return "tier-high";
  if (pct < 89) return "tier-mid-high";
  return "tier-very-high";
}

/** Default mastery scores for the six topics when no gap data (mockup-aligned). */
const DEFAULT_MASTERY = [0.48, 0.55, 0.67, 0.82, 0.74, 0.89];

const BAR_CHART_ICON = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <path d="M3 17v-4h4v4H3zM9 17V9h4v8H9zM15 17V5h4v12h-4z" fill="#8b5cf6" />
    <path d="M21 19H3" stroke="#b794f6" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

interface TopicMasteryProps {
  gaps: KnowledgeGap[];
  /** Topic scores used for the Readiness Radar; 0–1 current/target per topic. */
  topics: TopicScore[];
}

export function TopicMastery({ gaps, topics }: TopicMasteryProps) {
  // Derive gap info once so we can show open gap counts where available.
  const derivedFromGaps = deriveTopicMastery(gaps);
  const byConceptName = new Map(derivedFromGaps.map((r) => [r.name, r]));

  // Use the same topic scores that drive the Readiness Radar. If none are
  // provided (defensive), fall back to the default mock scores so the UI
  // still renders six rows.
  const baseTopics = topics.length > 0 ? topics : MOCK_TOPIC_SCORES;

  const rows = baseTopics.map((t, i) => {
    const gapRow = byConceptName.get(t.name);
    const mastery = typeof t.current === "number" ? t.current : DEFAULT_MASTERY[i] ?? 0.5;
    const openGaps = gapRow?.openGaps ?? 0;
    const needsAttention = mastery < 0.7 || openGaps > 0;
    return {
      name: t.name,
      mastery_score: mastery,
      openGaps,
      needsAttention,
    };
  });

  const needAttentionCount = rows.filter((r) => r.needsAttention).length;

  return (
    <article className="card topic-mastery-card">
      <header className="topic-mastery-head-flex">
        <div>
          <div className="topic-mastery-title-row">
            {BAR_CHART_ICON}
            <h3>Topic Mastery Breakdown</h3>
          </div>
        </div>
        {needAttentionCount > 0 && (
          <span className="pill pill-warn">{needAttentionCount} Need Attention</span>
        )}
      </header>
      <ul className="topic-mastery-list">
        {rows.map((row) => (
          <li
            key={row.name}
            className={`topic-mastery-row ${getMasteryTier(row.mastery_score)} ${row.needsAttention ? "needs-attention" : ""}`}
          >
            <div className="topic-mastery-head">
              <span className="topic-mastery-name">{row.name}</span>
              <span className={`topic-mastery-pct ${getMasteryTier(row.mastery_score)}`}>{formatPercent(row.mastery_score)}</span>
            </div>
            <div className="topic-mastery-bar-wrap">
              <div
                className={`topic-mastery-bar ${getMasteryTier(row.mastery_score)}`}
                style={{ width: `${Math.round(row.mastery_score * 100)}%` }}
              />
            </div>
            {row.openGaps > 0 && (
              <span className="topic-mastery-gaps">{row.openGaps} open gap(s)</span>
            )}
          </li>
        ))}
      </ul>
    </article>
  );
}
