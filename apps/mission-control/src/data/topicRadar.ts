/**
 * Topic labels for the Readiness Radar (short for axis labels).
 */
export const TOPIC_RADAR_LABELS: Record<string, string> = {
  "Binary Trees & Traversal": "Binary Trees",
  "Binary Trees": "Binary Trees",
  "Dynamic Programming": "Dynamic Prog.",
  "Graph Algorithms": "Graph Algos",
  "Sorting & Searching": "Sorting",
  "Sorting": "Sorting",
  "Recursion & Backtracking": "Recursion",
  "Recursion": "Recursion",
  "Hash Maps & Sets": "Hash Maps",
  "Hash Maps": "Hash Maps",
};

export const DEFAULT_TOPIC_ORDER = [
  "Binary Trees & Traversal",
  "Dynamic Programming",
  "Graph Algorithms",
  "Sorting & Searching",
  "Recursion & Backtracking",
  "Hash Maps & Sets",
];

export interface TopicScore {
  name: string;
  label: string;
  current: number;
  target: number;
}

/** Uneven, realistic mock data for the Readiness Radar (current/target as 0–1). */
export const MOCK_TOPIC_SCORES: TopicScore[] = [
  { name: "Binary Trees & Traversal", label: "Binary Trees", current: 0.38, target: 0.75 },
  { name: "Dynamic Programming", label: "Dynamic Prog.", current: 0.55, target: 0.8 },
  { name: "Graph Algorithms", label: "Graph Algos", current: 0.67, target: 0.7 },
  { name: "Sorting & Searching", label: "Sorting", current: 0.82, target: 0.85 },
  { name: "Recursion & Backtracking", label: "Recursion", current: 0.74, target: 0.75 },
  { name: "Hash Maps & Sets", label: "Hash Maps", current: 0.89, target: 0.8 },
];

/**
 * Build 6 topic scores for radar: use derived topic rows (by index) or defaults.
 */
export function buildTopicScoresForRadar(
  topicRows: Array<{ name: string; mastery_score: number }>,
  defaultTarget = 0.8
): TopicScore[] {
  const result: TopicScore[] = [];
  for (let i = 0; i < DEFAULT_TOPIC_ORDER.length; i++) {
    const name = DEFAULT_TOPIC_ORDER[i];
    const row = topicRows[i];
    const current = row != null ? row.mastery_score : 0.5;
    result.push({
      name,
      label: TOPIC_RADAR_LABELS[name] ?? name.slice(0, 12),
      current,
      target: defaultTarget,
    });
  }
  return result;
}
