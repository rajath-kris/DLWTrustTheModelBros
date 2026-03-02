import type { LearningState } from "../../types";
import type { TopicScore } from "../topicRadar";
import type { CourseData, MockDeadline, MockDocument, MockSession } from "./types";

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function labelFromTopic(name: string): string {
  const compact = name.split(/\s+/).join(" ").trim();
  if (!compact) {
    return "Topic";
  }
  if (compact.length <= 13) {
    return compact;
  }
  return `${compact.slice(0, 12)}.`;
}

function toDeadlineScorePercent(score: number): number {
  const normalized = score > 1 ? score / 100 : score;
  return Math.round(clamp01(normalized) * 100);
}

function mapLiveDeadlines(state: LearningState, courseId: string): MockDeadline[] {
  return state.deadlines
    .filter((item) => courseId === "all" || item.course_id === courseId)
    .map((item) => ({
      id: item.deadline_id,
      name: item.name,
      due_date: item.due_date,
      readiness_score: toDeadlineScorePercent(item.readiness_score),
      associated_gaps: item.associated_gap_ids,
    }))
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
}

function mapLiveDocuments(state: LearningState, courseId: string): MockDocument[] {
  return state.documents
    .filter((item) => courseId === "all" || item.course_id === courseId)
    .map((item) => ({
      doc_id: item.doc_id,
      course_id: item.course_id,
      module_id: item.module_id,
      course_label: item.course_id.toUpperCase(),
      module_label: item.module_id,
      name: item.name,
      size: formatBytes(item.size_bytes),
      upload_date: item.uploaded_at.split("T")[0] ?? item.uploaded_at,
      type: item.is_anchor ? "anchor" : item.type.includes("pdf") ? "pdf" : "other",
      path: item.file_url,
      is_anchor: item.is_anchor,
    }));
}

function mapLiveSessions(state: LearningState, courseId: string): MockSession[] {
  return state.sessions
    .filter((item) => courseId === "all" || item.course_id === courseId)
    .sort((a, b) => new Date(b.timestamp_utc).getTime() - new Date(a.timestamp_utc).getTime())
    .map((item) => ({
      id: item.session_id,
      timestamp_utc: item.timestamp_utc,
      summary: item.summary,
      topic: item.topic,
      gap_id: item.gap_ids[0],
    }));
}

function mapLiveTopicScores(state: LearningState, courseId: string): TopicScore[] {
  return state.topic_mastery
    .filter((item) => courseId === "all" || item.course_id === courseId)
    .map((item) => ({
      name: item.name,
      label: labelFromTopic(item.name),
      current: clamp01(item.current),
      target: clamp01(item.target),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function buildCaptureTimestampMap(state: LearningState, courseId: string): Record<string, string> {
  const rows = state.captures.filter((item) => courseId === "all" || item.course_id === courseId);
  const map: Record<string, string> = {};
  for (const row of rows) {
    map[row.capture_id] = row.timestamp_utc;
  }
  return map;
}

function buildLiveStats(
  state: LearningState,
  courseId: string,
  deadlines: MockDeadline[],
  gapsCount: number
): CourseData["stats"] {
  const now = Date.now();
  const weekAgo = now - 7 * 24 * 60 * 60 * 1000;
  const captures = state.captures.filter((item) => courseId === "all" || item.course_id === courseId);
  const sessionsThisWeek = captures.filter((item) => new Date(item.timestamp_utc).getTime() >= weekAgo).length;

  const gaps = state.gaps.filter((item) => courseId === "all" || item.course_id === courseId);
  const critical = gaps.filter((item) => item.priority_score >= 0.7 || item.severity >= 0.7).length;
  const nearest = deadlines.find((item) => new Date(item.due_date).getTime() >= now) ?? deadlines[0];
  const nearestDays = nearest ? Math.max(0, Math.ceil((new Date(nearest.due_date).getTime() - now) / (24 * 60 * 60 * 1000))) : 0;

  return {
    masteryPercent: Math.round(clamp01(state.readiness_axes.concept_mastery) * 100),
    activeGaps: gapsCount,
    criticalGaps: critical,
    highGaps: Math.max(0, gapsCount - critical),
    nearestDeadlineName: nearest?.name ?? "No upcoming deadline",
    nearestDeadlineDays: nearestDays,
    nearestDeadlineReadiness: nearest?.readiness_score ?? 0,
    sentinelSessionsThisWeek: sessionsThisWeek,
  };
}

export function buildHybridCourseData(
  fallback: CourseData,
  state: LearningState,
  options?: { liveAvailable?: boolean }
): CourseData {
  const liveAvailable = options?.liveAvailable ?? true;
  const courseId = fallback.id;

  const liveGaps = state.gaps.filter((item) => item.course_id === courseId);
  const liveTopicScores = mapLiveTopicScores(state, courseId);
  const liveDeadlines = mapLiveDeadlines(state, courseId);
  const liveDocuments = mapLiveDocuments(state, courseId);
  const liveSessions = mapLiveSessions(state, courseId);
  const liveCaptureTimestamps = buildCaptureTimestampMap(state, courseId);
  const liveStats = buildLiveStats(state, courseId, liveDeadlines, liveGaps.length);

  const useLiveGaps = liveAvailable && liveGaps.length > 0;
  const useLiveTopicScores = liveAvailable && liveTopicScores.length > 0;
  const useLiveDeadlines = liveAvailable && liveDeadlines.length > 0;
  const useLiveDocuments = liveAvailable && liveDocuments.length > 0;
  const useLiveSessions = liveAvailable && liveSessions.length > 0;
  const useLiveCaptureTimestamps = liveAvailable && Object.keys(liveCaptureTimestamps).length > 0;
  const useLiveStats = liveAvailable && (useLiveGaps || useLiveDeadlines || useLiveSessions);

  return {
    ...fallback,
    gaps: useLiveGaps ? liveGaps : fallback.gaps,
    topicScores: useLiveTopicScores ? liveTopicScores : fallback.topicScores,
    deadlines: useLiveDeadlines ? liveDeadlines : fallback.deadlines,
    documents: useLiveDocuments ? liveDocuments : fallback.documents,
    sessions: useLiveSessions ? liveSessions : fallback.sessions,
    captureTimestamps: useLiveCaptureTimestamps ? liveCaptureTimestamps : fallback.captureTimestamps,
    stats: useLiveStats ? liveStats : fallback.stats,
  };
}
