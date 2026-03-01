import type { GapStatus, LearningState } from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export const emptyState: LearningState = {
  updated_at: new Date(0).toISOString(),
  captures: [],
  gaps: [],
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

export function openEventStream(onMessage: (event: MessageEvent) => void): EventSource {
  const stream = new EventSource(`${API_BASE}/api/v1/events/stream`);
  stream.onmessage = onMessage;
  return stream;
}
