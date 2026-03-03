import type { TopicSummary } from "../types";

interface ActivationCourseOption {
  id: string;
  name: string;
}

export function SentinelActivationModal({
  open,
  courses,
  selectedCourseId,
  selectedTopicId,
  topics,
  loadingTopics,
  activating,
  error,
  onClose,
  onSelectCourse,
  onSelectTopic,
  onActivate,
  onOpenDocumentHub,
}: {
  open: boolean;
  courses: ActivationCourseOption[];
  selectedCourseId: string;
  selectedTopicId: string;
  topics: TopicSummary[];
  loadingTopics: boolean;
  activating: boolean;
  error: string | null;
  onClose: () => void;
  onSelectCourse: (courseId: string) => void;
  onSelectTopic: (topicId: string) => void;
  onActivate: () => void;
  onOpenDocumentHub: () => void;
}) {
  if (!open) {
    return null;
  }

  const noTopicsForCourse = selectedCourseId !== "" && !loadingTopics && topics.length === 0;
  const activateDisabled =
    activating ||
    loadingTopics ||
    selectedCourseId.trim() === "" ||
    selectedTopicId.trim() === "" ||
    noTopicsForCourse;

  return (
    <div className="sentinel-activation-backdrop" onClick={onClose}>
      <div className="sentinel-activation-modal" onClick={(event) => event.stopPropagation()}>
        <div className="sentinel-activation-header">
          <h2>Activate Sentinel</h2>
          <button type="button" className="top-bar-btn" onClick={onClose} disabled={activating}>
            Close
          </button>
        </div>
        <div className="sentinel-activation-form">
          <label className="quiz-config-label" htmlFor="sentinel-activation-course">
            Course
          </label>
          <select
            id="sentinel-activation-course"
            className="quiz-topic-select"
            value={selectedCourseId}
            onChange={(event) => onSelectCourse(event.target.value)}
            disabled={activating}
            aria-label="Select course for sentinel activation"
          >
            <option value="">Select course</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
              </option>
            ))}
          </select>

          <label className="quiz-config-label" htmlFor="sentinel-activation-topic">
            Topic
          </label>
          <select
            id="sentinel-activation-topic"
            className="quiz-topic-select"
            value={selectedTopicId}
            onChange={(event) => onSelectTopic(event.target.value)}
            disabled={activating || loadingTopics || selectedCourseId.trim() === ""}
            aria-label="Select topic for sentinel activation"
          >
            <option value="">{loadingTopics ? "Loading topics..." : "Select topic"}</option>
            {topics.map((topic) => (
              <option key={topic.topic_id} value={topic.topic_id}>
                {topic.topic_name}
              </option>
            ))}
          </select>

          {noTopicsForCourse && (
            <div className="sentinel-activation-inline-warning" role="status">
              <p>No topics found for this course. Create/upload in Document Hub first.</p>
              <button type="button" className="top-bar-btn" onClick={onOpenDocumentHub} disabled={activating}>
                Open Document Hub
              </button>
            </div>
          )}

          {error && (
            <p className="status-line error" role="alert">
              {error}
            </p>
          )}

          <div className="sentinel-activation-actions">
            <button
              type="button"
              className="top-bar-btn primary"
              onClick={onActivate}
              disabled={activateDisabled}
            >
              {activating ? "Activating..." : "Activate Sentinel"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
