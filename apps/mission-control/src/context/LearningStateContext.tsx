import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { emptyState, fetchState, openEventStream, submitQuiz as submitQuizApi, updateGapStatus } from "../api";
import { buildMockLearningState } from "../data/courses/mockParityAdapter";
import type {
  GapStatus,
  LearningDataSource,
  LearningState,
  QuizSubmitRequest,
  QuizSubmitResponse,
  TopicUpdate,
} from "../types";

interface LearningStateContextValue {
  dataSource: LearningDataSource;
  setDataSource: (value: LearningDataSource) => void;
  state: LearningState;
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
  refreshState: () => Promise<void>;
  setGapStatus: (gapId: string, status: GapStatus) => Promise<void>;
  submitQuiz: (request: QuizSubmitRequest) => Promise<QuizSubmitResponse>;
}

const STORAGE_KEY = "mission-control-data-source";
const LearningStateContext = createContext<LearningStateContextValue | null>(null);

function readStoredDataSource(): LearningDataSource {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw === "bridge" ? "bridge" : "mock";
}

function normalizeText(raw: string): string {
  return raw.trim().toLowerCase();
}

export function StateProvider({ children }: { children: React.ReactNode }) {
  const [dataSource, setDataSourceState] = useState<LearningDataSource>(() => readStoredDataSource());
  const [state, setState] = useState<LearningState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveAvailable, setLiveAvailable] = useState(false);

  const refreshState = useCallback(async () => {
    if (dataSource === "mock") {
      setState(buildMockLearningState());
      setError(null);
      setLiveAvailable(false);
      return;
    }
    const fresh = await fetchState();
    setState(fresh);
    setError(null);
    setLiveAvailable(true);
  }, [dataSource]);

  useEffect(() => {
    let mounted = true;
    let stream: EventSource | null = null;

    async function hydrate() {
      try {
        await refreshState();
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Could not load learning state.");
        setLiveAvailable(false);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    setLoading(true);
    hydrate();

    if (dataSource === "bridge") {
      stream = openEventStream((message) => {
        try {
          const parsed = JSON.parse(message.data) as { payload?: { state?: LearningState } };
          if (parsed.payload?.state) {
            setState(parsed.payload.state);
            setError(null);
            setLiveAvailable(true);
          }
        } catch {
          // Ignore malformed stream events.
        }
      });
      stream.onerror = () => {
        if (!mounted) return;
        setLiveAvailable(false);
        setError("Live stream disconnected. Data may be stale.");
      };
    }

    return () => {
      mounted = false;
      stream?.close();
    };
  }, [dataSource, refreshState]);

  const setDataSource = useCallback((value: LearningDataSource) => {
    window.localStorage.setItem(STORAGE_KEY, value);
    setDataSourceState(value);
  }, []);

  const setGapStatusAction = useCallback(
    async (gapId: string, status: GapStatus) => {
      if (dataSource === "bridge") {
        await updateGapStatus(gapId, status);
        await refreshState();
        return;
      }

      setState((prev) => ({
        ...prev,
        updated_at: new Date().toISOString(),
        gaps: prev.gaps.map((gap) => (gap.gap_id === gapId ? { ...gap, status } : gap)),
      }));
    },
    [dataSource, refreshState]
  );

  const submitQuiz = useCallback(
    async (request: QuizSubmitRequest): Promise<QuizSubmitResponse> => {
      if (dataSource === "bridge") {
        const response = await submitQuizApi(request);
        await refreshState();
        return response;
      }

      const topicQuestions = state.question_bank.filter(
        (item) => normalizeText(item.topic) === normalizeText(request.topic) && request.sources.includes(item.source)
      );
      const answersById = new Map(request.answers.map((a) => [a.question_id, a.user_answer]));
      const results = topicQuestions
        .filter((item) => answersById.has(item.question_id))
        .map((item) => {
          const userAnswer = answersById.get(item.question_id) ?? "";
          return {
            question_id: item.question_id,
            topic: item.topic,
            source: item.source,
            concept: item.concept,
            user_answer: userAnswer,
            correct_answer: item.correct_answer,
            is_correct: normalizeText(userAnswer) === normalizeText(item.correct_answer),
          };
        });

      if (results.length === 0) {
        throw new Error("No quiz answers matched selected question bank items.");
      }

      const correct = results.filter((r) => r.is_correct).length;
      const score = correct / results.length;
      const quiz = {
        quiz_id: `mock-quiz-${Date.now()}`,
        timestamp_utc: new Date().toISOString(),
        topic: request.topic,
        sources: request.sources,
        total_questions: results.length,
        correct_answers: correct,
        score,
        results,
      };

      const topicBefore = state.topics.find((topic) => normalizeText(topic.topic) === normalizeText(request.topic));
      const before = topicBefore?.mastery ?? 0.5;
      const after = Math.max(0, Math.min(1, before + (score - 0.5) * 0.2));
      const topicUpdate: TopicUpdate = {
        topic: request.topic,
        before_mastery: before,
        after_mastery: after,
        delta: after - before,
      };

      const newGapIds: string[] = [];
      const newGaps = results
        .filter((result) => !result.is_correct)
        .map((result) => {
          const gapId = `mock-gap-${Date.now()}-${result.question_id}`;
          newGapIds.push(gapId);
          return {
            gap_id: gapId,
            concept: `${result.topic}: ${result.concept}`,
            severity: 0.55,
            confidence: 0.72,
            gap_type: "concept" as const,
            status: "open" as const,
            capture_id: quiz.quiz_id,
            evidence_url: "#",
            deadline_score: 0.4,
            priority_score: 0.58,
            course_id: "all",
            basis_question: `Quiz miss ${result.question_id}`,
            basis_answer_excerpt: result.user_answer,
          };
        });

      setState((prev) => ({
        ...prev,
        updated_at: new Date().toISOString(),
        quizzes: [...prev.quizzes, quiz],
        gaps: [...prev.gaps, ...newGaps],
        topics: prev.topics.some((topic) => normalizeText(topic.topic) === normalizeText(request.topic))
          ? prev.topics.map((topic) =>
              normalizeText(topic.topic) === normalizeText(request.topic)
                ? { ...topic, mastery: after, momentum: after - before, last_updated: new Date().toISOString() }
                : topic
            )
          : [...prev.topics, { topic: request.topic, mastery: after, momentum: after - before, last_updated: new Date().toISOString() }],
      }));

      return {
        schema_version: 1,
        quiz,
        readiness_axes: state.readiness_axes,
        topic_updates: [topicUpdate],
        new_gap_ids: newGapIds,
      };
    },
    [dataSource, refreshState, state.question_bank, state.topics, state.readiness_axes]
  );

  const value = useMemo<LearningStateContextValue>(
    () => ({
      dataSource,
      setDataSource,
      state,
      loading,
      error,
      liveAvailable,
      refreshState,
      setGapStatus: setGapStatusAction,
      submitQuiz,
    }),
    [dataSource, setDataSource, state, loading, error, liveAvailable, refreshState, setGapStatusAction, submitQuiz]
  );

  return <LearningStateContext.Provider value={value}>{children}</LearningStateContext.Provider>;
}

export function useLearningState(): LearningStateContextValue {
  const ctx = useContext(LearningStateContext);
  if (!ctx) {
    throw new Error("useLearningState must be used within StateProvider.");
  }
  return ctx;
}
