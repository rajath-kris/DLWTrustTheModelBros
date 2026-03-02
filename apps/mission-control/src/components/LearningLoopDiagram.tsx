import { useState, useCallback, useEffect } from "react";

interface PipelineNodeConfig {
  id: string;
  emoji: string;
  borderColor: string;
  label: string;
  title: string;
  description: string;
  snippet?: string;
}

const PIPELINE_NODES: PipelineNodeConfig[] = [
  {
    id: "eye",
    emoji: "👁️",
    borderColor: "#14b8a6",
    label: "Student reads PDF / IDE / Browser",
    title: "The Eye: Sentinel Capture",
    description:
      "Learning happens in your tools—PDFs, IDEs, and the browser. Sentinel stays out of the way until you need it. When you hit a moment of confusion, you're already in context; the Eye is the bridge from that context to guided insight.",
  },
  {
    id: "trigger",
    emoji: "⌨️",
    borderColor: "#f97316",
    label: "Alt+S triggers Sentinel capture",
    title: "Trigger: Global Hotkey",
    description:
      "A single global hotkey (Alt+S) opens the region selector from any app. You draw a box around the content you're stuck on—an equation, a code snippet, or a diagram. No switching apps, no copy-paste. The capture includes platform, active window, and the cropped image.",
    snippet: "# Global hotkey (Alt+S) opens region capture\n# Sentinel captures cropped region + metadata",
  },
  {
    id: "ai",
    emoji: "🤖",
    borderColor: "#a855f7",
    label: "Azure AI Vision interprets content",
    title: "AI: Vision + Socratic Prompting",
    description:
      "The cropped image is sent to the bridge API, which uses Azure AI Vision for OCR, captioning, and tagging. A Socratic prompt is generated—guiding questions anchored to your syllabus, not final answers. Structured gaps are extracted for the Brain.",
  },
  {
    id: "brain",
    emoji: "🧠",
    borderColor: "#3b82f6",
    label: "The Brain updates Radar & Gaps",
    title: "The Brain: Mission Control",
    description:
      "Capture evidence is stored and the state store is updated with new gaps and readiness axes. The radar and gap list in Mission Control reflect your current mastery and deadlines. GET /api/v1/state and SSE keep the dashboard live.",
  },
  {
    id: "insight",
    emoji: "💡",
    borderColor: "#22c55e",
    label: "Student gains insight without context switch",
    title: "Insight: Stay in Flow",
    description:
      "The overlay returns a Socratic prompt and optional gap summary. You get guidance in place, then close with Esc. No tab switching, no losing focus. Insights feed back into the Brain so your next session starts from an up-to-date picture.",
  },
];

export function LearningLoopDiagram() {
  const [modalId, setModalId] = useState<string | null>(null);
  const selected = modalId ? PIPELINE_NODES.find((n) => n.id === modalId) : null;

  const openModal = useCallback((id: string) => setModalId(id), []);
  const closeModal = useCallback(() => setModalId(null), []);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) closeModal();
    },
    [closeModal]
  );

  useEffect(() => {
    if (!modalId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalId, closeModal]);

  return (
    <>
      <article className="card learning-pipeline-card">
        <span className="learning-pipeline-badge">App-Agnostic</span>
        <header>
          <h3>The Learning Pipeline</h3>
          <p>Eye → Trigger → AI → Brain → Insight.</p>
        </header>
        <div className="learning-pipeline-diagram" role="img" aria-label="Learning pipeline flow">
          <div className="learning-pipeline-row">
            {PIPELINE_NODES.map((node, index) => (
              <div key={node.id} className="learning-pipeline-cell">
                <button
                  type="button"
                  className="learning-pipeline-node"
                  style={{ ["--node-color" as string]: node.borderColor }}
                  onClick={() => openModal(node.id)}
                  title={node.title}
                >
                  <span className="learning-pipeline-node-emoji" aria-hidden>
                    {node.emoji}
                  </span>
                </button>
                <p className="learning-pipeline-node-label">{node.label}</p>
                {index < PIPELINE_NODES.length - 1 && (
                  <span className="learning-pipeline-arrow" aria-hidden>
                    →
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </article>

      {selected && (
        <div
          className="learning-pipeline-backdrop"
          onClick={handleBackdropClick}
          onKeyDown={(e) => e.key === "Escape" && closeModal()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="pipeline-modal-title"
        >
          <div className="learning-pipeline-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="learning-pipeline-modal-close"
              onClick={closeModal}
              aria-label="Close"
            >
              ×
            </button>
            <h2 id="pipeline-modal-title" className="learning-pipeline-modal-title">
              {selected.title}
            </h2>
            <p className="learning-pipeline-modal-description">{selected.description}</p>
            {selected.snippet && (
              <pre className="learning-pipeline-modal-snippet">
                <code>{selected.snippet}</code>
              </pre>
            )}
          </div>
        </div>
      )}
    </>
  );
}
