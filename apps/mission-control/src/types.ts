export type GapStatus = "open" | "reviewing" | "closed";

export interface ReadinessAxes {
  concept_mastery: number;
  deadline_pressure: number;
  retention_risk: number;
  problem_transfer: number;
  consistency: number;
}

export interface CaptureEvent {
  capture_id: string;
  timestamp_utc: string;
  app_name: string;
  window_title: string;
  socratic_prompt: string;
  gaps: string[];
}

export interface KnowledgeGap {
  gap_id: string;
  concept: string;
  severity: number;
  confidence: number;
  status: GapStatus;
  capture_id: string;
  evidence_url: string;
  deadline_score: number;
  priority_score: number;
}

export interface LearningState {
  updated_at: string;
  captures: CaptureEvent[];
  gaps: KnowledgeGap[];
  readiness_axes: ReadinessAxes;
}

export interface ServerEventEnvelope {
  type: string;
  payload: {
    state?: LearningState;
    gap_id?: string;
    status?: GapStatus;
  };
}
