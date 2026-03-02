import { useRef } from "react";
import { useCourse } from "../context/CourseContext";
import { useBrainState } from "../context/BrainStateContext";
import { DocumentHub } from "../components/DocumentHub";
import type { MockDocument } from "../data/mockDocuments";

function classifyDocumentType(rawType: string, isAnchor: boolean): MockDocument["type"] {
  if (isAnchor) {
    return "anchor";
  }
  return rawType.toLowerCase().includes("pdf") ? "pdf" : "other";
}

export function DocumentHubPage() {
  const { courseId, courseData, liveAvailable, liveError } = useCourse();
  const { state, uploadCourseDocument, anchorCourseDocument, removeCourseDocument } = useBrainState();
  const uploadClickRef = useRef<(() => void) | null>(null);
  const allLiveDocuments: MockDocument[] = state.documents.map((doc) => ({
    doc_id: doc.doc_id,
    name: doc.name,
    size: `${Math.max(1, Math.round(doc.size_bytes / 1024))} KB`,
    upload_date: doc.uploaded_at.split("T")[0] ?? doc.uploaded_at,
    type: classifyDocumentType(doc.type, doc.is_anchor),
    path: doc.file_url,
    is_anchor: doc.is_anchor,
  }));
  const documentRows = courseId === "all"
    ? (liveAvailable || allLiveDocuments.length > 0 ? allLiveDocuments : undefined)
    : courseData?.documents;
  const count = documentRows?.length ?? 0;
  const courseBadge = courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

  async function handleUpload(files: File[]) {
    const targetCourse = courseId === "all" ? "all" : courseId;
    for (const file of files) {
      await uploadCourseDocument(targetCourse, file);
    }
  }

  async function handleSetAnchor(docId: string) {
    const targetCourse = courseId === "all" ? "all" : courseId;
    await anchorCourseDocument(targetCourse, docId);
  }

  async function handleDelete(docId: string) {
    const targetCourse = courseId === "all" ? "all" : courseId;
    await removeCourseDocument(targetCourse, docId);
  }

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
      {!liveAvailable && (
        <p className="status-line">{liveError ?? "Live data unavailable. Showing fallback data where possible."}</p>
      )}
      <DocumentHub
        sectionId="document-hub-page"
        documents={documentRows}
        hideHeader
        showRowActions
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
