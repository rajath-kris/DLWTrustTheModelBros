import type { CourseData } from "../data/courses";
import type {
  CaptureEvent,
  LearningState,
  QuestionBankItem,
  QuizQuestionResult,
  QuizRecord,
  ReadinessAxes,
  TopicMastery,
} from "../types";

const SCHEMA_VERSION = 1;

const MOCK_QUESTION_BANK: QuestionBankItem[] = [
  {
    id: "q-tree-postorder",
    topic: "Binary Trees & Traversal",
    type: "MCQ",
    question_text: "Which traversal visits the root node last?",
    options: ["In-order", "Pre-order", "Post-order", "Level-order"],
    correct_answer: "Post-order",
    source: "PYQ_2025_Q3",
    source_type: "pyq",
    captured_from_sentinel: false,
    concept: "Tree Traversals",
  },
  {
    id: "q-tree-height",
    topic: "Binary Trees & Traversal",
    type: "MCQ",
    question_text: "What is the maximum number of nodes in a binary tree of height h (root at height 0)?",
    options: ["2^h - 1", "2^(h+1) - 1", "2h", "h^2"],
    correct_answer: "2^(h+1) - 1",
    source: "CS2040_Tutorial_3_Q1",
    source_type: "tutorial",
    captured_from_sentinel: false,
    concept: "Tree Properties",
  },
  {
    id: "q-dp-overlap",
    topic: "Dynamic Programming",
    type: "MCQ",
    question_text: "Dynamic programming is most effective when a problem has:",
    options: [
      "Greedy-choice only",
      "Overlapping subproblems and optimal substructure",
      "No recursion",
      "Only sorted input",
    ],
    correct_answer: "Overlapping subproblems and optimal substructure",
    source: "CS2040_Tutorial_6_Q2",
    source_type: "tutorial",
    captured_from_sentinel: false,
    concept: "DP Fundamentals",
  },
  {
    id: "q-graph-bfs",
    topic: "Graph Algorithms",
    type: "MCQ",
    question_text: "Which data structure is typically used in BFS?",
    options: ["Stack", "Queue", "Priority Queue", "Set"],
    correct_answer: "Queue",
    source: "SENTINEL_CAPTURE_12",
    source_type: "sentinel",
    captured_from_sentinel: true,
    concept: "BFS",
  },
];

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function toReadinessAxes(courseData: CourseData): ReadinessAxes {
  const mastery = clamp01(courseData.stats.masteryPercent / 100);
  return {
    concept_mastery: mastery,
    deadline_pressure: clamp01(1 - (courseData.stats.nearestDeadlineReadiness / 100)),
    retention_risk: clamp01(courseData.stats.activeGaps * 0.08),
    problem_transfer: clamp01(mastery - 0.1),
    consistency: clamp01(0.72 + (courseData.stats.sentinelSessionsThisWeek / 100)),
  };
}

function toTopics(courseData: CourseData): TopicMastery[] {
  return courseData.topicScores.map((topic, idx) => ({
    topic_id: `${courseData.id}-topic-${idx + 1}`,
    name: topic.name,
    mastery_score: clamp01(topic.current),
  }));
}

function toCaptures(courseData: CourseData): CaptureEvent[] {
  return courseData.sessions.map((session) => ({
    capture_id: session.id,
    timestamp_utc: session.timestamp_utc,
    app_name: "Sentinel Desktop",
    window_title: session.topic,
    socratic_prompt: session.summary,
    gaps: session.gap_id ? [session.gap_id] : [],
  }));
}

function mockQuizQuestion(question: QuestionBankItem): QuizQuestionResult {
  return {
    question_id: question.id,
    question_text: question.question_text,
    options: question.options,
    correct_answer: question.correct_answer,
    user_answer: question.correct_answer,
    is_correct: true,
    source: question.source,
    concept: question.concept,
  };
}

function mockQuizHistory(courseData: CourseData): QuizRecord[] {
  const questions = MOCK_QUESTION_BANK
    .filter((item) => item.topic.toLowerCase().includes(courseData.id === "cs2040" ? "" : ""))
    .slice(0, 2);

  return [
    {
      id: `${courseData.id}-quiz-seed-1`,
      topic: courseData.topicScores[0]?.name ?? "General",
      date_taken: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      sources: ["pyq", "tutorial"],
      score: { correct: 2, total: 3 },
      questions: questions.map(mockQuizQuestion),
      mastery_delta: 0.03,
      generated_gap_ids: [],
    },
  ];
}

export function buildLearningStateFromCourseData(courseData: CourseData): LearningState {
  return {
    schema_version: SCHEMA_VERSION,
    updated_at: new Date().toISOString(),
    captures: toCaptures(courseData),
    gaps: courseData.gaps,
    topics: toTopics(courseData),
    question_bank: MOCK_QUESTION_BANK,
    quizzes: mockQuizHistory(courseData),
    readiness_axes: toReadinessAxes(courseData),
  };
}

export function buildLearningStateFromAllCourses(dataByCourse: CourseData[]): LearningState {
  const topicsByName = new Map<string, TopicMastery[]>();
  const merged: LearningState = {
    schema_version: SCHEMA_VERSION,
    updated_at: new Date().toISOString(),
    captures: [],
    gaps: [],
    topics: [],
    question_bank: MOCK_QUESTION_BANK,
    quizzes: [],
    readiness_axes: {
      concept_mastery: 0,
      deadline_pressure: 0,
      retention_risk: 0,
      problem_transfer: 0,
      consistency: 0,
    },
  };

  for (const course of dataByCourse) {
    const state = buildLearningStateFromCourseData(course);
    merged.captures.push(...state.captures);
    merged.gaps.push(...state.gaps);
    merged.quizzes.push(...state.quizzes);
    for (const topic of state.topics) {
      const arr = topicsByName.get(topic.name) ?? [];
      arr.push(topic);
      topicsByName.set(topic.name, arr);
    }
  }

  merged.topics = Array.from(topicsByName.entries()).map(([name, values], idx) => ({
    topic_id: `all-topic-${idx + 1}`,
    name,
    mastery_score: clamp01(values.reduce((sum, item) => sum + item.mastery_score, 0) / values.length),
  }));

  merged.readiness_axes = {
    concept_mastery: clamp01(merged.topics.reduce((sum, item) => sum + item.mastery_score, 0) / Math.max(merged.topics.length, 1)),
    deadline_pressure: clamp01(Math.max(...dataByCourse.map((course) => 1 - (course.stats.nearestDeadlineReadiness / 100)))),
    retention_risk: clamp01(merged.gaps.filter((gap) => gap.status !== "closed").length * 0.06),
    problem_transfer: clamp01((merged.topics.reduce((sum, item) => sum + item.mastery_score, 0) / Math.max(merged.topics.length, 1)) - 0.12),
    consistency: 0.8,
  };

  return merged;
}

