import type { KnowledgeGap } from "../types";

export interface TopicMasteryRow {
  name: string;
  mastery_score: number;
  openGaps: number;
  needsAttention: boolean;
}

const MASTERY_ATTENTION_THRESHOLD = 0.7;

/**
 * Derive topic-level mastery from gaps. Each unique concept is treated as a topic;
 * mastery = 1 - avg(severity) for open gaps in that topic, or 1 if no open gaps.
 */
export function deriveTopicMastery(gaps: KnowledgeGap[]): TopicMasteryRow[] {
  const byConcept = new Map<string, KnowledgeGap[]>();
  for (const gap of gaps) {
    const key = gap.concept.trim() || "Other";
    if (!byConcept.has(key)) byConcept.set(key, []);
    byConcept.get(key)!.push(gap);
  }

  const rows: TopicMasteryRow[] = [];
  for (const [name, list] of byConcept.entries()) {
    const open = list.filter((g) => g.status !== "closed");
    const mastery_score =
      open.length === 0 ? 1 : Math.max(0, 1 - open.reduce((s, g) => s + g.severity, 0) / open.length);
    rows.push({
      name,
      mastery_score,
      openGaps: open.length,
      needsAttention: mastery_score < MASTERY_ATTENTION_THRESHOLD || open.length > 0,
    });
  }

  return rows.sort((a, b) => a.mastery_score - b.mastery_score);
}
