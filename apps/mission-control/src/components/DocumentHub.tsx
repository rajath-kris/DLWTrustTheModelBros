import { useCallback, useEffect, useRef, useState } from "react";
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
  uploadEnabled = true,
  uploadRequirementHint,
  onUploadClickRef,
  onUploadFiles,
  onSetAnchor,
  onMoveTopic,
  onDeleteDocument,
  topicOptions = [],
}: {
  sectionId?: string;
  documents?: MockDocument[];
  hideHeader?: boolean;
  showRowActions?: boolean;
  uploadEnabled?: boolean;
  uploadRequirementHint?: string;
  onUploadClickRef?: React.MutableRefObject<(() => void) | null>;
  onUploadFiles?: (files: File[]) => Promise<void>;
  onSetAnchor?: (doc: MockDocument) => Promise<void>;
  onMoveTopic?: (doc: MockDocument, topicId: string) => Promise<void>;
  onDeleteDocument?: (doc: MockDocument) => Promise<void>;
  topicOptions?: Array<{ topic_id: string; topic_name: string }>;
}) {
  const [documents, setDocuments] = useState<MockDocument[]>(initialDocuments ?? MOCK_DOCUMENTS);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const openFileDialog = useCallback(() => {
    if (!uploadEnabled) {
      return;
    }
    fileInputRef.current?.click();
  }, [uploadEnabled]);

  useEffect(() => {
    if (onUploadClickRef) {
      onUploadClickRef.current = openFileDialog;
    }
    return () => {
      if (onUploadClickRef) {
        onUploadClickRef.current = null;
      }
    };
  }, [onUploadClickRef, openFileDialog]);

  useEffect(() => {
    if (initialDocuments != null) {
      setDocuments(initialDocuments);
    }
  }, [initialDocuments]);

  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [workingDocId, setWorkingDocId] = useState<string | null>(null);
  const [moveSelectionByDocId, setMoveSelectionByDocId] = useState<Record<string, string>>({});

  useEffect(() => {
    setMoveSelectionByDocId((current) => {
      const next = { ...current };
      for (const doc of documents) {
        if (!doc.doc_id || next[doc.doc_id]) {
          continue;
        }
        next[doc.doc_id] = (doc.topic_id || "").toString();
      }
      return next;
    });
  }, [documents]);

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!uploadEnabled) {
        return;
      }
      setDragging(true);
    },
    [uploadEnabled]
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!uploadEnabled) {
        return;
      }
      setDragging(false);
    },
    [uploadEnabled]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!uploadEnabled) {
        return;
      }
      setDragging(false);
      const files = e.dataTransfer?.files;
      if (!files?.length) {
        return;
      }
      void handleFiles(Array.from(files));
    },
    [uploadEnabled]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!uploadEnabled) {
        return;
      }
      const files = e.target.files;
      if (!files?.length) {
        return;
      }
      void handleFiles(Array.from(files));
      e.target.value = "";
    },
    [uploadEnabled]
  );

  async function handleFiles(files: File[]) {
    setUploadError(null);
    if (onUploadFiles) {
      try {
        await onUploadFiles(files);
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : "Upload failed.");
      }
      return;
    }
    setUploadError("Live upload is unavailable for this view.");
  }

  async function handleSetAnchor(doc: MockDocument) {
    if (!onSetAnchor || !doc.doc_id) {
      return;
    }
    setUploadError(null);
    setWorkingDocId(doc.doc_id);
    try {
      await onSetAnchor(doc);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not set document anchor.");
    } finally {
      setWorkingDocId(null);
    }
  }

  async function handleDelete(doc: MockDocument) {
    if (!onDeleteDocument || !doc.doc_id) {
      return;
    }
    setUploadError(null);
    setWorkingDocId(doc.doc_id);
    try {
      await onDeleteDocument(doc);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not delete document.");
    } finally {
      setWorkingDocId(null);
    }
  }

  async function handleMoveTopic(doc: MockDocument) {
    if (!onMoveTopic || !doc.doc_id) {
      return;
    }
    const targetTopicId = (moveSelectionByDocId[doc.doc_id] || "").trim();
    const currentTopicId = (doc.topic_id || "").trim();
    if (!targetTopicId || targetTopicId === currentTopicId) {
      return;
    }
    setUploadError(null);
    setWorkingDocId(doc.doc_id);
    try {
      await onMoveTopic(doc, targetTopicId);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not move document to selected topic.");
    } finally {
      setWorkingDocId(null);
    }
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
        className={`document-hub-dropzone document-hub-dropzone-compact ${dragging ? "dragging" : ""} ${
          uploadEnabled ? "" : "upload-disabled"
        }`}
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
          disabled={!uploadEnabled}
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
        <p className="document-hub-drop-text">
          {uploadEnabled
            ? "Drag & drop or click to upload / PDFs, Word docs, syllabi, lecture notes."
            : uploadRequirementHint || "Select required tags before uploading."}
        </p>
      </div>

      {uploadError && <p className="status-line error">{uploadError}</p>}

      <ul className="document-hub-list document-hub-list-new">
        {documents.length === 0 ? (
          <li className="status-line">No documents yet.</li>
        ) : (
          documents.map((doc) => (
            <li
              key={doc.doc_id ?? `${doc.name}-${doc.upload_date}`}
              className={`document-hub-item-new ${showRowActions ? "document-hub-item-with-actions" : ""}`}
            >
              <div className="document-hub-item-icon" aria-hidden>
                {DOC_ICON}
              </div>
              <div className="document-hub-item-body">
                <span className="document-hub-item-name">{doc.name}</span>
                <span className="document-hub-item-meta">
                  {doc.size} | {doc.upload_date}
                </span>
                {showRowActions && (doc.course_label || doc.course_id || doc.topic_label || doc.topic_id) && (
                  <div className="document-hub-item-tags">
                    {(doc.course_label || doc.course_id) && (
                      <span className="pill pill-doc-tag">{(doc.course_label || doc.course_id || "").toString()}</span>
                    )}
                    {(doc.topic_label || doc.topic_id) && (
                      <span className="pill pill-doc-tag pill-doc-tag-topic">{(doc.topic_label || doc.topic_id || "").toString()}</span>
                    )}
                  </div>
                )}
              </div>
              {(doc.type === "anchor" || doc.is_anchor) && <span className="pill pill-syllabus-anchor">Syllabus Anchor</span>}
              {showRowActions && (
                <div className="document-hub-item-actions">
                  <button type="button" className="doc-hub-action-btn" onClick={() => doc.path && window.open(doc.path, "_blank", "noopener,noreferrer")}>
                    Preview
                  </button>
                  <button
                    type="button"
                    className="doc-hub-action-btn"
                    disabled={!doc.doc_id || !onSetAnchor || workingDocId === doc.doc_id}
                    onClick={() => void handleSetAnchor(doc)}
                  >
                    {doc.type === "anchor" || doc.is_anchor ? "Anchor" : "Set as Anchor"}
                  </button>
                  <button
                    type="button"
                    className="doc-hub-action-btn doc-hub-action-delete"
                    disabled={!doc.doc_id || !onDeleteDocument || workingDocId === doc.doc_id}
                    onClick={() => void handleDelete(doc)}
                  >
                    Delete
                  </button>
                  <select
                    className="doc-hub-topic-select"
                    aria-label={`Select target topic for ${doc.name}`}
                    value={doc.doc_id ? moveSelectionByDocId[doc.doc_id] ?? (doc.topic_id || "") : ""}
                    disabled={!doc.doc_id || workingDocId === doc.doc_id || topicOptions.length === 0}
                    onChange={(event) => {
                      if (!doc.doc_id) {
                        return;
                      }
                      const nextValue = event.target.value;
                      setMoveSelectionByDocId((current) => ({ ...current, [doc.doc_id as string]: nextValue }));
                    }}
                  >
                    <option value="">Move to topic</option>
                    {topicOptions.map((topic) => (
                      <option key={topic.topic_id} value={topic.topic_id}>
                        {topic.topic_name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="doc-hub-action-btn"
                    disabled={
                      !doc.doc_id ||
                      !onMoveTopic ||
                      workingDocId === doc.doc_id ||
                      topicOptions.length === 0 ||
                      !(moveSelectionByDocId[doc.doc_id] || "").trim() ||
                      (moveSelectionByDocId[doc.doc_id] || "").trim() === (doc.topic_id || "").trim()
                    }
                    onClick={() => void handleMoveTopic(doc)}
                  >
                    Move
                  </button>
                </div>
              )}
            </li>
          ))
        )}
      </ul>
    </article>
  );
}
