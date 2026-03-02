import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { submitQuiz as submitQuizApi, fetchState as fetchStateApi } from "../api";
import { buildLearningStateFromAllCourses, buildLearningStateFromCourseData } from "../adapters/learningStateAdapter";
import { useCourse } from "./CourseContext";
import type { LearningState, QuizSubmissionRequest, QuizSubmissionResponse } from "../types";

export type StateSource = "mock" | "bridge";

interface StateContextValue {
  source: StateSource;
  setSource: (source: StateSource) => void;
  state: LearningState | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  submitQuiz: (payload: QuizSubmissionRequest) => Promise<QuizSubmissionResponse>;
}

const StateContext = createContext<StateContextValue | null>(null);

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function clampRange(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function envDefaultSource(): StateSource {
  const raw = (import.meta.env.VITE_STATE_SOURCE as string | undefined)?.toLowerCase();
  return raw === "bridge" ? "bridge" : "mock";
}

function simulateQuizSubmission(state: LearningState, payload: QuizSubmissionRequest): { next: LearningState; response: QuizSubmissionResponse } {
  const questions = payload.answers
    .map((answer) => {
      const question = state.question_bank.find((item) => item.id === answer.question_id);
      if (!question) return null;
      const isCorrect = answer.user_answer.trim().toLowerCase() === question.correct_answer.trim().toLowerCase();
      return {
        question_id: question.id,
        question_text: question.question_text,
        options: question.options,
        correct_answer: question.correct_answer,
        user_answer: answer.user_answer,
        is_correct: isCorrect,
        source: question.source,
        concept: question.concept,
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);

  const correct = questions.filter((item) => item.is_correct).length;
  const total = Math.max(questions.length, 1);
  const accuracy = correct / total;

  const topic = state.topics.find((item) => item.name.toLowerCase() === payload.topic.toLowerCase()) ?? state.topics[0];
  const delta = clampRange((accuracy - 0.6) * 0.18, -0.08, 0.08);
  const updatedTopic = topic
    ? { ...topic, mastery_score: clamp01(topic.mastery_score + delta) }
    : { topic_id: "mock-topic", name: payload.topic, mastery_score: clamp01(0.6 + delta) };

  const quizId = `mock-quiz-${Date.now()}`;
  const quiz = {
    id: quizId,
    topic: payload.topic,
    date_taken: new Date().toISOString(),
    sources: payload.sources,
    score: { correct, total },
    questions,
    mastery_delta: delta,
    generated_gap_ids: [] as string[],
  };

  const next: LearningState = {
    ...state,
    updated_at: new Date().toISOString(),
    topics: [
      ...state.topics.filter((item) => item.topic_id !== updatedTopic.topic_id),
      updatedTopic,
    ],
    quizzes: [quiz, ...state.quizzes],
    readiness_axes: {
      ...state.readiness_axes,
      concept_mastery: clamp01((state.readiness_axes.concept_mastery * 0.6) + (updatedTopic.mastery_score * 0.4)),
      problem_transfer: clamp01((state.readiness_axes.problem_transfer * 0.7) + (updatedTopic.mastery_score * 0.3) - 0.05),
    },
  };

  const response: QuizSubmissionResponse = {
    schema_version: state.schema_version,
    quiz,
    readiness_axes: next.readiness_axes,
    topic_updates: [updatedTopic],
    new_gap_ids: [],
  };

  return { next, response };
}

export function StateProvider({ children }: { children: React.ReactNode }) {
  const { courseId, courseData, allCoursesSummary } = useCourse();
  const [source, setSource] = useState<StateSource>(envDefaultSource);
  const [state, setState] = useState<LearningState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mockState = useMemo(() => {
    if (courseId === "all") return buildLearningStateFromAllCourses(allCoursesSummary.map((item) => item.data));
    if (!courseData) return null;
    return buildLearningStateFromCourseData(courseData);
  }, [allCoursesSummary, courseData, courseId]);

  async function loadBridgeState() {
    try {
      setLoading(true);
      setError(null);
      const payload = await fetchStateApi();
      setState(payload);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load bridge state");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (source === "mock") {
      setState(mockState);
      setLoading(false);
      setError(null);
      return;
    }
    void loadBridgeState();
  }, [mockState, source]);

  async function reload() {
    if (source === "mock") {
      setState(mockState);
      return;
    }
    await loadBridgeState();
  }

  async function submitQuiz(payload: QuizSubmissionRequest): Promise<QuizSubmissionResponse> {
    if (source === "bridge") {
      const response = await submitQuizApi(payload);
      await loadBridgeState();
      return response;
    }
    const baseline = state ?? mockState;
    if (!baseline) {
      throw new Error("No state available");
    }
    const { next, response } = simulateQuizSubmission(baseline, payload);
    setState(next);
    return response;
  }

  const value = useMemo<StateContextValue>(() => ({
    source,
    setSource,
    state,
    loading,
    error,
    reload,
    submitQuiz,
  }), [source, state, loading, error]);

  return <StateContext.Provider value={value}>{children}</StateContext.Provider>;
}

export function useLearningState(): StateContextValue {
  const ctx = useContext(StateContext);
  if (!ctx) throw new Error("useLearningState must be used within StateProvider");
  return ctx;
}
