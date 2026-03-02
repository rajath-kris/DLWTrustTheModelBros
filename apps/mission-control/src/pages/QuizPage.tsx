import { useEffect, useMemo, useState } from "react";

import { useBrainState } from "../context/BrainStateContext";
import { useCourse } from "../context/CourseContext";
import type { QuestionBankItem, QuizSelectionSummary, QuizSourceType, QuizSubmitResponse } from "../types";

const ALL_TOPICS = "All Topics";
const ALL_SOURCES: QuizSourceType[] = ["pyq", "tutorial", "sentinel"];

const SOURCE_LABEL: Record<QuizSourceType, string> = {
  pyq: "PYQ",
  tutorial: "Tutorial",
  sentinel: "Sentinel",
};

type QuizSession = {
  sessionId: string;
  topic: string;
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

export function QuizPage() {
  const { courseId } = useCourse();
  const { state, loading, error: stateError, prepareQuiz, submitQuiz } = useBrainState();
  const [selectedTopic, setSelectedTopic] = useState<string>(ALL_TOPICS);
  const [selectedSources, setSelectedSources] = useState<QuizSourceType[]>([...ALL_SOURCES]);
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [session, setSession] = useState<QuizSession | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [result, setResult] = useState<QuizSubmitResponse | null>(null);
  const [selectionSummary, setSelectionSummary] = useState<QuizSelectionSummary | null>(null);

  const scopedQuestions = useMemo(() => {
    return state.question_bank.filter((item) => {
      if (courseId === "all") {
        return true;
      }
      return normalized(item.course_id) === "all" || normalized(item.course_id) === normalized(courseId);
    });
  }, [state.question_bank, courseId]);

  const topicOptions = useMemo(() => {
    const topicSet = new Set<string>([ALL_TOPICS]);
    for (const item of scopedQuestions) {
      topicSet.add(item.topic);
    }
    for (const row of state.topic_mastery) {
      if (courseId !== "all" && normalized(row.course_id) !== normalized(courseId)) {
        continue;
      }
      topicSet.add(row.name);
    }
    return Array.from(topicSet.values());
  }, [courseId, scopedQuestions, state.topic_mastery]);

  useEffect(() => {
    if (!topicOptions.includes(selectedTopic)) {
      setSelectedTopic(topicOptions[0] ?? ALL_TOPICS);
    }
  }, [selectedTopic, topicOptions]);

  const eligibleQuestions = useMemo(() => {
    const topicFiltered = scopedQuestions.filter((item) => {
      if (normalized(selectedTopic) === normalized(ALL_TOPICS)) {
        return true;
      }
      return normalized(item.topic) === normalized(selectedTopic);
    });
    return topicFiltered.filter((item) => selectedSources.includes(item.source));
  }, [scopedQuestions, selectedTopic, selectedSources]);

  const history = useMemo(() => {
    const filtered = state.quizzes.filter((quiz) => {
      if (courseId === "all") {
        return true;
      }
      return normalized(quiz.course_id) === normalized(courseId);
    });
    return [...filtered].sort((a, b) => b.timestamp_utc.localeCompare(a.timestamp_utc));
  }, [state.quizzes, courseId]);

  const currentQuestion = session?.questions[session.currentIndex] ?? null;
  const currentAnswer = currentQuestion ? session?.answers[currentQuestion.question_id] ?? "" : "";
  const allAnswered = session ? session.questions.every((item) => Boolean(session.answers[item.question_id])) : false;

  function toggleSource(source: QuizSourceType) {
    setSelectedSources((existing) => {
      if (existing.includes(source)) {
        return existing.filter((item) => item !== source);
      }
      return [...existing, source];
    });
  }

  async function startQuiz() {
    if (eligibleQuestions.length === 0) {
      setRequestError("No questions available for the selected topic/source filters.");
      return;
    }
    setPreparing(true);
    try {
      const desiredCount = Math.max(1, Math.min(25, questionCount));
      const prepared = await prepareQuiz({
        topic: selectedTopic,
        sources: selectedSources,
        question_count: desiredCount,
        course_id: courseId === "all" ? "all" : courseId,
      });
      if (!prepared.questions.length) {
        setRequestError("Quiz preparation returned no questions for this filter set.");
        return;
      }
      setResult(null);
      setRequestError(null);
      setSelectionSummary(prepared.selection_summary);
      setSession({
        sessionId: prepared.session_id,
        topic: prepared.topic,
        questions: prepared.questions,
        currentIndex: 0,
        answers: {},
        submitted: {},
      });
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Quiz preparation failed.");
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
        course_id: courseId === "all" ? "all" : courseId,
        session_id: session.sessionId,
      });
      setResult(response);
      setSession(null);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Quiz submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-shell page-fade">
      <h1>Quiz</h1>
      {loading && <p className="status-line">Loading quiz state...</p>}
      {stateError && <p className="status-line">{stateError}</p>}
      {requestError && <p className="status-line error">{requestError}</p>}

      <section className="content-grid">
        <article className="card">
          <h3>Setup</h3>
          <label className="doc-upload-label">
            Topic
            <select value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
              {topicOptions.map((topic) => (
                <option key={topic} value={topic}>
                  {topic}
                </option>
              ))}
            </select>
          </label>

          <div className="doc-upload-label">
            Sources
            <div className="doc-upload-helper">
              {ALL_SOURCES.map((source) => (
                <label key={source} style={{ marginRight: 12 }}>
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(source)}
                    onChange={() => toggleSource(source)}
                  />{" "}
                  {SOURCE_LABEL[source]}
                </label>
              ))}
            </div>
          </div>

          <label className="doc-upload-label">
            Number of Questions
            <input
              type="number"
              min={1}
              max={25}
              value={questionCount}
              onChange={(event) => setQuestionCount(Number(event.target.value || 5))}
            />
          </label>

          <p className="doc-upload-helper">Eligible questions: {eligibleQuestions.length}</p>
          <button
            type="button"
            className="top-bar-btn primary"
            onClick={() => void startQuiz()}
            disabled={preparing || selectedSources.length === 0 || eligibleQuestions.length === 0}
          >
            {preparing ? "Preparing..." : "Start Quiz"}
          </button>
          {selectionSummary && (
            <p className="doc-upload-helper" style={{ marginTop: 8 }}>
              Mix: gap {selectionSummary.gap_matched_count}, wrong-repeat {selectionSummary.wrong_repeat_count}, deadline {selectionSummary.deadline_boosted_count}, coverage {selectionSummary.coverage_count}
            </p>
          )}
        </article>

        <article className="card">
          <h3>Runner</h3>
          {!session || !currentQuestion ? (
            <p className="status-line">Start a quiz to begin answering.</p>
          ) : (
            <>
              <p>
                Question {session.currentIndex + 1} of {session.questions.length}
              </p>
              <p>{currentQuestion.question}</p>
              <div>
                {currentQuestion.options.map((option) => (
                  <label key={option} style={{ display: "block", marginBottom: 6 }}>
                    <input
                      type="radio"
                      name={`q-${currentQuestion.question_id}`}
                      checked={currentAnswer === option}
                      onChange={() => chooseAnswer(currentQuestion.question_id, option)}
                    />{" "}
                    {option}
                  </label>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button
                  type="button"
                  className="top-bar-btn"
                  onClick={() =>
                    setSession((existing) =>
                      existing
                        ? { ...existing, currentIndex: Math.max(0, existing.currentIndex - 1) }
                        : existing
                    )
                  }
                  disabled={session.currentIndex === 0}
                >
                  Previous
                </button>
                <button type="button" className="top-bar-btn" onClick={markCurrentSubmitted} disabled={!currentAnswer}>
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
              <div style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="top-bar-btn primary"
                  onClick={() => void completeQuiz()}
                  disabled={!allAnswered || submitting}
                >
                  {submitting ? "Submitting..." : "Finish Quiz"}
                </button>
              </div>
            </>
          )}
        </article>
      </section>

      <section className="content-grid" style={{ marginTop: 16 }}>
        <article className="card">
          <h3>Latest Result</h3>
          {!result ? (
            <p className="status-line">No result yet.</p>
          ) : (
            <>
              <p>
                Score: {result.quiz.correct_answers}/{result.quiz.total_questions} ({scorePercent(result)}%)
              </p>
              <p>New gaps created: {result.new_gap_ids.length}</p>
              {result.topic_updates.map((topicUpdate) => (
                <p key={topicUpdate.topic}>
                  {topicUpdate.topic}: {Math.round(topicUpdate.before_mastery * 100)}% to{" "}
                  {Math.round(topicUpdate.after_mastery * 100)}%
                </p>
              ))}
            </>
          )}
        </article>

        <article className="card">
          <h3>History</h3>
          {history.length === 0 ? (
            <p className="status-line">No quizzes submitted yet.</p>
          ) : (
            <ul className="session-list">
              {history.slice(0, 8).map((item) => (
                <li key={item.quiz_id} className="session-item">
                  <div className="session-row">
                    <span className="session-topic">{item.topic}</span>
                    <span>{Math.round(item.score * 100)}%</span>
                  </div>
                  <div className="session-row">
                    <span>{new Date(item.timestamp_utc).toLocaleString()}</span>
                    <span>
                      {item.correct_answers}/{item.total_questions}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </div>
  );
}
