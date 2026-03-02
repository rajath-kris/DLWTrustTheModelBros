export type GapStatus = "open" | "reviewing" | "closed";
export type QuizSourceType = "pyq" | "tutorial" | "sentinel";

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
  course_id?: string;
  topic_id?: string | null;
}

export interface KnowledgeGap {
  gap_id: string;
  concept: string;
  severity: number;
  confidence: number;
  basis_question?: string | null;
  basis_answer_excerpt?: string | null;
  gap_type?: "concept" | "reasoning" | "misconception" | null;
  status: GapStatus;
  capture_id: string;
  evidence_url: string;
  deadline_score: number;
  priority_score: number;
  course_id?: string;
  topic_id?: string | null;
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

export interface TopicCatalogItem {
  topic_id: string;
  course_id: string;
  name: string;
  normalized_name: string;
  source_doc_ids: string[];
  created_at: string;
  updated_at: string;
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
  topic_id: string;
  name: string;
  size_bytes: number;
  type: string;
  uploaded_at: string;
  file_url: string;
  is_anchor: boolean;
}

export interface TopicSummary {
  topic_id: string;
  topic_name: string;
  material_count: number;
  created_at: string;
  updated_at: string;
}

export interface TopicListResponse {
  topics: TopicSummary[];
  active_topic_id: string | null;
}

export interface ActiveTopicResponse {
  active_topic_id: string | null;
  active_topic_name: string | null;
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
}

export interface QuestionBankItem {
  question_id: string;
  topic: string;
  source: QuizSourceType;
  concept: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation?: string | null;
  course_id: string;
  topic_id?: string | null;
  origin_doc_id?: string | null;
  origin_topic_id?: string | null;
  generated?: boolean;
}

export interface QuizQuestionResult {
  question_id: string;
  topic: string;
  source: QuizSourceType;
  concept: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
}

export interface QuizRecord {
  quiz_id: string;
  timestamp_utc: string;
  topic: string;
  sources: QuizSourceType[];
  total_questions: number;
  correct_answers: number;
  score: number;
  results: QuizQuestionResult[];
  course_id: string;
  topic_id?: string | null;
}

export interface TopicUpdate {
  topic: string;
  before_mastery: number;
  after_mastery: number;
  delta: number;
}

export interface QuizSubmitRequest {
  topic: string;
  sources: QuizSourceType[];
  answers: Array<{
    question_id: string;
    user_answer: string;
  }>;
  course_id?: string;
  topic_id?: string;
  session_id?: string;
}

export interface QuizSubmitResponse {
  quiz: QuizRecord;
  readiness_axes: ReadinessAxes;
  topic_updates: TopicUpdate[];
  new_gap_ids: string[];
}

export interface QuizPrepareRequest {
  topic: string;
  sources: QuizSourceType[];
  question_count: number;
  course_id?: string;
  topic_id?: string;
}

export interface QuizSelectionSummary {
  gap_matched_count: number;
  wrong_repeat_count: number;
  deadline_boosted_count: number;
  coverage_count: number;
}

export interface QuizPrepareResponse {
  session_id: string;
  topic: string;
  questions: QuestionBankItem[];
  selection_summary: QuizSelectionSummary;
}

export interface LearningState {
  updated_at: string;
  captures: CaptureEvent[];
  gaps: KnowledgeGap[];
  courses: CourseSummary[];
  topic_mastery: TopicMasteryItem[];
  topics: TopicCatalogItem[];
  study_actions: StudyAction[];
  deadlines: CourseDeadline[];
  documents: CourseDocument[];
  sessions: SessionEvent[];
  question_bank: QuestionBankItem[];
  quizzes: QuizRecord[];
  readiness_axes: ReadinessAxes;
}

export interface BrainOverviewResponse {
  course_id: string;
  state: LearningState;
}

export interface ServerEventEnvelope {
  type: string;
  payload: {
    state?: LearningState;
    gap_id?: string;
    status?: GapStatus;
  };
}

export interface SentinelRuntimeStatus {
  running: boolean;
  process_count: number;
  detected_pids: number[];
  managed_pids: number[];
  last_action: "none" | "start" | "stop";
  last_action_at: string | null;
  last_error: string | null;
}

export interface SentinelRuntimeActionResponse {
  ok: boolean;
  action: "start" | "stop";
  message: string | null;
  stopped_count: number | null;
  failed_count: number | null;
  status: SentinelRuntimeStatus;
}
