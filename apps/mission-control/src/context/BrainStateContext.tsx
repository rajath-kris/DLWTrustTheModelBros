import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  askSentinel,
  createDeadline,
  deleteDocument,
  emptyState,
  fetchState,
  openEventStream,
  setDocumentAnchor,
  submitQuiz,
  updateGapStatus,
  uploadDocument,
} from "../api";
import type { AskResponse, GapStatus, LearningState, QuizSubmitRequest, QuizSubmitResponse, ServerEventEnvelope } from "../types";

interface BrainStateContextValue {
  state: LearningState;
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
  refreshState: () => Promise<void>;
  setGapStatus: (gapId: string, status: GapStatus) => Promise<void>;
  addDeadline: (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => Promise<void>;
  uploadCourseDocument: (courseId: string, moduleId: string, file: File, documentName?: string, documentType?: string) => Promise<void>;
  anchorCourseDocument: (courseId: string, docId: string) => Promise<void>;
  removeCourseDocument: (courseId: string, docId: string) => Promise<void>;
  ask: (payload: { course_id: string; thread_id?: string; turn_index?: number; message: string }) => Promise<AskResponse>;
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
    async (courseId: string, moduleId: string, file: File, documentName?: string, documentType?: string) => {
      await uploadDocument(courseId, moduleId, file, documentName, documentType);
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

  const removeCourseDocument = useCallback(
    async (courseId: string, docId: string) => {
      await deleteDocument(courseId, docId);
      await refreshState();
    },
    [refreshState]
  );

  const ask = useCallback(
    async (payload: { course_id: string; thread_id?: string; turn_index?: number; message: string }) => {
      const response = await askSentinel(payload);
      await refreshState();
      return response;
    },
    [refreshState]
  );

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
      anchorCourseDocument,
      removeCourseDocument,
      ask,
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
      anchorCourseDocument,
      removeCourseDocument,
      ask,
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
