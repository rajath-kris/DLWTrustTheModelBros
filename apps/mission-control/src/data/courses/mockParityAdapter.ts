import { emptyState } from "../../api";
import type { LearningState, QuizRecord, TopicMastery } from "../../types";
import { COURSES, getCourseData } from "./index";

function nowIso(): string {
  return new Date().toISOString();
}

export function buildMockLearningState(): LearningState {
  const state: LearningState = {
    ...emptyState,
    schema_version: 1,
    updated_at: nowIso(),
    courses: COURSES.map((course) => ({
      course_id: course.id,
      course_name: course.name,
    })),
  };

  const topicMap = new Map<string, TopicMastery>();
  const quizHistory: QuizRecord[] = [];

  for (const course of COURSES) {
    const data = getCourseData(course.id);
    if (!data) {
      continue;
    }

    state.gaps.push(
      ...data.gaps.map((gap) => ({
        ...gap,
        course_id: course.id,
      }))
    );

    const captureKeys = Object.keys(data.captureTimestamps ?? {});
    for (const captureId of captureKeys) {
      const timestamp = data.captureTimestamps?.[captureId] ?? nowIso();
      state.captures.push({
        capture_id: captureId,
        timestamp_utc: timestamp,
        app_name: "Mock Study App",
        window_title: `${course.name} notes`,
        socratic_prompt: "What assumption are you making before selecting this method?",
        gaps: data.gaps.filter((g) => g.capture_id === captureId).map((g) => g.gap_id),
        course_id: course.id,
      });
    }

    for (const topic of data.topicScores) {
      topicMap.set(`${course.id}:${topic.name.toLowerCase()}`, {
        topic: topic.name,
        mastery: topic.current,
        momentum: topic.current - topic.target,
        last_updated: nowIso(),
      });
    }

    for (const topic of data.topicScores.slice(0, 2)) {
      state.question_bank.push({
        question_id: `${course.id}-${topic.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        topic: topic.name,
        source: "tutorial",
        concept: topic.label,
        question: `Which statement best improves mastery in ${topic.label}?`,
        options: [
          "Practice one worked example then explain it aloud",
          "Memorize final answers only",
          "Skip error review",
          "Avoid previous year questions",
        ],
        correct_answer: "Practice one worked example then explain it aloud",
        explanation: "Active recall plus worked examples improves retention and transfer.",
      });
    }

    quizHistory.push({
      quiz_id: `${course.id}-quiz-seed`,
      timestamp_utc: nowIso(),
      topic: data.topicScores[0]?.name ?? "General",
      sources: ["tutorial"],
      total_questions: 2,
      correct_answers: 1,
      score: 0.5,
      results: [
        {
          question_id: `${course.id}-${(data.topicScores[0]?.label ?? "topic").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
          topic: data.topicScores[0]?.name ?? "General",
          source: "tutorial",
          concept: data.topicScores[0]?.label ?? "Concept",
          user_answer: "Practice one worked example then explain it aloud",
          correct_answer: "Practice one worked example then explain it aloud",
          is_correct: true,
        },
        {
          question_id: `${course.id}-${(data.topicScores[1]?.label ?? "topic").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
          topic: data.topicScores[1]?.name ?? "General",
          source: "tutorial",
          concept: data.topicScores[1]?.label ?? "Concept",
          user_answer: "Memorize final answers only",
          correct_answer: "Practice one worked example then explain it aloud",
          is_correct: false,
        },
      ],
    });
  }

  state.topics = Array.from(topicMap.values());
  state.quizzes = quizHistory;
  state.readiness_axes = {
    concept_mastery: 0.64,
    deadline_pressure: 0.46,
    retention_risk: 0.38,
    problem_transfer: 0.61,
    consistency: 0.7,
  };
  return state;
}
