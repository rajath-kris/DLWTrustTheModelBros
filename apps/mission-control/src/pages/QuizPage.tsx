import { useEffect, useMemo, useState } from "react";

import { fetchTopicsForCourse } from "../api";
import { useBrainState } from "../context/BrainStateContext";
import { useCourse } from "../context/CourseContext";
import type {
  QuestionBankItem,
  QuizRecord,
  QuizSelectionSummary,
  QuizSourceType,
  QuizSubmitResponse,
  TopicSummary,
} from "../types";

const ALL_TOPICS = "All Topics";
const ALL_TOPICS_ID = "__all_topics__";
const ALL_SOURCES: QuizSourceType[] = ["pyq", "tutorial", "sentinel"];

const SOURCE_LABEL: Record<QuizSourceType, string> = {
  pyq: "PYQ",
  tutorial: "Tutorial",
  sentinel: "Sentinel",
};

/* Inline SVG icons for quiz page */
const QuizIcons = {
  check: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  cross: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  circle: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
    </svg>
  ),
  play: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  ),
  clipboard: (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="M9 14h6M9 18h6" />
    </svg>
  ),
  trophy: (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z" />
      <path d="M7 4V2h10v2M7 8V6a5 5 0 0 0 10 0V8" />
      <path d="M5 8H4a2 2 0 0 0-2 2v1a2 2 0 0 0 2 2h1M19 8h1a2 2 0 0 1 2 2v1a2 2 0 0 1-2 2h-1M8 12h8" />
    </svg>
  ),
  clock: (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
};

type QuizSession = {
  sessionId: string;
  topic: string;
  topicId: string | null;
  courseId: string;
  questions: QuestionBankItem[];
  currentIndex: number;
  answers: Record<string, string>;
  submitted: Record<string, boolean>;
};

function normalized(value: string): string {
  return value.trim().toLowerCase();
}

function scorePercent(result: QuizSubmitResponse): number {
  return Math.round(result.quiz.score * 100);
}

function ConnectionBadge({
  loading,
  error,
  liveAvailable,
}: {
  loading: boolean;
  error: string | null;
  liveAvailable: boolean;
}) {
  const connected = liveAvailable && !error;
  const statusClass = connected ? "connected" : loading ? "loading" : "disconnected";
  const label = connected ? "Connected" : loading ? "Loading…" : "Disconnected";
  return (
    <span className={`quiz-connection-badge ${statusClass}`} role="status" aria-live="polite">
      <span className="quiz-connection-badge-dot" aria-hidden />
      {label}
    </span>
  );
}

export function QuizPage() {
  const { courseId, courseData, setCourseId } = useCourse();
  const { state, loading, error: stateError, liveAvailable, prepareQuiz, submitQuiz } = useBrainState();
  /** Quiz runs in current course context; no course selector in UI. */
  const activeCourseId = courseId === "all" ? null : courseId;
  const [selectedTopicKey, setSelectedTopicKey] = useState<string>(ALL_TOPICS_ID);
  const [selectedSources, setSelectedSources] = useState<QuizSourceType[]>([...ALL_SOURCES]);
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [session, setSession] = useState<QuizSession | null>(null);
  const [historyFilterCourseId, setHistoryFilterCourseId] = useState<string>("all");
  const [submitting, setSubmitting] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [result, setResult] = useState<QuizSubmitResponse | null>(null);
  const [selectionSummary, setSelectionSummary] = useState<QuizSelectionSummary | null>(null);
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [topicLoadError, setTopicLoadError] = useState<string | null>(null);
  const [localQuizHistory, setLocalQuizHistory] = useState<QuizRecord[]>(() => {
    try {
      const raw = localStorage.getItem("quiz-history");
      if (!raw) return [];
      const parsed = JSON.parse(raw) as QuizRecord[];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("quiz-history", JSON.stringify(localQuizHistory));
    } catch {
      /* ignore */
    }
  }, [localQuizHistory]);

  useEffect(() => {
    if (!session) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [session]);

  const scopedQuestions = useMemo(() => {
    if (!activeCourseId) return [];
    return state.question_bank.filter((item) => {
      return normalized(item.course_id) === "all" || normalized(item.course_id) === normalized(activeCourseId);
    });
  }, [state.question_bank, activeCourseId]);

  useEffect(() => {
    if (!activeCourseId) {
      setTopics([]);
      setTopicLoadError(null);
      return;
    }

    let active = true;
    setTopicLoadError(null);
    void fetchTopicsForCourse(activeCourseId)
      .then((response) => {
        if (!active) {
          return;
        }
        setTopics(response.topics);
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setTopics([]);
        setTopicLoadError(error instanceof Error ? error.message : "Could not load topics for this course.");
      });

    return () => {
      active = false;
    };
  }, [activeCourseId]);

  const topicOptions = useMemo(() => {
    const options: Array<{ id: string; label: string }> = [{ id: ALL_TOPICS_ID, label: ALL_TOPICS }];
    const seenIds = new Set<string>([ALL_TOPICS_ID]);
    for (const topic of topics) {
      const id = topic.topic_id.trim();
      const label = topic.topic_name.trim();
      if (!id || !label || seenIds.has(id)) {
        continue;
      }
      seenIds.add(id);
      options.push({ id, label });
    }
    return options;
  }, [topics]);

  const selectedTopicId = useMemo(() => {
    return selectedTopicKey === ALL_TOPICS_ID ? null : selectedTopicKey;
  }, [selectedTopicKey]);

  const selectedTopicLabel = useMemo(() => {
    const match = topicOptions.find((option) => option.id === selectedTopicKey);
    return match?.label ?? ALL_TOPICS;
  }, [selectedTopicKey, topicOptions]);

  useEffect(() => {
    const valid = topicOptions.some((option) => option.id === selectedTopicKey);
    if (!valid) {
      setSelectedTopicKey(ALL_TOPICS_ID);
    }
  }, [selectedTopicKey, topicOptions]);

  const eligibleQuestions = useMemo(() => {
    const sourceFiltered = scopedQuestions.filter((item) => selectedSources.includes(item.source));
    if (!selectedTopicId) {
      return sourceFiltered;
    }
    return sourceFiltered.filter(
      (item) => normalized(item.topic_id || "") === normalized(selectedTopicId)
    );
  }, [scopedQuestions, selectedTopicId, selectedSources]);

  useEffect(() => {
    const max = Math.max(1, Math.min(25, eligibleQuestions.length));
    if (eligibleQuestions.length > 0 && questionCount > max) {
      setQuestionCount(max);
    }
  }, [eligibleQuestions.length, questionCount]);

  const history = useMemo(() => {
    const fromState = state.quizzes.filter((quiz) => {
      if (courseId === "all") return true;
      return normalized(quiz.course_id) === normalized(courseId);
    });
    const fromLocal = localQuizHistory.filter((quiz) => {
      if (courseId === "all") return true;
      return normalized(quiz.course_id) === normalized(courseId);
    });
    const seen = new Set<string>();
    const combined: QuizRecord[] = [];
    for (const q of [...fromLocal, ...fromState]) {
      if (seen.has(q.quiz_id)) continue;
      seen.add(q.quiz_id);
      combined.push(q);
    }
    let filtered = combined.sort((a, b) => b.timestamp_utc.localeCompare(a.timestamp_utc));
    if (courseId === "all" && historyFilterCourseId !== "all") {
      filtered = filtered.filter((q) => normalized(q.course_id) === normalized(historyFilterCourseId));
    }
    return filtered;
  }, [state.quizzes, localQuizHistory, courseId, historyFilterCourseId]);

  const courseNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of state.courses) {
      map.set(normalized(c.course_id), c.course_name);
    }
    return map;
  }, [state.courses]);

  const historyCourseOptions = useMemo(() => {
    const ids = new Set<string>();
    for (const quiz of [...state.quizzes, ...localQuizHistory]) {
      const id = normalized(quiz.course_id);
      if (!id || id === "all") continue;
      ids.add(id);
    }
    return Array.from(ids.values()).sort((a, b) => a.localeCompare(b));
  }, [state.quizzes, localQuizHistory]);

  function formatHistoryDate(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return `Today, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return `Yesterday, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  function handleRetake(item: QuizRecord) {
    if (item.course_id && item.course_id !== "all") {
      setCourseId(item.course_id);
    }
    const match = topics.find((topic) => normalized(topic.topic_name) === normalized(item.topic));
    setSelectedTopicKey(match?.topic_id ?? ALL_TOPICS_ID);
    setSelectedSources(item.sources.length > 0 ? [...item.sources] : [...ALL_SOURCES]);
    setQuestionCount(Math.min(25, item.total_questions));
    setSession(null);
    setResult(null);
  }

  const currentQuestion = session?.questions[session.currentIndex] ?? null;
  const currentAnswer = currentQuestion ? session?.answers[currentQuestion.question_id] ?? "" : "";
  const allAnswered = session ? session.questions.every((item) => Boolean(session.answers[item.question_id])) : false;
  const currentSubmitted = currentQuestion ? Boolean(session?.submitted[currentQuestion.question_id]) : false;
  const allSubmitted =
    session?.questions.every((item) => Boolean(session.submitted[item.question_id])) ?? false;

  function toggleSource(source: QuizSourceType) {
    setSelectedSources((existing) => {
      if (existing.includes(source)) {
        return existing.filter((item) => item !== source);
      }
      return [...existing, source];
    });
  }

  async function startQuiz() {
    if (!activeCourseId) {
      setRequestError("Select a course from the sidebar to start a quiz.");
      return;
    }
    setPreparing(true);
    setRequestError(null);
    try {
      const desiredCount = Math.max(1, Math.min(25, questionCount));
      const prepared = await prepareQuiz({
        topic: selectedTopicLabel,
        sources: selectedSources,
        question_count: desiredCount,
        course_id: activeCourseId,
        topic_id: selectedTopicId ?? undefined,
      });
      if (!prepared.questions.length) {
        if (selectedTopicId !== null) {
          const fallbackPrepared = await prepareQuiz({
            topic: ALL_TOPICS,
            sources: selectedSources,
            question_count: desiredCount,
            course_id: activeCourseId,
          });
          if (fallbackPrepared.questions.length > 0) {
            setSelectedTopicKey(ALL_TOPICS_ID);
            setResult(null);
            setSelectionSummary(fallbackPrepared.selection_summary);
            setSession({
              sessionId: fallbackPrepared.session_id,
              topic: fallbackPrepared.topic,
              topicId: null,
              courseId: activeCourseId,
              questions: fallbackPrepared.questions,
              currentIndex: 0,
              answers: {},
              submitted: {},
            });
            setRequestError(
              "No matching questions for the selected topic yet. Started with All Topics instead."
            );
            return;
          }
        }
        setRequestError("Quiz preparation returned no questions. Upload topic materials or broaden filters.");
        return;
      }
      setResult(null);
      setSelectionSummary(prepared.selection_summary);
      setSession({
        sessionId: prepared.session_id,
        topic: prepared.topic,
        topicId: selectedTopicId,
        courseId: activeCourseId,
        questions: prepared.questions,
        currentIndex: 0,
        answers: {},
        submitted: {},
      });
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Quiz preparation failed. Check bridge connection and topic/course filters.");
    } finally {
      setPreparing(false);
    }
  }

  function chooseAnswer(questionId: string, answer: string) {
    setSession((existing) => {
      if (!existing) {
        return existing;
      }
      return {
        ...existing,
        answers: { ...existing.answers, [questionId]: answer },
      };
    });
  }

  function markCurrentSubmitted() {
    if (!currentQuestion) {
      return;
    }
    if (!currentAnswer) {
      return;
    }
    setSession((existing) => {
      if (!existing) {
        return existing;
      }
      return {
        ...existing,
        submitted: { ...existing.submitted, [currentQuestion.question_id]: true },
      };
    });
  }

  async function completeQuiz() {
    if (!session) {
      return;
    }
    setSubmitting(true);
    setRequestError(null);
    try {
      const response = await submitQuiz({
        topic: session.topic,
        sources: selectedSources,
        answers: session.questions.map((item) => ({
          question_id: item.question_id,
          user_answer: session.answers[item.question_id] ?? "",
        })),
        course_id: session.courseId,
        session_id: session.sessionId,
        topic_id: session.topicId ?? undefined,
      });
      setResult(response);
      setSession(null);
      setLocalQuizHistory((prev) => [response.quiz, ...prev]);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Quiz submission failed. Please retry with bridge running.");
    } finally {
      setSubmitting(false);
    }
  }

  const startDisabled = preparing || selectedSources.length === 0 || !activeCourseId || eligibleQuestions.length === 0;

  return (
    <div className={`page-shell page-fade quiz-page ${session ? "quiz-page--active" : ""} ${result && !session ? "quiz-page--result" : ""}`}>
      <header className="quiz-header">
        <h1>Quiz{courseData?.name ? ` — ${courseData.name.split("—")[0].trim()}` : ""}</h1>
        <ConnectionBadge loading={loading} error={stateError} liveAvailable={liveAvailable} />
      </header>

      {loading && <p className="status-line">Loading quiz state…</p>}
      {stateError && <p className="status-line">{stateError}</p>}
      {topicLoadError && <p className="status-line error">{topicLoadError}</p>}
      {requestError && <p className="status-line error">{requestError}</p>}

      <div className="quiz-main">
        <div className="quiz-primary">
          <article className="card">
            <h3>Setup</h3>
            {!activeCourseId ? (
              <p className="quiz-no-course">
                Select a course from the sidebar to take a quiz in that course.
              </p>
            ) : (
              <>
            <label className="quiz-config-label" htmlFor="quiz-topic">
              Topic
            </label>
            <select
              id="quiz-topic"
              className="quiz-topic-select"
              value={selectedTopicKey}
              onChange={(event) => setSelectedTopicKey(event.target.value)}
              aria-label="Select quiz topic"
            >
              {topicOptions.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.label}
                </option>
              ))}
            </select>

            <span className="quiz-config-label">Question sources</span>
            <div className="quiz-sources-grid" style={{ marginBottom: "1rem" }}>
              {ALL_SOURCES.map((source) => {
                const selected = selectedSources.includes(source);
                return (
                  <button
                    key={source}
                    type="button"
                    className={`quiz-source-card ${selected ? "selected" : ""}`}
                    onClick={() => toggleSource(source)}
                    aria-pressed={selected}
                  >
                    {selected ? QuizIcons.check : QuizIcons.circle}
                    {SOURCE_LABEL[source]}
                  </button>
                );
              })}
            </div>

            <div className="quiz-settings-row">
              <div className="quiz-settings-block">
                <label htmlFor="quiz-count">Number of questions</label>
                <input
                  id="quiz-count"
                  type="number"
                  min={1}
                  max={Math.max(1, Math.min(25, eligibleQuestions.length))}
                  className="quiz-count-input"
                  value={questionCount}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    const max = Math.max(1, Math.min(25, eligibleQuestions.length));
                    setQuestionCount(isNaN(v) ? 1 : Math.max(1, Math.min(max, v)));
                  }}
                  aria-label="Number of questions"
                />
                {eligibleQuestions.length > 0 && questionCount > eligibleQuestions.length && (
                  <p className="quiz-available-warning" role="status">
                    Only {eligibleQuestions.length} questions available for this selection; quiz will use that many.
                  </p>
                )}
              </div>
              <div className="quiz-settings-block">
                <label>Available</label>
                <p
                  className={`quiz-available-count ${eligibleQuestions.length === 0 ? "zero" : ""} quiz-available-clickable`}
                  aria-live="polite"
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (eligibleQuestions.length > 0) {
                      setQuestionCount(Math.min(25, eligibleQuestions.length));
                    }
                  }}
                  onKeyDown={(e) => {
                    if (eligibleQuestions.length > 0 && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      setQuestionCount(Math.min(25, eligibleQuestions.length));
                    }
                  }}
                >
                  {eligibleQuestions.length} questions available
                </p>
              </div>
            </div>

            <button
              type="button"
              className="quiz-start-btn"
              onClick={() => void startQuiz()}
              disabled={startDisabled}
            >
              {QuizIcons.play}
              {preparing ? "Preparing…" : "Start Quiz"}
            </button>
              </>
            )}
          </article>
        </div>

        <div className="quiz-secondary">
          <article className="card">
            <h3>Runner</h3>
            {!session || !currentQuestion ? (
              <div className="quiz-empty-state">
                {QuizIcons.clipboard}
                <strong>No active quiz</strong>
                <p>Configure options above and click Start Quiz to begin.</p>
              </div>
            ) : (
              <>
                <div className="quiz-runner-progress-wrap">
                  <p className="quiz-runner-progress">
                    Question {session.currentIndex + 1} of {session.questions.length}
                  </p>
                  <div
                    className="quiz-progress-bar"
                    role="progressbar"
                    aria-valuenow={session.currentIndex + 1}
                    aria-valuemin={1}
                    aria-valuemax={session.questions.length}
                    aria-label="Quiz progress"
                  >
                    <div
                      className="quiz-progress-bar-fill"
                      style={{ width: `${((session.currentIndex + 1) / session.questions.length) * 100}%` }}
                    />
                  </div>
                  <div className="quiz-question-dots" role="navigation" aria-label="Jump to question">
                    {session.questions.map((q, idx) => {
                      const submitted = session.submitted[q.question_id];
                      const userAns = session.answers[q.question_id];
                      const isCorrect = userAns != null && normalized(userAns) === normalized(q.correct_answer);
                      const dotClass = submitted
                        ? isCorrect
                          ? "correct"
                          : "incorrect"
                        : session.answers[q.question_id]
                          ? "answered"
                          : "";
                      return (
                        <button
                          key={q.question_id}
                          type="button"
                          className={`quiz-question-dot ${idx === session.currentIndex ? "current" : ""} ${dotClass}`}
                          onClick={() => setSession((ex) => (ex ? { ...ex, currentIndex: idx } : ex))}
                          aria-label={`Question ${idx + 1}${submitted ? (isCorrect ? ", correct" : ", incorrect") : userAns ? ", answered" : ""}`}
                          aria-current={idx === session.currentIndex ? "true" : undefined}
                        />
                      );
                    })}
                  </div>
                </div>
                {!currentSubmitted ? (
                  <>
                    <p className="quiz-question-text">{currentQuestion.question}</p>
                    <div className="quiz-options" role="radiogroup" aria-label="Answer options">
                      {currentQuestion.options.map((option) => (
                        <label
                          key={option}
                          className={`quiz-option-label ${currentAnswer === option ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={`q-${currentQuestion.question_id}`}
                            checked={currentAnswer === option}
                            onChange={() => chooseAnswer(currentQuestion.question_id, option)}
                          />
                          <span className="quiz-option-text">{option}</span>
                        </label>
                      ))}
                    </div>
                    <div className="quiz-runner-actions">
                      <button
                        type="button"
                        className="top-bar-btn"
                        onClick={() =>
                          setSession((existing) =>
                            existing ? { ...existing, currentIndex: Math.max(0, existing.currentIndex - 1) } : existing
                          )
                        }
                        disabled={session.currentIndex === 0}
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        className="top-bar-btn primary"
                        onClick={markCurrentSubmitted}
                        disabled={!currentAnswer}
                      >
                        Submit Answer
                      </button>
                      <button
                        type="button"
                        className="top-bar-btn"
                        onClick={() =>
                          setSession((existing) =>
                            existing
                              ? {
                                  ...existing,
                                  currentIndex: Math.min(existing.questions.length - 1, existing.currentIndex + 1),
                                }
                              : existing
                          )
                        }
                        disabled={session.currentIndex >= session.questions.length - 1}
                      >
                        Next
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div
                      className={`quiz-feedback ${currentAnswer === currentQuestion.correct_answer ? "correct" : "incorrect"}`}
                      role="status"
                    >
                      <div className="quiz-feedback-header">
                        {currentAnswer === currentQuestion.correct_answer ? (
                          <span className="quiz-feedback-icon correct" aria-hidden>
                            {QuizIcons.check}
                          </span>
                        ) : (
                          <span className="quiz-feedback-icon incorrect" aria-hidden>
                            {QuizIcons.cross}
                          </span>
                        )}
                        <strong>
                          {currentAnswer === currentQuestion.correct_answer ? "Correct" : "Incorrect"}
                        </strong>
                      </div>
                      {currentAnswer !== currentQuestion.correct_answer && (
                        <>
                          <p className="quiz-feedback-your-answer">
                            <span className="quiz-feedback-label">Your answer:</span>{" "}
                            <span className="quiz-feedback-wrong">{currentAnswer || "(none)"}</span>
                          </p>
                          <p className="quiz-feedback-correct-answer">
                            <span className="quiz-feedback-label">Correct answer:</span>{" "}
                            <span className="quiz-feedback-correct-highlight">{currentQuestion.correct_answer}</span>
                          </p>
                        </>
                      )}
                      <p className="quiz-feedback-meta">
                        Topic: {currentQuestion.topic} · Concept: {currentQuestion.concept}
                      </p>
                      {currentQuestion.explanation && (
                        <p className="quiz-feedback-explanation">{currentQuestion.explanation}</p>
                      )}
                    </div>
                    <div className="quiz-runner-actions">
                      <button
                        type="button"
                        className="top-bar-btn"
                        onClick={() =>
                          setSession((existing) =>
                            existing ? { ...existing, currentIndex: Math.max(0, existing.currentIndex - 1) } : existing
                          )
                        }
                        disabled={session.currentIndex === 0}
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        className="top-bar-btn"
                        onClick={() =>
                          setSession((existing) =>
                            existing
                              ? {
                                  ...existing,
                                  currentIndex: Math.min(existing.questions.length - 1, existing.currentIndex + 1),
                                }
                              : existing
                          )
                        }
                        disabled={session.currentIndex >= session.questions.length - 1}
                      >
                        Next
                      </button>
                    </div>
                  </>
                )}
                <div style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="top-bar-btn primary"
                    onClick={() => void completeQuiz()}
                    disabled={!allSubmitted || submitting}
                  >
                    {submitting ? "Submitting…" : "Finish Quiz"}
                  </button>
                </div>
              </>
            )}
          </article>

          <article className="card">
            <h3>Latest Result</h3>
            {!result ? (
              <div className="quiz-empty-state">
                {QuizIcons.trophy}
                <strong>No result yet</strong>
                <p>Complete a quiz to see your score and topic updates.</p>
              </div>
            ) : (
              <div className="quiz-result-content">
                <div className="quiz-result-score">
                  <span className="quiz-result-score-value">
                    {result.quiz.correct_answers}/{result.quiz.total_questions}
                  </span>
                  <span className="quiz-result-score-pct">{scorePercent(result)}%</span>
                </div>
                {result.new_gap_ids.length > 0 && (
                  <p className="quiz-result-gaps">
                    {result.new_gap_ids.length} new knowledge gap{result.new_gap_ids.length !== 1 ? "s" : ""} identified
                  </p>
                )}
                <section className="quiz-result-topic-breakdown" aria-label="Topic breakdown">
                  <h4 className="quiz-result-subhead">By topic</h4>
                  {result.topic_updates.map((topicUpdate) => (
                    <div key={topicUpdate.topic} className="quiz-result-topic-row">
                      <span className="quiz-result-topic-name">{topicUpdate.topic}</span>
                      <span className="quiz-result-topic-mastery">
                        {Math.round(topicUpdate.before_mastery * 100)}% → {Math.round(topicUpdate.after_mastery * 100)}%
                        {topicUpdate.delta >= 0 ? (
                          <span className="quiz-result-delta positive">+{Math.round(topicUpdate.delta * 100)}%</span>
                        ) : (
                          <span className="quiz-result-delta negative">{Math.round(topicUpdate.delta * 100)}%</span>
                        )}
                      </span>
                    </div>
                  ))}
                </section>
                <section className="quiz-result-concept-breakdown" aria-label="Concept breakdown">
                  <h4 className="quiz-result-subhead">By concept</h4>
                  {(() => {
                    const byConcept = new Map<string, { correct: number; total: number }>();
                    for (const r of result.quiz.results) {
                      const cur = byConcept.get(r.concept) ?? { correct: 0, total: 0 };
                      cur.total++;
                      if (r.is_correct) cur.correct++;
                      byConcept.set(r.concept, cur);
                    }
                    return Array.from(byConcept.entries()).map(([concept, { correct, total }]) => (
                      <div key={concept} className="quiz-result-concept-row">
                        <span className="quiz-result-concept-name">{concept}</span>
                        <span className="quiz-result-concept-accuracy">
                          {correct}/{total} correct
                        </span>
                      </div>
                    ));
                  })()}
                </section>
                <p className="quiz-result-next-steps">
                  {result.new_gap_ids.length > 0
                    ? "Review the knowledge gaps in the Gaps tab and retry questions on weak concepts."
                    : result.topic_updates.some((t) => t.delta < 0)
                      ? "Focus on topics that decreased; try another quiz to reinforce."
                      : "Great job! Consider another quiz to reinforce or explore new topics."}
                </p>
              </div>
            )}
          </article>
        </div>
      </div>

      <footer className="quiz-footer">
        <article className="card">
          <h3>History</h3>
          {courseId === "all" && (
            <label className="quiz-config-label" htmlFor="history-filter-course">
              Show
            </label>
          )}
          {courseId === "all" && (
            <select
              id="history-filter-course"
              className="quiz-topic-select"
              value={historyFilterCourseId}
              onChange={(e) => setHistoryFilterCourseId(e.target.value)}
              aria-label="Filter history by course"
              style={{ marginBottom: "1rem", maxWidth: 240 }}
            >
              <option value="all">All courses</option>
              {historyCourseOptions.map((id) => (
                <option key={id} value={id}>
                  {courseNameById.get(id) ?? id}
                </option>
              ))}
            </select>
          )}
          {history.length === 0 ? (
            <div className="quiz-empty-state">
              {QuizIcons.clock}
              <strong>No quizzes submitted yet</strong>
              <p>Your attempts will appear here. Take a quiz to get started.</p>
            </div>
          ) : (
            <div className="quiz-history-grid">
              {history.slice(0, 12).map((item) => {
                const pct = Math.round(item.score * 100);
                const scoreClass = pct >= 80 ? "score-high" : pct >= 50 ? "score-mid" : "score-low";
                const courseLabel =
                  courseNameById.get(normalized(item.course_id)) ??
                  item.course_id;
                return (
                  <div key={item.quiz_id} className="quiz-history-card">
                    <div className="quiz-history-card-header">
                      <span className="quiz-history-badge">{item.topic}</span>
                      <span className={`quiz-history-score ${scoreClass}`}>
                        {item.correct_answers}/{item.total_questions} ({pct}%)
                      </span>
                    </div>
                    <p className="quiz-history-date">{formatHistoryDate(item.timestamp_utc)}</p>
                    <p className="quiz-history-meta">
                      Sources: {item.sources.map((s) => SOURCE_LABEL[s]).join(", ")}
                    </p>
                    {item.course_id && item.course_id !== "all" && (
                      <p className="quiz-history-course">Course: {courseLabel}</p>
                    )}
                    <div className="quiz-history-actions">
                      <button
                        type="button"
                        className="top-bar-btn"
                        onClick={() => handleRetake(item)}
                      >
                        Retake Quiz
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </article>
      </footer>
    </div>
  );
}
