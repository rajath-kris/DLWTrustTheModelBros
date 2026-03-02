/**
 * Quiz Engine: single source of truth for quiz scoring, mastery updates,
 * and knowledge gap identification. Used by mock flow and can be extended
 * for backend-aligned calculations.
 */

import type {
  QuestionBankItem,
  QuizQuestionResult,
  QuizRecord,
  QuizSourceType,
  QuizSubmitResponse,
  TopicUpdate,
  ReadinessAxes,
} from "../types";
import { MOCK_INITIAL_MASTERY } from "../data/mockQuizData";

const DEFAULT_READINESS: ReadinessAxes = {
  concept_mastery: 0.5,
  deadline_pressure: 0.3,
  retention_risk: 0.4,
  problem_transfer: 0.45,
  consistency: 0.5,
};

function normalized(s: string): string {
  return s.trim().toLowerCase();
}

export interface ScoreResult {
  results: QuizQuestionResult[];
  correctCount: number;
  byTopic: Map<string, { correct: number; total: number }>;
  byConcept: Map<string, { correct: number; total: number }>;
}

/**
 * Calculate score and per-topic/per-concept breakdown from questions and answers.
 */
export function calculateScore(
  questions: QuestionBankItem[],
  answers: Record<string, string>
): ScoreResult {
  const results: QuizQuestionResult[] = [];
  const byTopic = new Map<string, { correct: number; total: number }>();
  const byConcept = new Map<string, { correct: number; total: number }>();
  let correctCount = 0;

  for (const q of questions) {
    const userAnswer = answers[q.question_id] ?? "";
    const isCorrect = normalized(userAnswer) === normalized(q.correct_answer);
    if (isCorrect) correctCount++;
    results.push({
      question_id: q.question_id,
      topic: q.topic,
      source: q.source,
      concept: q.concept,
      user_answer: userAnswer,
      correct_answer: q.correct_answer,
      is_correct: isCorrect,
    });
    const tCur = byTopic.get(q.topic) ?? { correct: 0, total: 0 };
    tCur.total++;
    if (isCorrect) tCur.correct++;
    byTopic.set(q.topic, tCur);
    const cCur = byConcept.get(q.concept) ?? { correct: 0, total: 0 };
    cCur.total++;
    if (isCorrect) cCur.correct++;
    byConcept.set(q.concept, cCur);
  }

  return { results, correctCount, byTopic, byConcept };
}

/**
 * Compute topic mastery updates from performance. Uses initial mastery and
 * applies weighted delta from correct/incorrect ratio per topic.
 */
export function updateMastery(
  byTopic: Map<string, { correct: number; total: number }>,
  initialMastery: Record<string, number> = MOCK_INITIAL_MASTERY
): TopicUpdate[] {
  const topicUpdates: TopicUpdate[] = [];
  for (const [topic, { correct, total }] of byTopic) {
    const before = initialMastery[topic] ?? 0.5;
    const delta = total > 0 ? (correct / total) * 0.25 - (1 - correct / total) * 0.2 : 0;
    const after = Math.max(0, Math.min(1, before + delta));
    topicUpdates.push({
      topic,
      before_mastery: before,
      after_mastery: after,
      delta: after - before,
    });
  }
  return topicUpdates;
}

/**
 * Identify new knowledge gap IDs from wrong answers (one per topic that had wrong answers).
 */
export function identifyKnowledgeGaps(
  questions: QuestionBankItem[],
  answers: Record<string, string>,
  byTopic: Map<string, { correct: number; total: number }>
): string[] {
  const newGapIds: string[] = [];
  for (const [topic, { correct, total }] of byTopic) {
    if (correct >= total) continue;
    const wrongQ = questions.find(
      (q) => q.topic === topic && normalized(answers[q.question_id] ?? "") !== normalized(q.correct_answer)
    );
    if (wrongQ) newGapIds.push(`mock-gap-${wrongQ.question_id}-${Date.now()}`);
  }
  return newGapIds;
}

/**
 * Generate full QuizSubmitResponse from questions, answers, and config.
 * Single entry point for mock submit flow.
 */
export function generateSubmitResponse(
  questions: QuestionBankItem[],
  answers: Record<string, string>,
  topic: string,
  sources: QuizSourceType[],
  courseId: string
): QuizSubmitResponse {
  const { results, correctCount, byTopic } = calculateScore(questions, answers);
  const topic_updates = updateMastery(byTopic);
  const new_gap_ids = identifyKnowledgeGaps(questions, answers, byTopic);

  const quizRecord: QuizRecord = {
    quiz_id: `mock-quiz-${Date.now()}`,
    timestamp_utc: new Date().toISOString(),
    topic,
    sources,
    total_questions: questions.length,
    correct_answers: correctCount,
    score: questions.length > 0 ? correctCount / questions.length : 0,
    results,
    course_id: courseId,
  };

  return {
    quiz: quizRecord,
    readiness_axes: DEFAULT_READINESS,
    topic_updates,
    new_gap_ids,
  };
}
