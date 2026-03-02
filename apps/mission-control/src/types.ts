<<<<<<< Updated upstream
﻿export type GapStatus = "open" | "reviewing" | "closed";
=======
export type GapStatus = "open" | "reviewing" | "closed";
export type QuestionSource = "pyq" | "tutorial" | "sentinel";
export type LearningDataSource = "mock" | "bridge";

export interface ApiErrorShape {
  detail: string;
  code: string;
}
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
=======
  course_id?: string;
}

export interface TopicMastery {
  topic: string;
  mastery: number;
  momentum: number;
  last_updated: string;
}

export interface QuestionBankItem {
  question_id: string;
  topic: string;
  source: QuestionSource;
  concept: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation?: string | null;
}

export interface QuizQuestionResult {
  question_id: string;
  topic: string;
  source: QuestionSource;
  concept: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
}

export interface QuizRecord {
  quiz_id: string;
  timestamp_utc: string;
  topic: string;
  sources: QuestionSource[];
  total_questions: number;
  correct_answers: number;
  score: number;
  results: QuizQuestionResult[];
}

export interface TopicUpdate {
  topic: string;
  before_mastery: number;
  after_mastery: number;
  delta: number;
}

export interface QuizSubmitRequest {
  topic: string;
  sources: QuestionSource[];
  answers: Array<{ question_id: string; user_answer: string }>;
}

export interface QuizSubmitResponse {
  schema_version: number;
  quiz: QuizRecord;
  readiness_axes: ReadinessAxes;
  topic_updates: TopicUpdate[];
  new_gap_ids: string[];
}

export interface CourseSummary {
  course_id: string;
  course_name: string;
}

export interface TopicMasteryItem {
  topic_id: string;
  course_id: string;
  name: string;
  current: number;
  target: number;
  open_gaps: number;
}

export interface StudyAction {
  action_id: string;
  course_id: string;
  topic_id: string;
  title: string;
  rationale: string;
  eta_minutes: number;
  priority: number;
  source_gap_ids: string[];
}

export interface CourseDeadline {
  deadline_id: string;
  course_id: string;
  name: string;
  due_date: string;
  readiness_score: number;
  associated_gap_ids: string[];
}

export interface CourseDocument {
  doc_id: string;
  course_id: string;
  name: string;
  size_bytes: number;
  type: string;
  uploaded_at: string;
  file_url: string;
  is_anchor: boolean;
}

export interface SessionEvent {
  session_id: string;
  course_id: string;
  thread_id: string;
  turn_index: number;
  timestamp_utc: string;
  summary: string;
  topic: string;
  gap_ids: string[];
  capture_id?: string | null;
>>>>>>> Stashed changes
}

export interface LearningState {
  schema_version: number;
  updated_at: string;
  captures: CaptureEvent[];
  gaps: KnowledgeGap[];
<<<<<<< Updated upstream
  readiness_axes: ReadinessAxes;
=======
  topics: TopicMastery[];
  question_bank: QuestionBankItem[];
  quizzes: QuizRecord[];
  readiness_axes: ReadinessAxes;
  courses: CourseSummary[];
  topic_mastery: TopicMasteryItem[];
  study_actions: StudyAction[];
  deadlines: CourseDeadline[];
  documents: CourseDocument[];
  sessions: SessionEvent[];
>>>>>>> Stashed changes
}

export interface ServerEventEnvelope {
  type: string;
  payload: {
    state?: LearningState;
    gap_id?: string;
    status?: GapStatus;
  };
}
