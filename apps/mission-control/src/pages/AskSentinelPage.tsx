import { useState, useRef, useEffect } from "react";
import { useCourse } from "../context/CourseContext";

type Message = { role: "user" | "assistant"; text: string; citations?: string[] };

const QUICK_CHIPS = [
  "Explain my weakest topic",
  "Quiz me on Binary Trees",
  "Summarize Lecture_07",
  "What should I study today?",
  "What gaps do I have in Dynamic Programming?",
];

const MOCK_RESPONSE = "Here’s a concise breakdown based on your syllabus and recent captures. **Binary Trees**: focus on traversal order and recursive structure. Try drawing a small tree and listing pre/in/post order. Code snippet:\n\n```\nfunction inorder(node) {\n  if (!node) return;\n  inorder(node.left);\n  visit(node);\n  inorder(node.right);\n}\n```\n\n*Based on CS2040_Syllabus.pdf and your Gap #2.*";

export function AskSentinelPage() {
  const { courseId, courseData } = useCourse();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const courseBadge = courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = (text: string) => {
    if (!text.trim()) return;
    const userMsg: Message = { role: "user", text: text.trim() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setStreaming(true);
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: MOCK_RESPONSE, citations: ["CS2040_Syllabus.pdf"] },
      ]);
      setStreaming(false);
    }, 800);
  };

  const handleChip = (chip: string) => {
    send(chip);
  };

  return (
    <div className="page-shell page-fade ask-sentinel-page">
      <header className="ask-page-header">
        <div className="ask-page-title-row">
          <h1>Ask Sentinel</h1>
          <span className="ask-pulse" title="Active">●</span>
          <span className="pill pill-course-badge">{courseBadge}</span>
        </div>
      </header>

      <div className="ask-layout">
        <aside className={`ask-history-panel ${historyOpen ? "open" : ""}`}>
          <div className="ask-history-header">
            <h3>History</h3>
            <button type="button" className="ask-history-close" onClick={() => setHistoryOpen(false)} aria-label="Close">×</button>
          </div>
          <ul className="ask-history-list">
            <li className="ask-history-item">Today — Weakest topic</li>
            <li className="ask-history-item">Yesterday — Quiz prep</li>
          </ul>
        </aside>
        <div className="ask-main">
          <div className="ask-messages-wrap" ref={listRef}>
            {messages.length === 0 ? (
              <div className="ask-empty">
                <p className="ask-empty-prompt">Ask anything about your course.</p>
                <div className="ask-chips">
                  {QUICK_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      className="ask-chip"
                      onClick={() => handleChip(chip)}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <ul className="ask-message-list">
                {messages.map((msg, i) => (
                  <li key={i} className={`ask-msg ask-msg-${msg.role}`}>
                    <div className="ask-msg-bubble">
                      {msg.role === "assistant" ? (
                        <div className="ask-msg-content ask-msg-markdown">
                          {msg.text.split("```").map((part, j) =>
                            j % 2 === 1 ? (
                              <pre key={j} className="ask-code-block"><code>{part.trim()}</code></pre>
                            ) : (
                              <span key={j}>{part.replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1")}</span>
                            )
                          )}
                        </div>
                      ) : (
                        <p className="ask-msg-content">{msg.text}</p>
                      )}
                      {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                        <p className="ask-citations">Based on {msg.citations.join(", ")}</p>
                      )}
                    </div>
                  </li>
                ))}
                {streaming && (
                  <li className="ask-msg ask-msg-assistant">
                    <div className="ask-msg-bubble">
                      <span className="ask-typing">Thinking…</span>
                    </div>
                  </li>
                )}
              </ul>
            )}
          </div>
          <form
            className="ask-input-wrap"
            onSubmit={(e) => { e.preventDefault(); send(input); }}
          >
            <button type="button" className="ask-attach-btn" aria-label="Attach">📎</button>
            <input
              type="text"
              className="ask-input"
              placeholder={`Ask Sentinel anything about ${courseBadge}…`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button type="submit" className="ask-send-btn">Send</button>
          </form>
        </div>
        {!historyOpen && (
          <button type="button" className="ask-history-toggle" onClick={() => setHistoryOpen(true)}>
            History
          </button>
        )}
      </div>
    </div>
  );
}
