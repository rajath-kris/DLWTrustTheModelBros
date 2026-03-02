export type GapStatus = "open" | "reviewing" | "closed";

export interface ReadinessAxes {
  concept_mastery: number;
  deadline_pressure: number;
  retention_risk: number;
  problem_transfer: number;
  consistency: number;
}

export type QuizSourceType = "pyq" | "tutorial" | "sentinel";

export interface CaptureEvent {
  capture_id: string;
  timestamp_utc: string;
  app_name: string;
  window_title: string;
  socratic_prompt: string;
  gaps: string[];
}

export interface TopicMastery {
  topic_id: string;
  name: string;
  mastery_score: number;
}

export interface QuestionBankItem {
  id: string;
  topic: string;
  type: "MCQ";
  question_text: string;
  options: string[];
  correct_answer: string;
  source: string;
  source_type: QuizSourceType;
  captured_from_sentinel: boolean;
  concept: string;
}

export interface QuizQuestionResult {
  question_id: string;
  question_text: string;
  options: string[];
  correct_answer: string;
  user_answer: string;
  is_correct: boolean;
  source: string;
  concept: string;
}

export interface QuizRecord {
  id: string;
  topic: string;
  date_taken: string;
  sources: QuizSourceType[];
  score: {
    correct: number;
    total: number;
  };
  questions: QuizQuestionResult[];
  mastery_delta: number;
  generated_gap_ids: string[];
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
  schema_version: number;
  updated_at: string;
  captures: CaptureEvent[];
  gaps: KnowledgeGap[];
  topics: TopicMastery[];
  question_bank: QuestionBankItem[];
  quizzes: QuizRecord[];
  readiness_axes: ReadinessAxes;
}

export interface QuizSubmissionRequest {
  topic: string;
  sources: QuizSourceType[];
  answers: Array<{
    question_id: string;
    user_answer: string;
  }>;
}

export interface QuizSubmissionResponse {
  schema_version: number;
  quiz: QuizRecord;
  readiness_axes: ReadinessAxes;
  topic_updates: TopicMastery[];
  new_gap_ids: string[];
}

export interface APIErrorResponse {
  detail: string;
  code: string;
}

export interface ServerEventEnvelope {
  type: string;
  payload: {
    state?: LearningState;
    gap_id?: string;
    status?: GapStatus;
  };
}
