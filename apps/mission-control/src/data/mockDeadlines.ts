/**
 * Mock deadlines for dashboard when bridge does not yet expose GET /api/v1/syllabus or state.deadlines.
 * Replace with API data when available.
 */
export interface MockDeadline {
  id: string;
  name: string;
  due_date: string; // ISO date or datetime
  readiness_score?: number;
  associated_gaps?: string[];
}

export const MOCK_DEADLINES: MockDeadline[] = [
  {
    id: "dl-1",
    name: "Laplace Transform",
    due_date: "2026-03-20T23:59:59Z",
    readiness_score: 65,
    associated_gaps: [],
  },
  {
    id: "dl-2",
    name: "Fourier Series",
    due_date: "2026-03-25T23:59:59Z",
    readiness_score: 58,
    associated_gaps: [],
  },
  {
    id: "dl-3",
    name: "State Space Models",
    due_date: "2026-03-28T23:59:59Z",
    readiness_score: 72,
    associated_gaps: [],
  },
];

/** Nearest upcoming deadline by due_date, or null if all past. */
export function getNearestDeadline(deadlines: MockDeadline[] = MOCK_DEADLINES): MockDeadline | null {
  const now = new Date();
  const upcoming = deadlines
    .filter((d) => new Date(d.due_date) > now)
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
  return upcoming[0] ?? null;
}
