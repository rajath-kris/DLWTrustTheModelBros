import { useEffect, useMemo, useRef, useState } from "react";
import { fetchActiveTopic, fetchTopics, upsertTopic } from "../api";
import { useCourse } from "../context/CourseContext";
import { useBrainState } from "../context/BrainStateContext";
import { DocumentHub } from "../components/DocumentHub";
import type { MockDocument } from "../data/mockDocuments";
import type { TopicSummary } from "../types";

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

function topicIdFromName(topicName: string): string {
  const compact = topicName.trim().toLowerCase().replace(/\s+/g, " ");
  const slug = compact.replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  if (!slug) {
    return `topic-${Date.now()}`;
  }
  return slug.startsWith("topic-") ? slug : `topic-${slug}`;
}

export function DocumentHubPage() {
  const { courseId, courseData, allCoursesSummary, courses, liveAvailable, liveError } = useCourse();
  const { state, uploadCourseDocument, moveCourseDocument, anchorCourseDocument, removeCourseDocument } = useBrainState();
  const uploadClickRef = useRef<(() => void) | null>(null);

  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [topicLoadError, setTopicLoadError] = useState<string | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState(courseId === "all" ? "" : courseId);
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [suggestedTopicId, setSuggestedTopicId] = useState("");
  const [newTopicName, setNewTopicName] = useState("");
  const [isCreatingTopic, setIsCreatingTopic] = useState(false);
  const [topicCreateError, setTopicCreateError] = useState<string | null>(null);

  useEffect(() => {
    setSelectedCourseId(courseId === "all" ? "" : courseId);
  }, [courseId]);

  useEffect(() => {
    let active = true;

    async function hydrateTopics() {
      try {
        const [topicList, activeTopic] = await Promise.all([fetchTopics(), fetchActiveTopic()]);
        if (!active) {
          return;
        }
        setTopics(topicList.topics);
        const preferredTopicId =
          activeTopic.active_topic_id ||
          topicList.active_topic_id ||
          topicList.topics[0]?.topic_id ||
          "";
        setSuggestedTopicId(preferredTopicId);
        setTopicLoadError(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setTopicLoadError(error instanceof Error ? error.message : "Could not load topics.");
      }
    }

    void hydrateTopics();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedTopicId) {
      return;
    }
    if (topics.some((topic) => topic.topic_id === selectedTopicId)) {
      return;
    }
    setSelectedTopicId("");
  }, [topics, selectedTopicId]);

  const topicNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const topic of topics) {
      map.set(topic.topic_id, topic.topic_name);
    }
    return map;
  }, [topics]);

  const courseNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const course of courses) {
      if (course.id === "all") {
        continue;
      }
      map.set(course.id, course.name);
    }
    for (const course of state.courses) {
      if (course.course_id === "all") {
        continue;
      }
      if (!map.has(course.course_id)) {
        map.set(course.course_id, course.course_name);
      }
    }
    return map;
  }, [courses, state.courses]);

  const uploadCourseOptions = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ id: string; name: string }> = [];
    for (const course of courses) {
      if (course.id === "all" || seen.has(course.id)) {
        continue;
      }
      seen.add(course.id);
      options.push({ id: course.id, name: course.name });
    }
    for (const course of state.courses) {
      if (course.course_id === "all" || seen.has(course.course_id)) {
        continue;
      }
      seen.add(course.course_id);
      options.push({ id: course.course_id, name: course.course_name });
    }
    options.sort((a, b) => a.name.localeCompare(b.name));
    return options;
  }, [courses, state.courses]);

  const allLiveDocuments = useMemo<MockDocument[]>(
    () =>
      state.documents
        .filter((doc) => courseId === "all" || doc.course_id === courseId)
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
    [state.documents, courseId, topicNameById]
  );

  const fallbackDocuments = useMemo<MockDocument[] | undefined>(() => {
    if (courseId === "all") {
      return allCoursesSummary.flatMap(({ course, data }) =>
        data.documents.map((doc) => ({
          ...doc,
          course_id: course.id,
          course_label: formatCourseLabel(course.id),
        }))
      );
    }
    return courseData?.documents;
  }, [allCoursesSummary, courseData, courseId]);

  const documentRows = allLiveDocuments.length > 0 || liveAvailable ? allLiveDocuments : fallbackDocuments;
  const count = documentRows?.length ?? 0;
  const courseBadge = courseId === "all" ? "All" : formatCourseLabel(courseId);
  const canUpload = Boolean(selectedTopicId) && (courseId !== "all" || Boolean(selectedCourseId));

  const uploadRequirementHint =
    topics.length === 0
      ? "No topics available. Create a topic before uploading."
      : courseId === "all" && !selectedCourseId
      ? "Select a course and topic before uploading."
      : !selectedTopicId
      ? "Select a topic before uploading."
      : undefined;

  async function handleUpload(files: File[]) {
    const targetCourse = courseId === "all" ? selectedCourseId : courseId;
    if (!targetCourse || targetCourse === "all") {
      throw new Error("Select a target course before uploading.");
    }
    if (!selectedTopicId) {
      throw new Error("Select a target topic before uploading.");
    }
    for (const file of files) {
      await uploadCourseDocument(targetCourse, selectedTopicId, file);
    }
  }

  async function handleSetAnchor(doc: MockDocument) {
    const targetCourse = doc.course_id || (courseId === "all" ? selectedCourseId : courseId);
    if (!doc.doc_id || !targetCourse || targetCourse === "all") {
      throw new Error("Could not resolve the document course for anchoring.");
    }
    await anchorCourseDocument(targetCourse, doc.doc_id);
  }

  async function handleMoveTopic(doc: MockDocument, topicId: string) {
    const targetCourse = doc.course_id || (courseId === "all" ? selectedCourseId : courseId);
    if (!doc.doc_id || !targetCourse || targetCourse === "all") {
      throw new Error("Could not resolve the document course for topic move.");
    }
    const targetTopic = topicId.trim();
    if (!targetTopic) {
      throw new Error("Select a target topic to move this document.");
    }
    await moveCourseDocument(targetCourse, doc.doc_id, targetTopic);
  }

  async function handleDelete(doc: MockDocument) {
    const targetCourse = doc.course_id || (courseId === "all" ? selectedCourseId : courseId);
    if (!doc.doc_id || !targetCourse || targetCourse === "all") {
      throw new Error("Could not resolve the document course for deletion.");
    }
    await removeCourseDocument(targetCourse, doc.doc_id);
  }

  async function handleCreateTopic() {
    const cleanedTopicName = newTopicName.trim().replace(/\s+/g, " ");
    if (!cleanedTopicName) {
      setTopicCreateError("Enter a topic name before creating it.");
      return;
    }

    setTopicCreateError(null);
    setIsCreatingTopic(true);
    try {
      const createdTopic = await upsertTopic(topicIdFromName(cleanedTopicName), cleanedTopicName);
      setTopics((current) => {
        const next = current.filter((topic) => topic.topic_id !== createdTopic.topic_id);
        return [createdTopic, ...next];
      });
      setSelectedTopicId(createdTopic.topic_id);
      setSuggestedTopicId(createdTopic.topic_id);
      setNewTopicName("");
    } catch (error) {
      setTopicCreateError(error instanceof Error ? error.message : "Could not create topic.");
    } finally {
      setIsCreatingTopic(false);
    }
  }

  return (
    <div className="page-shell page-fade">
      <header className="docs-page-header">
        <div className="docs-page-title-row">
          <h1>Document Hub</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <span className="pill pill-docs-uploaded">{count} Uploaded</span>
          <button type="button" className="top-bar-btn primary" onClick={() => uploadClickRef.current?.()} disabled={!canUpload}>
            + Upload
          </button>
        </div>
        <div className="docs-upload-controls">
          {courseId === "all" && (
            <label className="docs-upload-control">
              <span>Course</span>
              <select value={selectedCourseId} onChange={(event) => setSelectedCourseId(event.target.value)} aria-label="Select course for upload">
                <option value="">Select course</option>
                {uploadCourseOptions.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="docs-upload-control">
            <span>Topic</span>
            <select value={selectedTopicId} onChange={(event) => setSelectedTopicId(event.target.value)} aria-label="Select topic for upload">
              <option value="">Select topic</option>
              {topics.map((topic) => (
                <option key={topic.topic_id} value={topic.topic_id}>
                  {topic.topic_name}
                </option>
              ))}
            </select>
          </label>
          <label className="docs-upload-control docs-upload-control-create-topic">
            <span>New topic</span>
            <div className="docs-topic-create-row">
              <input
                type="text"
                value={newTopicName}
                placeholder="e.g. Linked Lists"
                aria-label="New topic name"
                onChange={(event) => setNewTopicName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter") {
                    return;
                  }
                  event.preventDefault();
                  void handleCreateTopic();
                }}
              />
              <button type="button" className="top-bar-btn" onClick={() => void handleCreateTopic()} disabled={isCreatingTopic || !newTopicName.trim()}>
                {isCreatingTopic ? "Creating..." : "Create topic"}
              </button>
            </div>
          </label>
        </div>
      </header>

      {!liveAvailable && <p className="status-line">{liveError ?? "Live data unavailable. Showing fallback data where possible."}</p>}
      {topicLoadError && <p className="status-line error">{topicLoadError}</p>}
      {topicCreateError && <p className="status-line error">{topicCreateError}</p>}
      {!selectedTopicId && suggestedTopicId && (
        <p className="status-line">
          Suggested topic: {topicNameById.get(suggestedTopicId) || suggestedTopicId}. Select a topic to enable upload.
        </p>
      )}
      {courseId === "all" && selectedCourseId && (
        <p className="status-line">Upload target course: {courseNameById.get(selectedCourseId) || selectedCourseId}</p>
      )}

      <DocumentHub
        sectionId="document-hub-page"
        documents={documentRows}
        hideHeader
        showRowActions
        uploadEnabled={canUpload}
        uploadRequirementHint={uploadRequirementHint}
        onUploadClickRef={uploadClickRef}
        onUploadFiles={handleUpload}
        onSetAnchor={handleSetAnchor}
        onMoveTopic={handleMoveTopic}
        onDeleteDocument={handleDelete}
        topicOptions={topics}
      />

      <p className="docs-page-footer">
        The Syllabus Anchor grounds Sentinel AI in your course boundaries and keeps guidance aligned with your materials.
      </p>
    </div>
  );
}
