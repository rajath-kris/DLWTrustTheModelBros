import { useEffect, useMemo, useRef, useState } from "react";

import {
  fetchActiveTopic,
  fetchSentinelRuntimeStatus,
  fetchTopicsForCourse,
  startSentinelRuntime,
  upsertTopic,
} from "../api";
import { DocumentHub } from "../components/DocumentHub";
import { useBrainState } from "../context/BrainStateContext";
import { useCourse } from "../context/CourseContext";
import type { MockDocument } from "../data/mockDocuments";
import type { SentinelSessionContext, TopicSummary } from "../types";

function normalizeCourseId(raw: string): string {
  return raw.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

function topicIdFromName(topicName: string): string {
  const compact = topicName.trim().toLowerCase().replace(/\s+/g, " ");
  const slug = compact.replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  if (!slug) {
    return `topic-${Date.now()}`;
  }
  return slug.startsWith("topic-") ? slug : `topic-${slug}`;
}

function classifyDocumentType(rawType: string, isAnchor: boolean): MockDocument["type"] {
  if (isAnchor) {
    return "anchor";
  }
  return rawType.toLowerCase().includes("pdf") ? "pdf" : "other";
}

function formatCourseLabel(courseId: string): string {
  if (courseId === "all") {
    return "ALL";
  }
  return courseId.toUpperCase();
}

export function CoursesPage() {
  const { courses, courseId, setCourseId } = useCourse();
  const {
    state,
    loading,
    liveAvailable,
    error: liveError,
    refreshState,
    createCourse,
    deleteCourse,
    uploadCourseDocument,
    moveCourseDocument,
    anchorCourseDocument,
    removeCourseDocument,
    fetchSentinelSessionContext,
    setSentinelSessionContext,
  } = useBrainState();

  const uploadClickRef = useRef<(() => void) | null>(null);

  const availableCourses = useMemo(
    () => courses.filter((item) => item.id !== "all"),
    [courses]
  );

  const [selectedCourseId, setSelectedCourseId] = useState(
    courseId !== "all" ? courseId : availableCourses[0]?.id || ""
  );
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [topicLoadError, setTopicLoadError] = useState<string | null>(null);
  const [newCourseCode, setNewCourseCode] = useState("");
  const [newCourseTitle, setNewCourseTitle] = useState("");
  const [newTopicName, setNewTopicName] = useState("");
  const [creatingCourse, setCreatingCourse] = useState(false);
  const [deletingCourseId, setDeletingCourseId] = useState<string | null>(null);
  const [creatingTopic, setCreatingTopic] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [sessionContext, setSessionContext] = useState<SentinelSessionContext | null>(null);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);
  const [bindingSession, setBindingSession] = useState(false);

  const courseNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of availableCourses) {
      map.set(item.id, item.name);
    }
    for (const row of state.courses) {
      if (row.course_id === "all") {
        continue;
      }
      if (!map.has(row.course_id)) {
        map.set(row.course_id, row.course_name);
      }
    }
    return map;
  }, [availableCourses, state.courses]);

  const topicNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of topics) {
      map.set(item.topic_id, item.topic_name);
    }
    return map;
  }, [topics]);

  useEffect(() => {
    if (courseId !== "all") {
      setSelectedCourseId(courseId);
      return;
    }
    setSelectedCourseId((current) => {
      if (current && availableCourses.some((item) => item.id === current)) {
        return current;
      }
      return availableCourses[0]?.id || "";
    });
  }, [availableCourses, courseId]);

  useEffect(() => {
    let active = true;

    async function hydrateTopics() {
      if (!selectedCourseId) {
        if (active) {
          setTopics([]);
          setSelectedTopicId("");
          setTopicLoadError(null);
        }
        return;
      }

      try {
        const [topicList, activeTopic] = await Promise.all([
          fetchTopicsForCourse(selectedCourseId),
          fetchActiveTopic(),
        ]);
        if (!active) {
          return;
        }
        setTopics(topicList.topics);
        const preferredTopic =
          (activeTopic.active_topic_id &&
          topicList.topics.some((item) => item.topic_id === activeTopic.active_topic_id)
            ? activeTopic.active_topic_id
            : "") ||
          topicList.topics[0]?.topic_id ||
          "";
        setSelectedTopicId((current) =>
          current && topicList.topics.some((item) => item.topic_id === current)
            ? current
            : preferredTopic
        );
        setTopicLoadError(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setTopicLoadError(error instanceof Error ? error.message : "Could not load topics for this course.");
      }
    }

    void hydrateTopics();
    return () => {
      active = false;
    };
  }, [selectedCourseId]);

  useEffect(() => {
    let active = true;
    void fetchSentinelSessionContext()
      .then((value) => {
        if (active) {
          setSessionContext(value);
        }
      })
      .catch(() => {
        if (active) {
          setSessionContext(null);
        }
      });
    return () => {
      active = false;
    };
  }, [fetchSentinelSessionContext]);

  const liveDocuments = useMemo<MockDocument[]>(
    () =>
      state.documents
        .filter((doc) => doc.course_id === selectedCourseId)
        .slice()
        .sort((a, b) => Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at))
        .map((doc) => ({
          doc_id: doc.doc_id,
          course_id: doc.course_id,
          topic_id: doc.topic_id,
          course_label: formatCourseLabel(doc.course_id),
          topic_label: topicNameById.get(doc.topic_id) || doc.topic_id,
          name: doc.name,
          size: `${Math.max(1, Math.round(doc.size_bytes / 1024))} KB`,
          upload_date: doc.uploaded_at.split("T")[0] ?? doc.uploaded_at,
          type: classifyDocumentType(doc.type, doc.is_anchor),
          path: doc.file_url,
          is_anchor: doc.is_anchor,
        })),
    [selectedCourseId, state.documents, topicNameById]
  );

  const canUpload = Boolean(selectedCourseId) && Boolean(selectedTopicId);
  const uploadRequirementHint = !selectedCourseId
    ? "Create/select a course first."
    : topics.length === 0
    ? "Create a topic for this course first."
    : !selectedTopicId
    ? "Select a topic before uploading."
    : undefined;

  async function handleCreateCourse() {
    const normalizedCode = normalizeCourseId(newCourseCode);
    const cleanedTitle = newCourseTitle.trim().replace(/\s+/g, " ");
    if (!normalizedCode) {
      setFormError("Enter a valid course code.");
      return;
    }
    if (!cleanedTitle) {
      setFormError("Enter a course title.");
      return;
    }

    setCreatingCourse(true);
    setFormError(null);
    try {
      await createCourse(normalizedCode, cleanedTitle);
      await refreshState();
      setSelectedCourseId(normalizedCode);
      setCourseId(normalizedCode);
      setNewCourseCode("");
      setNewCourseTitle("");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not create course.");
    } finally {
      setCreatingCourse(false);
    }
  }

  async function handleDeleteCourse(targetCourseId: string) {
    setDeletingCourseId(targetCourseId);
    setFormError(null);
    try {
      await deleteCourse(targetCourseId);
      await refreshState();
      if (selectedCourseId === targetCourseId) {
        const fallback = availableCourses.find((item) => item.id !== targetCourseId)?.id || "";
        setSelectedCourseId(fallback);
        setCourseId(fallback || "all");
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not delete course.");
    } finally {
      setDeletingCourseId(null);
    }
  }

  async function handleCreateTopic() {
    const cleanedTopicName = newTopicName.trim().replace(/\s+/g, " ");
    if (!selectedCourseId) {
      setFormError("Select a course before creating a topic.");
      return;
    }
    if (!cleanedTopicName) {
      setFormError("Enter a topic name.");
      return;
    }

    setCreatingTopic(true);
    setFormError(null);
    try {
      const created = await upsertTopic(topicIdFromName(cleanedTopicName), cleanedTopicName, selectedCourseId);
      setTopics((current) => [created, ...current.filter((item) => item.topic_id !== created.topic_id)]);
      setSelectedTopicId(created.topic_id);
      setNewTopicName("");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not create topic.");
    } finally {
      setCreatingTopic(false);
    }
  }

  async function handleUpload(files: File[]) {
    if (!selectedCourseId) {
      throw new Error("Select a course before uploading.");
    }
    if (!selectedTopicId) {
      throw new Error("Select a topic before uploading.");
    }
    for (const file of files) {
      await uploadCourseDocument(selectedCourseId, selectedTopicId, file);
    }
  }

  async function handleSetAnchor(doc: MockDocument) {
    if (!doc.doc_id || !selectedCourseId) {
      throw new Error("Could not resolve document for anchor update.");
    }
    await anchorCourseDocument(selectedCourseId, doc.doc_id);
  }

  async function handleMoveTopic(doc: MockDocument, topicId: string) {
    if (!doc.doc_id || !selectedCourseId) {
      throw new Error("Could not resolve document for topic move.");
    }
    await moveCourseDocument(selectedCourseId, doc.doc_id, topicId);
  }

  async function handleDeleteDocument(doc: MockDocument) {
    if (!doc.doc_id || !selectedCourseId) {
      throw new Error("Could not resolve document for delete.");
    }
    await removeCourseDocument(selectedCourseId, doc.doc_id);
  }

  async function handleStartSentinelSession() {
    if (!selectedCourseId || !selectedTopicId) {
      setSessionMessage("Select course and topic before starting Sentinel session.");
      return;
    }

    setBindingSession(true);
    setSessionMessage(null);
    try {
      const context = await setSentinelSessionContext(selectedCourseId, selectedTopicId);
      setSessionContext(context);

      const runtime = await fetchSentinelRuntimeStatus();
      if (!runtime.running) {
        await startSentinelRuntime();
      }
      setSessionMessage("Sentinel session is ready for this course/topic.");
    } catch (error) {
      setSessionMessage(error instanceof Error ? error.message : "Could not bind Sentinel session.");
    } finally {
      setBindingSession(false);
    }
  }

  return (
    <div className="page-shell page-fade">
      <header className="courses-page-header">
        <div className="courses-page-title-row">
          <h1>Courses</h1>
          <span className="pill pill-docs-uploaded">{availableCourses.length} Courses</span>
          <span className="pill pill-docs-uploaded">{liveDocuments.length} Docs in Selected Course</span>
        </div>
      </header>

      {loading && <p className="status-line">Loading live course state...</p>}
      {!liveAvailable && <p className="status-line">{liveError ?? "Live bridge state unavailable."}</p>}
      {topicLoadError && <p className="status-line error">{topicLoadError}</p>}
      {formError && <p className="status-line error">{formError}</p>}
      {sessionMessage && <p className="status-line">{sessionMessage}</p>}

      <section className="courses-grid">
        <article className="card courses-card">
          <h3>Create Course</h3>
          <div className="courses-form-grid">
            <label className="quiz-config-label" htmlFor="course-code">Course code</label>
            <input
              id="course-code"
              className="quiz-count-input"
              value={newCourseCode}
              placeholder="e.g. cs2100"
              onChange={(event) => setNewCourseCode(event.target.value)}
            />
            <label className="quiz-config-label" htmlFor="course-title">Course title</label>
            <input
              id="course-title"
              className="quiz-count-input"
              value={newCourseTitle}
              placeholder="e.g. Computer Organisation"
              onChange={(event) => setNewCourseTitle(event.target.value)}
            />
            <button
              type="button"
              className="top-bar-btn primary"
              onClick={() => void handleCreateCourse()}
              disabled={creatingCourse}
            >
              {creatingCourse ? "Creating..." : "Create Course"}
            </button>
          </div>
        </article>

        <article className="card courses-card">
          <h3>Course List</h3>
          <ul className="courses-list">
            {availableCourses.map((item) => (
              <li key={item.id} className="courses-list-item">
                <button
                  type="button"
                  className={`courses-course-chip ${selectedCourseId === item.id ? "active" : ""}`}
                  onClick={() => {
                    setSelectedCourseId(item.id);
                    setCourseId(item.id);
                  }}
                >
                  {item.name}
                </button>
                <button
                  type="button"
                  className="top-bar-btn"
                  onClick={() => void handleDeleteCourse(item.id)}
                  disabled={deletingCourseId === item.id}
                >
                  {deletingCourseId === item.id ? "Deleting..." : "Delete"}
                </button>
              </li>
            ))}
            {availableCourses.length === 0 && <li className="status-line">No courses yet.</li>}
          </ul>
        </article>
      </section>

      <section className="courses-grid">
        <article className="card courses-card">
          <h3>Topic Manager</h3>
          <label className="quiz-config-label" htmlFor="courses-topic-select">Topic</label>
          <select
            id="courses-topic-select"
            className="quiz-topic-select"
            value={selectedTopicId}
            onChange={(event) => setSelectedTopicId(event.target.value)}
            aria-label="Select topic for selected course"
          >
            <option value="">Select topic</option>
            {topics.map((topic) => (
              <option key={topic.topic_id} value={topic.topic_id}>
                {topic.topic_name}
              </option>
            ))}
          </select>
          <div className="courses-topic-create-row">
            <input
              className="quiz-count-input"
              value={newTopicName}
              placeholder="e.g. Laplace Transform"
              onChange={(event) => setNewTopicName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") {
                  return;
                }
                event.preventDefault();
                void handleCreateTopic();
              }}
            />
            <button
              type="button"
              className="top-bar-btn"
              onClick={() => void handleCreateTopic()}
              disabled={creatingTopic || !selectedCourseId}
            >
              {creatingTopic ? "Creating..." : "Create Topic"}
            </button>
          </div>
        </article>

        <article className="card courses-card">
          <h3>Sentinel Session</h3>
          <p className="courses-session-meta">
            Active context:{" "}
            {sessionContext?.course_id && sessionContext?.topic_id
              ? `${sessionContext.course_name || sessionContext.course_id} / ${sessionContext.topic_name || sessionContext.topic_id}`
              : "Not set"}
          </p>
          <button
            type="button"
            className="quiz-start-btn"
            onClick={() => void handleStartSentinelSession()}
            disabled={bindingSession || !selectedCourseId || !selectedTopicId}
          >
            {bindingSession ? "Binding..." : "Start Sentinel Session"}
          </button>
        </article>
      </section>

      <DocumentHub
        sectionId="courses-document-hub"
        hideHeader
        showRowActions
        documents={liveDocuments}
        uploadEnabled={canUpload}
        uploadRequirementHint={uploadRequirementHint}
        onUploadClickRef={uploadClickRef}
        onUploadFiles={handleUpload}
        onSetAnchor={handleSetAnchor}
        onMoveTopic={handleMoveTopic}
        onDeleteDocument={handleDeleteDocument}
        topicOptions={topics}
      />
    </div>
  );
}

