import { useCallback, useState, useEffect, useRef } from "react";
import { MOCK_DOCUMENTS, type MockDocument } from "../data/mockDocuments";

const DOC_HUB_SECTION_ID = "document-hub";

const DOC_ICON = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
  </svg>
);

export function DocumentHub({
  sectionId = DOC_HUB_SECTION_ID,
  documents: initialDocuments,
  hideHeader = false,
  showRowActions = false,
  onUploadClickRef,
}: {
  sectionId?: string;
  documents?: MockDocument[];
  hideHeader?: boolean;
  showRowActions?: boolean;
  /** Set from parent so "+ Upload" can trigger file input. */
  onUploadClickRef?: React.MutableRefObject<(() => void) | null>;
}) {
  const [documents, setDocuments] = useState<MockDocument[]>(initialDocuments ?? MOCK_DOCUMENTS);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const openFileDialog = useCallback(() => fileInputRef.current?.click(), []);
  useEffect(() => {
    if (onUploadClickRef) onUploadClickRef.current = openFileDialog;
    return () => { if (onUploadClickRef) onUploadClickRef.current = null; };
  }, [onUploadClickRef, openFileDialog]);

  useEffect(() => {
    if (initialDocuments != null) setDocuments(initialDocuments);
  }, [initialDocuments]);
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    handleFiles(Array.from(files));
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    handleFiles(Array.from(files));
    e.target.value = "";
  }, []);

  function handleFiles(files: File[]) {
    setUploadError(null);
    console.log("Document upload (placeholder):", files.map((f) => f.name));
    setUploadError("Upload not yet connected to bridge.");
  }

  return (
    <article id={sectionId} className="card document-hub-card">
      {!hideHeader && (
        <header className="document-hub-head-new">
          <h3>Document Hub</h3>
          <span className="pill pill-docs-uploaded">{documents.length} Uploaded</span>
        </header>
      )}

      <div
        className={`document-hub-dropzone document-hub-dropzone-compact ${dragging ? "dragging" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt"
          onChange={handleFileInput}
          className="document-hub-input"
          aria-label="Choose files to upload"
        />
        <div className="document-hub-drop-icon" aria-hidden>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
            <line x1="12" y1="11" x2="12" y2="17" />
            <line x1="9" y1="14" x2="15" y2="14" />
          </svg>
        </div>
        <p className="document-hub-drop-text">Drag & drop or click to upload / PDFs, Word docs, syllabi, lecture notes.</p>
      </div>

      {uploadError && <p className="status-line error">{uploadError}</p>}

      <ul className="document-hub-list document-hub-list-new">
        {documents.length === 0 ? (
          <li className="status-line">No documents yet.</li>
        ) : (
          documents.map((doc) => (
            <li key={doc.name} className={`document-hub-item-new ${showRowActions ? "document-hub-item-with-actions" : ""}`}>
              <div className="document-hub-item-icon" aria-hidden>
                {DOC_ICON}
              </div>
              <div className="document-hub-item-body">
                <span className="document-hub-item-name">{doc.name}</span>
                <span className="document-hub-item-meta">
                  {doc.size} · {doc.upload_date}
                </span>
              </div>
              {doc.type === "anchor" && (
                <span className="pill pill-syllabus-anchor">Syllabus Anchor</span>
              )}
              {showRowActions && (
                <div className="document-hub-item-actions">
                  <button type="button" className="doc-hub-action-btn">Preview</button>
                  <button type="button" className="doc-hub-action-btn">{doc.type === "anchor" ? "Anchor" : "Set as Anchor"}</button>
                  <button type="button" className="doc-hub-action-btn doc-hub-action-delete">Delete</button>
                </div>
              )}
            </li>
          ))
        )}
      </ul>
    </article>
  );
}
