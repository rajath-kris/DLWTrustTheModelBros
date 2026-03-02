import type { KnowledgeGap } from "../../types";
import type { TopicScore } from "../topicRadar";

export interface MockDeadline {
  id: string;
  name: string;
  due_date: string;
  readiness_score?: number;
  associated_gaps?: string[];
}

export interface MockDocument {
  doc_id?: string;
  course_id?: string;
  module_id?: string;
  course_label?: string;
  module_label?: string;
  name: string;
  size: string;
  upload_date: string;
  type: "anchor" | "pdf" | "other";
  path?: string;
  is_anchor?: boolean;
}

export interface MockSession {
  id: string;
  timestamp_utc: string;
  summary: string;
  topic: string;
  gap_id?: string;
  thumbnail_url?: string;
}

export interface CourseStats {
  masteryPercent: number;
  activeGaps: number;
  criticalGaps: number;
  highGaps: number;
  nearestDeadlineName: string;
  nearestDeadlineDays: number;
  nearestDeadlineReadiness: number;
  sentinelSessionsThisWeek: number;
}

export interface CourseData {
  id: string;
  name: string;
  accentColor: string;
  topicScores: TopicScore[];
  gaps: KnowledgeGap[];
  documents: MockDocument[];
  deadlines: MockDeadline[];
  sessions: MockSession[];
  stats: CourseStats;
  /** Optional: capture_id -> ISO timestamp for relative time in gap list */
  captureTimestamps?: Record<string, string>;
}

export interface CourseInfo {
  id: string;
  name: string;
  accentColor: string;
}
