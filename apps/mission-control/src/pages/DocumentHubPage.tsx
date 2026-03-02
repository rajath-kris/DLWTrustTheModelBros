import { useRef } from "react";
import { useCourse } from "../context/CourseContext";
import { DocumentHub } from "../components/DocumentHub";

export function DocumentHubPage() {
  const { courseId, courseData } = useCourse();
  const uploadClickRef = useRef<(() => void) | null>(null);
  const count = courseData?.documents?.length ?? 0;
  const courseBadge = courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

  return (
    <div className="page-shell page-fade">
      <header className="docs-page-header">
        <div className="docs-page-title-row">
          <h1>Document Hub</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <span className="pill pill-docs-uploaded">{count} Uploaded</span>
          <button type="button" className="top-bar-btn primary" onClick={() => uploadClickRef.current?.()}>
            + Upload
          </button>
        </div>
      </header>
      <DocumentHub
        sectionId="document-hub-page"
        documents={courseId === "all" ? undefined : courseData?.documents}
        hideHeader
        showRowActions
        onUploadClickRef={uploadClickRef}
      />
      <p className="docs-page-footer">
        The Syllabus Anchor grounds Sentinel AI in your course boundaries and keeps guidance aligned with your materials.
      </p>
    </div>
  );
}
