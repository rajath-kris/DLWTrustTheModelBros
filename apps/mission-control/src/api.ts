import type {
  ActiveTopicResponse,
  BrainOverviewResponse,
  CourseDeadline,
  CourseDocument,
  CourseSummary,
  GapStatus,
  LearningState,
  SentinelSessionContext,
  TopicListResponse,
  TopicSummary,
  QuizPrepareRequest,
  QuizPrepareResponse,
  QuizSubmitRequest,
  QuizSubmitResponse,
  SentinelRuntimeActionResponse,
  SentinelRuntimeStatus,
  SessionEvent,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export const emptyState: LearningState = {
  updated_at: new Date(0).toISOString(),
  captures: [],
  gaps: [],
  courses: [],
  topic_mastery: [],
  topics: [],
  study_actions: [],
  deadlines: [],
  documents: [],
  sessions: [],
  question_bank: [],
  quizzes: [],
  readiness_axes: {
    concept_mastery: 0,
    deadline_pressure: 0,
    retention_risk: 0,
    problem_transfer: 0,
    consistency: 0,
  },
};

export async function fetchState(): Promise<LearningState> {
  const response = await fetch(`${API_BASE}/api/v1/state`);
  if (!response.ok) {
    throw new Error(`State request failed: ${response.status}`);
  }
  return (await response.json()) as LearningState;
}

export async function fetchBrainOverview(courseId: string): Promise<BrainOverviewResponse> {
  const response = await fetch(`${API_BASE}/api/v1/brain/overview?course_id=${encodeURIComponent(courseId)}`);
  if (!response.ok) {
    throw new Error(`Brain overview request failed: ${response.status}`);
  }
  return (await response.json()) as BrainOverviewResponse;
}

export async function updateGapStatus(gapId: string, status: GapStatus): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/gaps/${gapId}/status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    throw new Error(`Gap update failed: ${response.status}`);
  }
}

export async function fetchDeadlines(courseId: string): Promise<CourseDeadline[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/deadlines`);
  if (!response.ok) {
    throw new Error(`Deadlines request failed: ${response.status}`);
  }
  const data = (await response.json()) as { deadlines?: CourseDeadline[] };
  return Array.isArray(data.deadlines) ? data.deadlines : [];
}

export async function createDeadline(
  courseId: string,
  payload: {
    name: string;
    due_date: string;
    readiness_score?: number;
    associated_gap_ids?: string[];
  }
): Promise<CourseDeadline> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/deadlines`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Create deadline failed: ${response.status}`);
  }
  return (await response.json()) as CourseDeadline;
}

export async function fetchDocuments(courseId: string): Promise<CourseDocument[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents`);
  if (!response.ok) {
    throw new Error(`Documents request failed: ${response.status}`);
  }
  const data = (await response.json()) as { documents?: CourseDocument[] };
  return Array.isArray(data.documents) ? data.documents : [];
}

export async function fetchTopics(): Promise<TopicListResponse> {
  const response = await fetch(`${API_BASE}/api/v1/topics`);
  if (!response.ok) {
    throw new Error(`Topics request failed: ${response.status}`);
  }
  return (await response.json()) as TopicListResponse;
}

export async function fetchTopicsForCourse(courseId: string): Promise<TopicListResponse> {
  const response = await fetch(
    `${API_BASE}/api/v1/topics?course_id=${encodeURIComponent(courseId)}`
  );
  if (!response.ok) {
    throw new Error(`Topics request failed: ${response.status}`);
  }
  return (await response.json()) as TopicListResponse;
}

export async function upsertTopic(topicId: string, topicName: string, courseId = "all"): Promise<TopicSummary> {
  const response = await fetch(`${API_BASE}/api/v1/topics`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      topic_id: topicId.trim(),
      topic_name: topicName.trim(),
      course_id: courseId.trim() || "all",
    }),
  });
  if (!response.ok) {
    throw new Error(`Create topic failed: ${response.status}`);
  }
  return (await response.json()) as TopicSummary;
}

export async function createCourse(courseId: string, courseName: string): Promise<CourseSummary> {
  const response = await fetch(`${API_BASE}/api/v1/courses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      course_id: courseId.trim(),
      course_name: courseName.trim(),
    }),
  });
  if (!response.ok) {
    throw new Error(`Create course failed: ${response.status}`);
  }
  return (await response.json()) as CourseSummary;
}

export async function deleteCourse(courseId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Delete course failed: ${response.status}`);
  }
}

export async function fetchActiveTopic(): Promise<ActiveTopicResponse> {
  const response = await fetch(`${API_BASE}/api/v1/topics/active`);
  if (!response.ok) {
    throw new Error(`Active topic request failed: ${response.status}`);
  }
  return (await response.json()) as ActiveTopicResponse;
}

export async function uploadDocument(
  courseId: string,
  topicId: string,
  file: File,
  documentName?: string,
  documentType?: string
): Promise<CourseDocument> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("topic_id", topicId.trim());
  if (documentName && documentName.trim()) {
    formData.append("document_name", documentName.trim());
  }
  if (documentType && documentType.trim()) {
    formData.append("document_type", documentType.trim());
  }
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    let detail = `Upload document failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload?.detail) {
        detail = `Upload document failed: ${payload.detail}`;
      }
    } catch {
      // Keep fallback status message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as CourseDocument;
}

export async function setDocumentAnchor(courseId: string, docId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/${encodeURIComponent(docId)}/anchor`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Set anchor failed: ${response.status}`);
  }
}

export async function deleteDocument(courseId: string, docId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Delete document failed: ${response.status}`);
  }
}

export async function moveDocumentToTopic(courseId: string, docId: string, topicId: string): Promise<CourseDocument> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/${encodeURIComponent(docId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ topic_id: topicId }),
  });
  if (!response.ok) {
    throw new Error(`Move document failed: ${response.status}`);
  }
  return (await response.json()) as CourseDocument;
}

export async function fetchSessions(courseId: string): Promise<SessionEvent[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/sessions`);
  if (!response.ok) {
    throw new Error(`Sessions request failed: ${response.status}`);
  }
  const data = (await response.json()) as { sessions?: SessionEvent[] };
  return Array.isArray(data.sessions) ? data.sessions : [];
}

export async function prepareQuiz(payload: QuizPrepareRequest): Promise<QuizPrepareResponse> {
  const response = await fetch(`${API_BASE}/api/v1/quizzes/prepare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Quiz prepare failed: ${response.status}`);
  }
  return (await response.json()) as QuizPrepareResponse;
}

export async function submitQuiz(payload: QuizSubmitRequest): Promise<QuizSubmitResponse> {
  const response = await fetch(`${API_BASE}/api/v1/quizzes/submit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Quiz submit failed: ${response.status}`);
  }
  return (await response.json()) as QuizSubmitResponse;
}

export function openEventStream(onMessage: (event: MessageEvent) => void): EventSource {
  const stream = new EventSource(`${API_BASE}/api/v1/events/stream`);
  stream.onmessage = onMessage;
  return stream;
}

export async function fetchSentinelRuntimeStatus(): Promise<SentinelRuntimeStatus> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime`);
  if (!response.ok) {
    throw new Error(`Sentinel runtime status request failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeStatus;
}

export async function startSentinelRuntime(): Promise<SentinelRuntimeActionResponse> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime/start`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Start sentinel runtime failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeActionResponse;
}

export async function stopSentinelRuntime(): Promise<SentinelRuntimeActionResponse> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime/stop`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Stop sentinel runtime failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeActionResponse;
}

export async function fetchSentinelSessionContext(): Promise<SentinelSessionContext> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/session-context`);
  if (!response.ok) {
    throw new Error(`Sentinel session context request failed: ${response.status}`);
  }
  return (await response.json()) as SentinelSessionContext;
}

export async function setSentinelSessionContext(
  courseId: string,
  topicId: string
): Promise<SentinelSessionContext> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/session-context`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      course_id: courseId.trim(),
      topic_id: topicId.trim(),
    }),
  });
  if (!response.ok) {
    throw new Error(`Set sentinel session context failed: ${response.status}`);
  }
  return (await response.json()) as SentinelSessionContext;
}
