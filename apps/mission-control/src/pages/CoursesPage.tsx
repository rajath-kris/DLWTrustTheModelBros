import { useMemo, useState } from "react";
import { useBrainState } from "../context/BrainStateContext";
import { useCourse } from "../context/CourseContext";

type CourseFilterId = "all" | "selected" | "with_docs" | "attention";
type CourseSortId = "name" | "docs" | "gaps";

function normalizeCourseId(raw: string): string {
  return raw.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

export function CoursesPage() {
  const { courses, courseId, setCourseId, liveAvailable, liveError } = useCourse();
  const { state, loading, createCourse, deleteCourse } = useBrainState();
  const [deletingCourseId, setDeletingCourseId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [filter, setFilter] = useState<CourseFilterId>("all");
  const [sortBy, setSortBy] = useState<CourseSortId>("name");
  const [search, setSearch] = useState("");
  const [courseModalOpen, setCourseModalOpen] = useState(false);
  const [newCourseCode, setNewCourseCode] = useState("");
  const [newCourseTitle, setNewCourseTitle] = useState("");
  const [creatingCourse, setCreatingCourse] = useState(false);
  const [courseCreateError, setCourseCreateError] = useState<string | null>(null);

  const availableCourses = useMemo(
    () => courses.filter((item) => item.id !== "all"),
    [courses]
  );

  const courseStats = useMemo(() => {
    const docsCountByCourse = new Map<string, number>();
    const openGapsCountByCourse = new Map<string, number>();

    for (const document of state.documents) {
      const courseKey = (document.course_id || "").trim();
      if (!courseKey || courseKey === "all") {
        continue;
      }
      docsCountByCourse.set(courseKey, (docsCountByCourse.get(courseKey) ?? 0) + 1);
    }

    for (const gap of state.gaps) {
      const courseKey = (gap.course_id || "").trim();
      if (!courseKey || courseKey === "all" || gap.status === "closed") {
        continue;
      }
      openGapsCountByCourse.set(courseKey, (openGapsCountByCourse.get(courseKey) ?? 0) + 1);
    }

    return { docsCountByCourse, openGapsCountByCourse };
  }, [state.documents, state.gaps]);

  const courseRows = useMemo(
    () =>
      availableCourses.map((course) => ({
        ...course,
        docsCount: courseStats.docsCountByCourse.get(course.id) ?? 0,
        openGaps: courseStats.openGapsCountByCourse.get(course.id) ?? 0,
        isActive: courseId === course.id,
      })),
    [availableCourses, courseId, courseStats.docsCountByCourse, courseStats.openGapsCountByCourse]
  );

  const filteredAndSorted = useMemo(() => {
    let list = courseRows;
    if (filter === "selected") {
      list = list.filter((course) => course.isActive);
    } else if (filter === "with_docs") {
      list = list.filter((course) => course.docsCount > 0);
    } else if (filter === "attention") {
      list = list.filter((course) => course.openGaps > 0);
    }

    const query = search.trim().toLowerCase();
    if (query) {
      list = list.filter(
        (course) =>
          course.name.toLowerCase().includes(query) ||
          course.id.toLowerCase().includes(query)
      );
    }

    if (sortBy === "docs") {
      list = [...list].sort((a, b) => b.docsCount - a.docsCount || a.name.localeCompare(b.name));
    } else if (sortBy === "gaps") {
      list = [...list].sort((a, b) => b.openGaps - a.openGaps || a.name.localeCompare(b.name));
    } else {
      list = [...list].sort((a, b) => a.name.localeCompare(b.name));
    }

    return list;
  }, [courseRows, filter, search, sortBy]);

  async function handleDeleteCourse(targetCourseId: string) {
    setMutationError(null);
    setDeletingCourseId(targetCourseId);
    try {
      await deleteCourse(targetCourseId);
      if (courseId === targetCourseId) {
        setCourseId("all");
      }
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : "Could not delete course.");
    } finally {
      setDeletingCourseId(null);
    }
  }

  async function handleCreateCourse() {
    const normalizedCode = normalizeCourseId(newCourseCode);
    const cleanedTitle = newCourseTitle.trim().split(/\s+/).join(" ");
    if (!normalizedCode) {
      setCourseCreateError("Enter a valid course code.");
      return;
    }
    if (!cleanedTitle) {
      setCourseCreateError("Enter a course title.");
      return;
    }

    setCreatingCourse(true);
    setCourseCreateError(null);
    setMutationError(null);
    try {
      await createCourse(normalizedCode, cleanedTitle);
      setCourseId(normalizedCode);
      setCourseModalOpen(false);
      setNewCourseCode("");
      setNewCourseTitle("");
    } catch (error) {
      setCourseCreateError(error instanceof Error ? error.message : "Could not create course.");
    } finally {
      setCreatingCourse(false);
    }
  }

  return (
    <div className="page-shell page-fade">
      <header className="gaps-page-header">
        <div className="gaps-page-title-row">
          <h1>Courses</h1>
          <span className="pill pill-course-badge">{availableCourses.length} Courses</span>
          <button
            type="button"
            className="top-bar-btn"
            onClick={() => {
              setCourseCreateError(null);
              setCourseModalOpen(true);
            }}
          >
            + Add Course
          </button>
        </div>
      </header>

      {loading && <p className="status-line">Loading course state...</p>}
      {!liveAvailable && <p className="status-line">{liveError ?? "Live data unavailable."}</p>}
      {mutationError && <p className="status-line error">{mutationError}</p>}
      {availableCourses.length === 0 && (
        <p className="status-line">No courses yet. Use Add Course above.</p>
      )}

      <div className="gaps-page-controls">
        <div className="gaps-page-filters">
          {([
            { id: "all", label: "All" },
            { id: "selected", label: "Selected" },
            { id: "with_docs", label: "With Docs" },
            { id: "attention", label: "Needs Attention" },
          ] as const).map((item) => (
            <button
              key={item.id}
              type="button"
              className={`filter ${filter === item.id ? "active" : ""}`}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="gaps-page-sort">
          <span className="gaps-sort-label">Sort:</span>
          {([
            { id: "name", label: "Name" },
            { id: "docs", label: "Docs" },
            { id: "gaps", label: "Open Gaps" },
          ] as const).map((item) => (
            <button
              key={item.id}
              type="button"
              className={`filter ${sortBy === item.id ? "active" : ""}`}
              onClick={() => setSortBy(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <input
          type="search"
          placeholder="Search courses..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="gaps-search"
          aria-label="Search courses"
        />
      </div>

      <div className="gaps-page-layout">
        <div className="gap-list gap-list-full">
          {filteredAndSorted.map((course) => {
            const deleting = deletingCourseId === course.id;

            return (
              <article
                key={course.id}
                className={`gap-row-card gap-row-card-clickable ${course.isActive ? "courses-row-active" : ""}`}
                onClick={() => setCourseId(course.id)}
              >
                <div className="gap-row-card-accent" aria-hidden />
                <div className="gap-row-card-main">
                  <div className="gap-row-card-head">
                    <h4 className="gap-row-card-title">{course.name}</h4>
                    <span className="pill pill-course-badge">{course.id.toUpperCase()}</span>
                  </div>
                  <div className="gap-row-card-meta">
                    <span className="gap-relative-time">Docs: {course.docsCount}</span>
                    <span className="gap-relative-time">Open Gaps: {course.openGaps}</span>
                    <button
                      type="button"
                      className="gap-row-action-btn"
                      onClick={(event) => {
                        event.stopPropagation();
                        setCourseId(course.id);
                      }}
                    >
                      Select
                    </button>
                    <button
                      type="button"
                      className="gap-row-action-btn"
                      disabled={deleting}
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleDeleteCourse(course.id);
                      }}
                    >
                      {deleting ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
          {filteredAndSorted.length === 0 && (
            <p className="status-line">No courses match the selected filters.</p>
          )}
        </div>
      </div>

      {courseModalOpen && (
        <div className="course-create-backdrop" onClick={() => !creatingCourse && setCourseModalOpen(false)}>
          <div className="course-create-modal" onClick={(event) => event.stopPropagation()}>
            <div className="course-create-header">
              <h2>Add Course</h2>
              <button
                type="button"
                className="top-bar-btn"
                onClick={() => setCourseModalOpen(false)}
                disabled={creatingCourse}
              >
                Close
              </button>
            </div>
            <div className="course-create-form">
              <label className="quiz-config-label" htmlFor="courses-page-course-code">
                Course Code
              </label>
              <input
                id="courses-page-course-code"
                className="quiz-count-input"
                value={newCourseCode}
                placeholder="e.g. cs2040"
                onChange={(event) => setNewCourseCode(event.target.value)}
                disabled={creatingCourse}
              />
              <label className="quiz-config-label" htmlFor="courses-page-course-title">
                Course Title
              </label>
              <input
                id="courses-page-course-title"
                className="quiz-count-input"
                value={newCourseTitle}
                placeholder="e.g. Data Structures and Algorithms"
                onChange={(event) => setNewCourseTitle(event.target.value)}
                disabled={creatingCourse}
              />
              {courseCreateError && (
                <p className="status-line error" role="alert">
                  {courseCreateError}
                </p>
              )}
              <div className="course-create-actions">
                <button
                  type="button"
                  className="top-bar-btn primary"
                  onClick={() => void handleCreateCourse()}
                  disabled={creatingCourse}
                >
                  {creatingCourse ? "Creating..." : "Create Course"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
