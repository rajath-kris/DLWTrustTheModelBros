import { useEffect, useMemo, useRef, useState } from "react";
import { fetchActiveModule, fetchModules } from "../api";
import { useCourse } from "../context/CourseContext";
import { useBrainState } from "../context/BrainStateContext";
import { DocumentHub } from "../components/DocumentHub";
import type { MockDocument } from "../data/mockDocuments";
import type { ModuleSummary } from "../types";

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

export function DocumentHubPage() {
  const { courseId, courseData, allCoursesSummary, courses, liveAvailable, liveError } = useCourse();
  const { state, uploadCourseDocument, anchorCourseDocument, removeCourseDocument } = useBrainState();
  const uploadClickRef = useRef<(() => void) | null>(null);

  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [moduleLoadError, setModuleLoadError] = useState<string | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState(courseId === "all" ? "" : courseId);
  const [selectedModuleId, setSelectedModuleId] = useState("");

  useEffect(() => {
    setSelectedCourseId(courseId === "all" ? "" : courseId);
  }, [courseId]);

  useEffect(() => {
    let active = true;

    async function hydrateModules() {
      try {
        const [moduleList, activeModule] = await Promise.all([fetchModules(), fetchActiveModule()]);
        if (!active) {
          return;
        }
        setModules(moduleList.modules);
        const preferredModuleId =
          activeModule.active_module_id ||
          moduleList.active_module_id ||
          moduleList.modules[0]?.module_id ||
          "";
        setSelectedModuleId((current) => current || preferredModuleId);
        setModuleLoadError(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setModuleLoadError(error instanceof Error ? error.message : "Could not load modules.");
      }
    }

    void hydrateModules();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedModuleId) {
      return;
    }
    if (modules.some((module) => module.module_id === selectedModuleId)) {
      return;
    }
    setSelectedModuleId(modules[0]?.module_id ?? "");
  }, [modules, selectedModuleId]);

  const moduleNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const module of modules) {
      map.set(module.module_id, module.module_name);
    }
    return map;
  }, [modules]);

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
          module_id: doc.module_id,
          course_label: formatCourseLabel(doc.course_id),
          module_label: moduleNameById.get(doc.module_id) || doc.module_id,
          name: doc.name,
          size: `${Math.max(1, Math.round(doc.size_bytes / 1024))} KB`,
          upload_date: doc.uploaded_at.split("T")[0] ?? doc.uploaded_at,
          type: classifyDocumentType(doc.type, doc.is_anchor),
          path: doc.file_url,
          is_anchor: doc.is_anchor,
        })),
    [state.documents, courseId, moduleNameById]
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
  const canUpload = Boolean(selectedModuleId) && (courseId !== "all" || Boolean(selectedCourseId));

  const uploadRequirementHint = modules.length === 0
    ? "No modules available. Create a module before uploading."
    : courseId === "all" && !selectedCourseId
      ? "Select a course and module before uploading."
      : !selectedModuleId
        ? "Select a module before uploading."
        : undefined;

  async function handleUpload(files: File[]) {
    const targetCourse = courseId === "all" ? selectedCourseId : courseId;
    if (!targetCourse || targetCourse === "all") {
      throw new Error("Select a target course before uploading.");
    }
    if (!selectedModuleId) {
      throw new Error("Select a target module before uploading.");
    }
    for (const file of files) {
      await uploadCourseDocument(targetCourse, selectedModuleId, file);
    }
  }

  async function handleSetAnchor(doc: MockDocument) {
    const targetCourse = doc.course_id || (courseId === "all" ? selectedCourseId : courseId);
    if (!doc.doc_id || !targetCourse || targetCourse === "all") {
      throw new Error("Could not resolve the document course for anchoring.");
    }
    await anchorCourseDocument(targetCourse, doc.doc_id);
  }

  async function handleDelete(doc: MockDocument) {
    const targetCourse = doc.course_id || (courseId === "all" ? selectedCourseId : courseId);
    if (!doc.doc_id || !targetCourse || targetCourse === "all") {
      throw new Error("Could not resolve the document course for deletion.");
    }
    await removeCourseDocument(targetCourse, doc.doc_id);
  }

  return (
    <div className="page-shell page-fade">
      <header className="docs-page-header">
        <div className="docs-page-title-row">
          <h1>Document Hub</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <span className="pill pill-docs-uploaded">{count} Uploaded</span>
          <button
            type="button"
            className="top-bar-btn primary"
            onClick={() => uploadClickRef.current?.()}
            disabled={!canUpload}
          >
            + Upload
          </button>
        </div>
        <div className="docs-upload-controls">
          {courseId === "all" && (
            <label className="docs-upload-control">
              <span>Course</span>
              <select
                value={selectedCourseId}
                onChange={(event) => setSelectedCourseId(event.target.value)}
                aria-label="Select course for upload"
              >
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
            <span>Module</span>
            <select
              value={selectedModuleId}
              onChange={(event) => setSelectedModuleId(event.target.value)}
              aria-label="Select module for upload"
            >
              <option value="">Select module</option>
              {modules.map((module) => (
                <option key={module.module_id} value={module.module_id}>
                  {module.module_name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      {!liveAvailable && (
        <p className="status-line">{liveError ?? "Live data unavailable. Showing fallback data where possible."}</p>
      )}
      {moduleLoadError && (
        <p className="status-line error">{moduleLoadError}</p>
      )}
      {courseId === "all" && selectedCourseId && (
        <p className="status-line">
          Upload target course: {courseNameById.get(selectedCourseId) || selectedCourseId}
        </p>
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
        onDeleteDocument={handleDelete}
      />
      <p className="docs-page-footer">
        The Syllabus Anchor grounds Sentinel AI in your course boundaries and keeps guidance aligned with your materials.
      </p>
    </div>
  );
}
