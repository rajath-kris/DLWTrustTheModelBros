import type { KnowledgeGap } from "../../types";
import type { CourseData } from "./types";

const EE2001_TOPIC_SCORES = [
  { name: "Ohm's Law & KVL", label: "Ohm's Law & KVL", current: 0.72, target: 0.8 },
  { name: "AC Circuits", label: "AC Circuits", current: 0.58, target: 0.75 },
  { name: "Thevenin/Norton", label: "Thevenin/Norton", current: 0.65, target: 0.7 },
  { name: "Op-Amps", label: "Op-Amps", current: 0.78, target: 0.8 },
  { name: "Filters", label: "Filters", current: 0.62, target: 0.75 },
  { name: "Semiconductors", label: "Semiconductors", current: 0.7, target: 0.75 },
];

function isoHoursAgo(h: number): string {
  const d = new Date();
  d.setHours(d.getHours() - h);
  return d.toISOString();
}

const EE2001_CAPTURE_TIMESTAMPS: Record<string, string> = {
  e1: isoHoursAgo(3),
  e2: isoHoursAgo(8),
  e3: isoHoursAgo(24),
};

const EE2001_GAPS: KnowledgeGap[] = [
  {
    gap_id: "ee2001-gap-1",
    concept: "Phasor representation of AC voltage",
    severity: 0.88,
    confidence: 0.82,
    status: "open",
    capture_id: "e1",
    evidence_url: "#",
    deadline_score: 0.75,
    priority_score: 0.85,
  },
  {
    gap_id: "ee2001-gap-2",
    concept: "Thevenin equivalent with dependent sources",
    severity: 0.62,
    confidence: 0.78,
    status: "open",
    capture_id: "e2",
    evidence_url: "#",
    deadline_score: 0.5,
    priority_score: 0.6,
  },
  {
    gap_id: "ee2001-gap-3",
    concept: "Band-pass filter cutoff frequency",
    severity: 0.7,
    confidence: 0.8,
    status: "reviewing",
    capture_id: "e3",
    evidence_url: "#",
    deadline_score: 0.6,
    priority_score: 0.68,
  },
];

const EE2001_DEADLINES = [
  {
    id: "ee2001-dl-1",
    name: "Lab Report 3",
    due_date: new Date(Date.now() + 11 * 24 * 60 * 60 * 1000).toISOString(),
    readiness_score: 74,
    associated_gaps: [],
  },
];

const EE2001_DOCUMENTS = [
  { name: "EE2001_Syllabus.pdf", size: "0.9 MB", upload_date: "2026-02-20", type: "anchor" as const, path: "/path/to/EE2001_Syllabus.pdf" },
  { name: "Lab_03_Manual.pdf", size: "2.1 MB", upload_date: "2026-02-22", type: "pdf" as const, path: "/path/to/Lab_03_Manual.pdf" },
  { name: "Lecture_05_AC.pdf", size: "1.8 MB", upload_date: "2026-02-18", type: "pdf" as const, path: "/path/to/Lecture_05_AC.pdf" },
];

const EE2001_SESSIONS = Array.from({ length: 11 }, (_, i) => ({
  id: `ee2001-session-${i + 1}`,
  timestamp_utc: new Date(Date.now() - (i * 6 + 2) * 60 * 60 * 1000).toISOString(),
  summary: i % 2 === 0 ? "Worked through AC circuit phasor problem." : "Reviewed Thevenin equivalent steps.",
  topic: i % 2 === 0 ? "AC Circuits" : "Thevenin/Norton",
  gap_id: i % 3 === 0 ? EE2001_GAPS[i % 3].gap_id : undefined,
}));

export const EE2001_DATA: CourseData = {
  id: "ee2001",
  name: "EE2001 — Circuit Analysis",
  accentColor: "#f97316",
  topicScores: EE2001_TOPIC_SCORES,
  gaps: EE2001_GAPS,
  documents: EE2001_DOCUMENTS,
  deadlines: EE2001_DEADLINES,
  sessions: EE2001_SESSIONS,
  stats: {
    masteryPercent: 68,
    activeGaps: 3,
    criticalGaps: 1,
    highGaps: 2,
    nearestDeadlineName: "Lab Report 3",
    nearestDeadlineDays: 11,
    nearestDeadlineReadiness: 74,
    sentinelSessionsThisWeek: 11,
  },
  captureTimestamps: EE2001_CAPTURE_TIMESTAMPS,
};
