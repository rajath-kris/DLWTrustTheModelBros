<<<<<<< Updated upstream
﻿import type { GapStatus, LearningState } from "./types";
=======
import type {
  ApiErrorShape,
  AskResponse,
  BrainOverviewResponse,
  CourseDeadline,
  CourseDocument,
  GapStatus,
  LearningState,
  QuizSubmitRequest,
  QuizSubmitResponse,
  SentinelRuntimeActionResponse,
  SentinelRuntimeStatus,
  SessionEvent,
} from "./types";
>>>>>>> Stashed changes

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export const emptyState: LearningState = {
  schema_version: 1,
  updated_at: new Date(0).toISOString(),
  captures: [],
  gaps: [],
<<<<<<< Updated upstream
=======
  topics: [],
  question_bank: [],
  quizzes: [],
  courses: [],
  topic_mastery: [],
  study_actions: [],
  deadlines: [],
  documents: [],
  sessions: [],
>>>>>>> Stashed changes
  readiness_axes: {
    concept_mastery: 0,
    deadline_pressure: 0,
    retention_risk: 0,
    problem_transfer: 0,
    consistency: 0,
  },
};

async function parseApiError(response: Response, fallback: string): Promise<never> {
  let parsed: ApiErrorShape | null = null;
  try {
    parsed = (await response.json()) as ApiErrorShape;
  } catch {
    parsed = null;
  }
  const detail = parsed?.detail || fallback;
  const code = parsed?.code ? ` (${parsed.code})` : "";
  throw new Error(`${detail}${code}`);
}

export async function fetchState(): Promise<LearningState> {
  const response = await fetch(`${API_BASE}/api/v1/state`);
  if (!response.ok) {
    await parseApiError(response, `State request failed: ${response.status}`);
  }
  return (await response.json()) as LearningState;
}

<<<<<<< Updated upstream
=======
export async function fetchBrainOverview(courseId: string): Promise<BrainOverviewResponse> {
  const response = await fetch(`${API_BASE}/api/v1/brain/overview?course_id=${encodeURIComponent(courseId)}`);
  if (!response.ok) {
    await parseApiError(response, `Brain overview request failed: ${response.status}`);
  }
  return (await response.json()) as BrainOverviewResponse;
}

>>>>>>> Stashed changes
export async function updateGapStatus(gapId: string, status: GapStatus): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/gaps/${gapId}/status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    await parseApiError(response, `Gap update failed: ${response.status}`);
  }
}

<<<<<<< Updated upstream
=======
export async function submitQuiz(payload: QuizSubmitRequest): Promise<QuizSubmitResponse> {
  const response = await fetch(`${API_BASE}/api/v1/quizzes/submit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await parseApiError(response, `Quiz submit failed: ${response.status}`);
  }
  return (await response.json()) as QuizSubmitResponse;
}

export async function fetchDeadlines(courseId: string): Promise<CourseDeadline[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/deadlines`);
  if (!response.ok) {
    await parseApiError(response, `Deadlines request failed: ${response.status}`);
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
    await parseApiError(response, `Create deadline failed: ${response.status}`);
  }
  return (await response.json()) as CourseDeadline;
}

export async function fetchDocuments(courseId: string): Promise<CourseDocument[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents`);
  if (!response.ok) {
    await parseApiError(response, `Documents request failed: ${response.status}`);
  }
  const data = (await response.json()) as { documents?: CourseDocument[] };
  return Array.isArray(data.documents) ? data.documents : [];
}

export async function uploadDocument(
  courseId: string,
  file: File,
  documentName?: string,
  documentType?: string
): Promise<CourseDocument> {
  const formData = new FormData();
  formData.append("file", file);
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
    await parseApiError(response, `Upload document failed: ${response.status}`);
  }
  return (await response.json()) as CourseDocument;
}

export async function setDocumentAnchor(courseId: string, docId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/${encodeURIComponent(docId)}/anchor`, {
    method: "POST",
  });
  if (!response.ok) {
    await parseApiError(response, `Set anchor failed: ${response.status}`);
  }
}

export async function deleteDocument(courseId: string, docId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    await parseApiError(response, `Delete document failed: ${response.status}`);
  }
}

export async function fetchSessions(courseId: string): Promise<SessionEvent[]> {
  const response = await fetch(`${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}/sessions`);
  if (!response.ok) {
    await parseApiError(response, `Sessions request failed: ${response.status}`);
  }
  const data = (await response.json()) as { sessions?: SessionEvent[] };
  return Array.isArray(data.sessions) ? data.sessions : [];
}

export async function askSentinel(payload: {
  course_id: string;
  thread_id?: string;
  turn_index?: number;
  message: string;
}): Promise<AskResponse> {
  const response = await fetch(`${API_BASE}/api/v1/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await parseApiError(response, `Ask request failed: ${response.status}`);
  }
  return (await response.json()) as AskResponse;
}

>>>>>>> Stashed changes
export function openEventStream(onMessage: (event: MessageEvent) => void): EventSource {
  const stream = new EventSource(`${API_BASE}/api/v1/events/stream`);
  stream.onmessage = onMessage;
  return stream;
}
<<<<<<< Updated upstream
=======

export async function fetchSentinelRuntimeStatus(): Promise<SentinelRuntimeStatus> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime`);
  if (!response.ok) {
    await parseApiError(response, `Sentinel runtime status request failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeStatus;
}

export async function startSentinelRuntime(): Promise<SentinelRuntimeActionResponse> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime/start`, {
    method: "POST",
  });
  if (!response.ok) {
    await parseApiError(response, `Start sentinel runtime failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeActionResponse;
}

export async function stopSentinelRuntime(): Promise<SentinelRuntimeActionResponse> {
  const response = await fetch(`${API_BASE}/api/v1/sentinel/runtime/stop`, {
    method: "POST",
  });
  if (!response.ok) {
    await parseApiError(response, `Stop sentinel runtime failed: ${response.status}`);
  }
  return (await response.json()) as SentinelRuntimeActionResponse;
}
>>>>>>> Stashed changes
