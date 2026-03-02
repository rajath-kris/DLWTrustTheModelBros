import type {
  APIErrorResponse,
  GapStatus,
  LearningState,
  QuizSubmissionRequest,
  QuizSubmissionResponse,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export const emptyState: LearningState = {
  schema_version: 1,
  updated_at: new Date(0).toISOString(),
  captures: [],
  gaps: [],
  topics: [],
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

async function toAPIError(response: Response, fallbackCode: string): Promise<Error> {
  try {
    const body = (await response.json()) as Partial<APIErrorResponse>;
    const code = body.code ?? fallbackCode;
    const detail = body.detail ?? `Request failed (${response.status})`;
    return new Error(`[${code}] ${detail}`);
  } catch {
    return new Error(`[${fallbackCode}] Request failed: ${response.status}`);
  }
}

export async function fetchState(): Promise<LearningState> {
  const response = await fetch(`${API_BASE}/api/v1/state`);
  if (!response.ok) {
    throw await toAPIError(response, "STATE_REQUEST_FAILED");
  }
  return (await response.json()) as LearningState;
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
    throw await toAPIError(response, "GAP_UPDATE_FAILED");
  }
}

export async function submitQuiz(payload: QuizSubmissionRequest): Promise<QuizSubmissionResponse> {
  const response = await fetch(`${API_BASE}/api/v1/quizzes/submit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await toAPIError(response, "QUIZ_SUBMISSION_FAILED");
  }

  return (await response.json()) as QuizSubmissionResponse;
}

export function openEventStream(onMessage: (event: MessageEvent) => void): EventSource {
  const stream = new EventSource(`${API_BASE}/api/v1/events/stream`);
  stream.onmessage = onMessage;
  return stream;
}
