import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  createDeadline,
  deleteDocument,
  emptyState,
  fetchState,
  moveDocumentToTopic,
  openEventStream,
  prepareQuiz,
  setDocumentAnchor,
  submitQuiz,
  updateGapStatus,
  uploadDocument,
} from "../api";
import type {
  GapStatus,
  LearningState,
  QuizPrepareRequest,
  QuizPrepareResponse,
  QuizSubmitRequest,
  QuizSubmitResponse,
  ServerEventEnvelope,
} from "../types";

interface BrainStateContextValue {
  state: LearningState;
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
  refreshState: () => Promise<void>;
  setGapStatus: (gapId: string, status: GapStatus) => Promise<void>;
  addDeadline: (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => Promise<void>;
  uploadCourseDocument: (courseId: string, topicId: string, file: File, documentName?: string, documentType?: string) => Promise<void>;
  moveCourseDocument: (courseId: string, docId: string, topicId: string) => Promise<void>;
  anchorCourseDocument: (courseId: string, docId: string) => Promise<void>;
  removeCourseDocument: (courseId: string, docId: string) => Promise<void>;
  prepareQuiz: (payload: QuizPrepareRequest) => Promise<QuizPrepareResponse>;
  submitQuiz: (payload: QuizSubmitRequest) => Promise<QuizSubmitResponse>;
}

const BrainStateContext = createContext<BrainStateContextValue | null>(null);

export function BrainStateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<LearningState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveAvailable, setLiveAvailable] = useState(true);

  const refreshState = useCallback(async () => {
    const fresh = await fetchState();
    setState(fresh);
    setError(null);
    setLiveAvailable(true);
  }, []);

  useEffect(() => {
    let stream: EventSource | null = null;
    let mounted = true;

    async function hydrate() {
      try {
        await refreshState();
      } catch (err) {
        if (!mounted) {
          return;
        }
        setLiveAvailable(false);
        setError(err instanceof Error ? err.message : "Could not load live bridge state.");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    hydrate();

    stream = openEventStream((message) => {
      try {
        const envelope = JSON.parse(message.data) as ServerEventEnvelope;
        if (envelope.payload?.state) {
          setState(envelope.payload.state);
          setError(null);
          setLiveAvailable(true);
        }
      } catch {
        // Ignore malformed stream events.
      }
    });

    stream.onerror = () => {
      if (!mounted) {
        return;
      }
      setLiveAvailable(false);
      setError("Live stream disconnected. Data may be stale until reconnection.");
    };

    return () => {
      mounted = false;
      stream?.close();
    };
  }, [refreshState]);

  const setGapStatus = useCallback(
    async (gapId: string, status: GapStatus) => {
      await updateGapStatus(gapId, status);
      await refreshState();
    },
    [refreshState]
  );

  const addDeadline = useCallback(
    async (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => {
      await createDeadline(courseId, payload);
      await refreshState();
    },
    [refreshState]
  );

  const uploadCourseDocument = useCallback(
    async (courseId: string, topicId: string, file: File, documentName?: string, documentType?: string) => {
      await uploadDocument(courseId, topicId, file, documentName, documentType);
      await refreshState();
    },
    [refreshState]
  );

  const anchorCourseDocument = useCallback(
    async (courseId: string, docId: string) => {
      await setDocumentAnchor(courseId, docId);
      await refreshState();
    },
    [refreshState]
  );

  const moveCourseDocument = useCallback(
    async (courseId: string, docId: string, topicId: string) => {
      await moveDocumentToTopic(courseId, docId, topicId);
      await refreshState();
    },
    [refreshState]
  );

  const removeCourseDocument = useCallback(
    async (courseId: string, docId: string) => {
      await deleteDocument(courseId, docId);
      await refreshState();
    },
    [refreshState]
  );

  const prepareQuizAttempt = useCallback(async (payload: QuizPrepareRequest) => {
    return prepareQuiz(payload);
  }, []);

  const submitQuizAttempt = useCallback(
    async (payload: QuizSubmitRequest) => {
      const response = await submitQuiz(payload);
      await refreshState();
      return response;
    },
    [refreshState]
  );

  const value = useMemo<BrainStateContextValue>(
    () => ({
      state,
      loading,
      error,
      liveAvailable,
      refreshState,
      setGapStatus,
      addDeadline,
      uploadCourseDocument,
      moveCourseDocument,
      anchorCourseDocument,
      removeCourseDocument,
      prepareQuiz: prepareQuizAttempt,
      submitQuiz: submitQuizAttempt,
    }),
    [
      state,
      loading,
      error,
      liveAvailable,
      refreshState,
      setGapStatus,
      addDeadline,
      uploadCourseDocument,
      moveCourseDocument,
      anchorCourseDocument,
      removeCourseDocument,
      prepareQuizAttempt,
      submitQuizAttempt,
    ]
  );

  return <BrainStateContext.Provider value={value}>{children}</BrainStateContext.Provider>;
}

export function useBrainState(): BrainStateContextValue {
  const ctx = useContext(BrainStateContext);
  if (!ctx) {
    throw new Error("useBrainState must be used within BrainStateProvider.");
  }
  return ctx;
}
