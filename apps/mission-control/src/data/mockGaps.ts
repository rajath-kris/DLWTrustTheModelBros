import type { KnowledgeGap } from "../types";

function isoHoursAgo(h: number): string {
  const d = new Date();
  d.setHours(d.getHours() - h);
  return d.toISOString();
}

/** Mock capture timestamps for relative time display. */
export const MOCK_CAPTURE_TIMESTAMPS: Record<string, string> = {
  c1: isoHoursAgo(2),
  c2: isoHoursAgo(5),
  c3: isoHoursAgo(24),
  c4: isoHoursAgo(48),
  c5: isoHoursAgo(72),
};

/** Mock knowledge gaps for the Gaps & Resources section (varied priorities and topics). */
export const MOCK_GAPS: KnowledgeGap[] = [
  {
    gap_id: "gap-1",
    concept: "BST deletion with two children — rebalancing",
    severity: 0.9,
    confidence: 0.85,
    status: "open",
    capture_id: "c1",
    evidence_url: "#",
    deadline_score: 0.8,
    priority_score: 0.88,
  },
  {
    gap_id: "gap-2",
    concept: "Memoization vs tabulation in DP",
    severity: 0.7,
    confidence: 0.8,
    status: "open",
    capture_id: "c2",
    evidence_url: "#",
    deadline_score: 0.6,
    priority_score: 0.72,
  },
  {
    gap_id: "gap-3",
    concept: "Dijkstra relaxation and priority queue",
    severity: 0.85,
    confidence: 0.9,
    status: "reviewing",
    capture_id: "c3",
    evidence_url: "#",
    deadline_score: 0.9,
    priority_score: 0.86,
  },
  {
    gap_id: "gap-4",
    concept: "Quicksort partition and pivot selection",
    severity: 0.55,
    confidence: 0.75,
    status: "open",
    capture_id: "c4",
    evidence_url: "#",
    deadline_score: 0.5,
    priority_score: 0.58,
  },
  {
    gap_id: "gap-5",
    concept: "Base case design in recursion",
    severity: 0.65,
    confidence: 0.82,
    status: "open",
    capture_id: "c5",
    evidence_url: "#",
    deadline_score: 0.55,
    priority_score: 0.64,
  },
  {
    gap_id: "gap-6",
    concept: "Hash collision handling — chaining",
    severity: 0.5,
    confidence: 0.78,
    status: "open",
    capture_id: "c5",
    evidence_url: "#",
    deadline_score: 0.4,
    priority_score: 0.52,
  },
  {
    gap_id: "gap-7",
    concept: "Inorder traversal iterative with stack",
    severity: 0.82,
    confidence: 0.88,
    status: "open",
    capture_id: "c1",
    evidence_url: "#",
    deadline_score: 0.85,
    priority_score: 0.84,
  },
];
