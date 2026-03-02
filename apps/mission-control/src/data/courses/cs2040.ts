import type { KnowledgeGap } from "../../types";
import type { CourseData } from "./types";
import { MOCK_GAPS } from "../mockGaps";
import { MOCK_CAPTURE_TIMESTAMPS } from "../mockGaps";

const TOPIC_SCORES = [
  { name: "Binary Trees & Traversal", label: "Binary Trees", current: 0.38, target: 0.75 },
  { name: "Dynamic Programming", label: "Dynamic Prog.", current: 0.55, target: 0.8 },
  { name: "Graph Algorithms", label: "Graph Algos", current: 0.67, target: 0.7 },
  { name: "Sorting & Searching", label: "Sorting", current: 0.82, target: 0.85 },
  { name: "Recursion & Backtracking", label: "Recursion", current: 0.74, target: 0.75 },
  { name: "Hash Maps & Sets", label: "Hash Maps", current: 0.89, target: 0.8 },
];

const DEADLINES = [
  {
    id: "cs2040-dl-1",
    name: "Data Structures Mid-Term",
    due_date: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString(),
    readiness_score: 61,
    associated_gaps: [],
  },
  {
    id: "cs2040-dl-2",
    name: "BST Assignment Due",
    due_date: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
    readiness_score: 78,
    associated_gaps: [],
  },
];

const DOCUMENTS = [
  { name: "CS2040_Syllabus.pdf", size: "1.2 MB", upload_date: "2026-02-28", type: "anchor" as const, path: "/path/to/CS2040_Syllabus.pdf" },
  { name: "Lecture_07_Trees.pdf", size: "3.4 MB", upload_date: "2026-02-25", type: "pdf" as const, path: "/path/to/Lecture_07_Trees.pdf" },
  { name: "Lecture_08_DP.pdf", size: "2.1 MB", upload_date: "2026-02-24", type: "pdf" as const, path: "/path/to/Lecture_08_DP.pdf" },
  { name: "Practice_Problems_W8.pdf", size: "0.8 MB", upload_date: "2026-02-23", type: "other" as const, path: "/path/to/Practice_Problems_W8.pdf" },
];

const SESSIONS = Array.from({ length: 24 }, (_, i) => ({
  id: `cs2040-session-${i + 1}`,
  timestamp_utc: new Date(Date.now() - (i * 4 + 1) * 60 * 60 * 1000).toISOString(),
  summary: i % 3 === 0 ? "Reviewed BST deletion and rebalancing." : "Captured confusion on memoization vs tabulation.",
  topic: i % 2 === 0 ? "Binary Trees" : "Dynamic Programming",
  gap_id: i % 4 === 0 ? `gap-${(i % 7) + 1}` : undefined,
}));

const gaps: KnowledgeGap[] = MOCK_GAPS.map((g) => ({ ...g, gap_id: `cs2040-${g.gap_id}` }));

export const CS2040_DATA: CourseData = {
  id: "cs2040",
  name: "CS2040 — Data Structures & Algorithms",
  accentColor: "#3b82f6",
  topicScores: TOPIC_SCORES,
  gaps,
  documents: DOCUMENTS,
  deadlines: DEADLINES,
  sessions: SESSIONS,
  stats: {
    masteryPercent: 73,
    activeGaps: 7,
    criticalGaps: 3,
    highGaps: 4,
    nearestDeadlineName: "Data Structures Mid-Term",
    nearestDeadlineDays: 4,
    nearestDeadlineReadiness: 61,
    sentinelSessionsThisWeek: 24,
  },
  captureTimestamps: MOCK_CAPTURE_TIMESTAMPS,
};
