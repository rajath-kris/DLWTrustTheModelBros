import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  createCourse,
  createDeadline,
  deleteDocument,
  deleteCourse,
  emptyState,
  fetchSentinelSessionContext,
  fetchState,
  moveDocumentToTopic,
  openEventStream,
  prepareQuiz,
  setSentinelSessionContext,
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
  SentinelSessionContext,
} from "../types";

const STREAM_DISCONNECTED_MESSAGE = "Live stream disconnected. Data may be stale until reconnection.";
const INITIAL_HYDRATE_ATTEMPTS = 4;
const INITIAL_HYDRATE_RETRY_DELAY_MS = 700;

interface BrainStateContextValue {
  state: LearningState;
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
  refreshState: () => Promise<void>;
  setGapStatus: (gapId: string, status: GapStatus) => Promise<void>;
  addDeadline: (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => Promise<void>;
  createCourse: (courseId: string, courseName: string) => Promise<void>;
  deleteCourse: (courseId: string) => Promise<void>;
  fetchSentinelSessionContext: () => Promise<SentinelSessionContext>;
  setSentinelSessionContext: (courseId: string, topicId: string) => Promise<SentinelSessionContext>;
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
    let reconnectTimer: number | null = null;
    let fallbackRefreshTimer: number | null = null;
    let reconnectAttempt = 0;
    let hydrateRetryTimer: number | null = null;

    async function hydrate() {
      let lastError: unknown = null;
      for (let attempt = 0; attempt < INITIAL_HYDRATE_ATTEMPTS; attempt += 1) {
        try {
          await refreshState();
          if (!mounted) {
            return;
          }
          setLoading(false);
          return;
        } catch (err) {
          lastError = err;
          if (!mounted) {
            return;
          }
          if (attempt < INITIAL_HYDRATE_ATTEMPTS - 1) {
            await new Promise<void>((resolve) => {
              hydrateRetryTimer = window.setTimeout(resolve, INITIAL_HYDRATE_RETRY_DELAY_MS);
            });
          }
        }
      }
      if (!mounted) {
        return;
      }
      setLiveAvailable(false);
      setError(lastError instanceof Error ? lastError.message : "Could not load live bridge state.");
      setLoading(false);
    }

    function clearReconnectTimer() {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    }

    async function tryBackgroundRefresh() {
      try {
        await refreshState();
      } catch {
        // Best-effort fallback while SSE is reconnecting.
      }
    }

    function connectStream() {
      stream?.close();
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

      stream.onopen = () => {
        if (!mounted) {
          return;
        }
        reconnectAttempt = 0;
        setLiveAvailable(true);
        setError((current) => (current === STREAM_DISCONNECTED_MESSAGE ? null : current));
      };

      stream.onerror = () => {
        if (!mounted) {
          return;
        }
        stream?.close();
        stream = null;
        setLiveAvailable(false);
        setError(STREAM_DISCONNECTED_MESSAGE);
        void tryBackgroundRefresh();

        clearReconnectTimer();
        const delayMs = Math.min(15000, 1000 * 2 ** reconnectAttempt);
        reconnectAttempt += 1;
        reconnectTimer = window.setTimeout(() => {
          if (!mounted) {
            return;
          }
          connectStream();
        }, delayMs);
      };
    }

    hydrate();
    connectStream();
    fallbackRefreshTimer = window.setInterval(() => {
      if (!mounted) {
        return;
      }
      void tryBackgroundRefresh();
    }, 20000);

    return () => {
      mounted = false;
      clearReconnectTimer();
      if (fallbackRefreshTimer !== null) {
        window.clearInterval(fallbackRefreshTimer);
      }
      if (hydrateRetryTimer !== null) {
        window.clearTimeout(hydrateRetryTimer);
      }
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

  const createCourseEntry = useCallback(
    async (courseId: string, courseName: string) => {
      await createCourse(courseId, courseName);
      await refreshState();
    },
    [refreshState]
  );

  const deleteCourseEntry = useCallback(
    async (courseId: string) => {
      await deleteCourse(courseId);
      await refreshState();
    },
    [refreshState]
  );

  const uploadCourseDocument = useCallback(
    async (courseId: string, topicId: string, file: File, documentName?: string, documentType?: string) => {
      const uploaded = await uploadDocument(courseId, topicId, file, documentName, documentType);
      setState((current) => {
        const nextDocuments = current.documents.filter((doc) => doc.doc_id !== uploaded.doc_id);
        nextDocuments.push(uploaded);
        return {
          ...current,
          updated_at: new Date().toISOString(),
          documents: nextDocuments,
        };
      });
      try {
        await refreshState();
      } catch {
        // Keep optimistic upload state when live refresh is temporarily unavailable.
      }
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

  const fetchSentinelSessionContextValue = useCallback(async () => {
    return fetchSentinelSessionContext();
  }, []);

  const setSentinelSessionContextValue = useCallback(
    async (courseId: string, topicId: string) => {
      const response = await setSentinelSessionContext(courseId, topicId);
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
      createCourse: createCourseEntry,
      deleteCourse: deleteCourseEntry,
      fetchSentinelSessionContext: fetchSentinelSessionContextValue,
      setSentinelSessionContext: setSentinelSessionContextValue,
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
      createCourseEntry,
      deleteCourseEntry,
      fetchSentinelSessionContextValue,
      setSentinelSessionContextValue,
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
