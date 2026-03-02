import { createContext, useCallback, useContext, useMemo } from "react";

import {
  askSentinel,
  createDeadline,
  deleteDocument,
  setDocumentAnchor,
  uploadDocument,
} from "../api";
import { useLearningState } from "./LearningStateContext";
import type { AskResponse, GapStatus, LearningState } from "../types";

interface BrainStateContextValue {
  state: LearningState;
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
  refreshState: () => Promise<void>;
  setGapStatus: (gapId: string, status: GapStatus) => Promise<void>;
  addDeadline: (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => Promise<void>;
  uploadCourseDocument: (courseId: string, file: File, documentName?: string, documentType?: string) => Promise<void>;
  anchorCourseDocument: (courseId: string, docId: string) => Promise<void>;
  removeCourseDocument: (courseId: string, docId: string) => Promise<void>;
  ask: (payload: { course_id: string; thread_id?: string; turn_index?: number; message: string }) => Promise<AskResponse>;
}

const BrainStateContext = createContext<BrainStateContextValue | null>(null);

export function BrainStateProvider({ children }: { children: React.ReactNode }) {
  const learning = useLearningState();

  const addDeadline = useCallback(
    async (courseId: string, payload: { name: string; due_date: string; readiness_score?: number }) => {
      if (learning.dataSource === "mock") {
        return;
      }
      await createDeadline(courseId, payload);
      await learning.refreshState();
    },
    [learning]
  );

  const uploadCourseDocument = useCallback(
    async (courseId: string, file: File, documentName?: string, documentType?: string) => {
      if (learning.dataSource === "mock") {
        return;
      }
      await uploadDocument(courseId, file, documentName, documentType);
      await learning.refreshState();
    },
    [learning]
  );

  const anchorCourseDocument = useCallback(
    async (courseId: string, docId: string) => {
      if (learning.dataSource === "mock") {
        return;
      }
      await setDocumentAnchor(courseId, docId);
      await learning.refreshState();
    },
    [learning]
  );

  const removeCourseDocument = useCallback(
    async (courseId: string, docId: string) => {
      if (learning.dataSource === "mock") {
        return;
      }
      await deleteDocument(courseId, docId);
      await learning.refreshState();
    },
    [learning]
  );

  const ask = useCallback(
    async (payload: { course_id: string; thread_id?: string; turn_index?: number; message: string }) => {
      if (learning.dataSource === "mock") {
        return {
          thread_id: payload.thread_id ?? `mock-thread-${Date.now()}`,
          turn_index: (payload.turn_index ?? 0) + 1,
          socratic_prompt: "What assumption in your reasoning needs direct evidence?",
          citations: [],
        };
      }
      const response = await askSentinel(payload);
      await learning.refreshState();
      return response;
    },
    [learning]
  );

  const value = useMemo<BrainStateContextValue>(
    () => ({
      state: learning.state,
      loading: learning.loading,
      error: learning.error,
      liveAvailable: learning.liveAvailable,
      refreshState: learning.refreshState,
      setGapStatus: learning.setGapStatus,
      addDeadline,
      uploadCourseDocument,
      anchorCourseDocument,
      removeCourseDocument,
      ask,
    }),
    [learning, addDeadline, uploadCourseDocument, anchorCourseDocument, removeCourseDocument, ask]
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
