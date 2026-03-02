import { useMemo, useState } from "react";
import { useLearningState } from "../context/LearningStateContext";
import type { QuestionSource, QuizQuestionResult, QuizSubmitResponse } from "../types";

const SOURCES: QuestionSource[] = ["pyq", "tutorial", "sentinel"];

function uniqTopics(items: string[]): string[] {
  return Array.from(new Set(items)).sort((a, b) => a.localeCompare(b));
}

export function QuizPage() {
  const { state, submitQuiz, loading, error, dataSource } = useLearningState();
  const topics = useMemo(() => uniqTopics(state.topics.map((t) => t.topic).concat(state.question_bank.map((q) => q.topic))), [state]);

  const [topic, setTopic] = useState<string>(topics[0] ?? "");
  const [sources, setSources] = useState<QuestionSource[]>(["pyq", "tutorial", "sentinel"]);
  const [questionCount, setQuestionCount] = useState<number>(3);
  const [started, setStarted] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [questionIds, setQuestionIds] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submittedSet, setSubmittedSet] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<QuizSubmitResponse | null>(null);

  const eligibleQuestions = useMemo(
    () => state.question_bank.filter((item) => item.topic.toLowerCase() === topic.toLowerCase() && sources.includes(item.source)),
    [state.question_bank, topic, sources]
  );

  const selectedQuestions = useMemo(() => {
    const idSet = new Set(questionIds);
    return state.question_bank.filter((item) => idSet.has(item.question_id));
  }, [state.question_bank, questionIds]);

  const activeQuestion = selectedQuestions[activeIndex] ?? null;
  const currentAnswer = activeQuestion ? answers[activeQuestion.question_id] ?? "" : "";
  const currentSubmitted = activeQuestion ? !!submittedSet[activeQuestion.question_id] : false;

  const latestHistory = useMemo(() => [...state.quizzes].sort((a, b) => b.timestamp_utc.localeCompare(a.timestamp_utc)), [state.quizzes]);

  const recommendations = useMemo(() => {
    const highPriority = state.gaps
      .filter((gap) => gap.status !== "closed")
      .sort((a, b) => b.priority_score - a.priority_score)
      .slice(0, 3)
      .map((gap) => `Review gap: ${gap.concept}`);
    const recentMisses = (result?.quiz.results ?? [])
      .filter((row) => !row.is_correct)
      .slice(0, 3)
      .map((row) => `Retry ${row.topic} - ${row.concept}`);
    return [...highPriority, ...recentMisses];
  }, [state.gaps, result]);

  function toggleSource(source: QuestionSource) {
    setSources((prev) => (prev.includes(source) ? prev.filter((item) => item !== source) : [...prev, source]));
  }

  function startQuiz() {
    setSubmitError(null);
    setResult(null);
    const picked = eligibleQuestions.slice(0, Math.max(1, Math.min(questionCount, eligibleQuestions.length)));
    setQuestionIds(picked.map((item) => item.question_id));
    setAnswers({});
    setSubmittedSet({});
    setActiveIndex(0);
    setStarted(true);
  }

  function markSubmitted(questionId: string) {
    setSubmittedSet((prev) => ({ ...prev, [questionId]: true }));
  }

  function getQuestionResult(questionId: string): QuizQuestionResult | null {
    return result?.quiz.results.find((row) => row.question_id === questionId) ?? null;
  }

  async function completeQuiz() {
    if (!topic) {
      setSubmitError("Select a topic before submitting.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        topic,
        sources,
        answers: selectedQuestions.map((item) => ({ question_id: item.question_id, user_answer: answers[item.question_id] ?? "" })),
      };
      const response = await submitQuiz(payload);
      setResult(response);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Quiz submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-shell page-fade quiz-page">
      <header className="quiz-page-header">
        <div>
          <h1>Quiz</h1>
          <p className="quiz-subtitle">Targeted checks on topics, with immediate learning impact.</p>
        </div>
        <span className="quiz-mode-pill">Mode: {dataSource === "bridge" ? "Bridge API" : "Mock"}</span>
      </header>

      {error && <p className="status-line error">{error}</p>}
      {loading && <p className="status-line">Loading state...</p>}

      <section className="quiz-top-grid">
        <article className="card quiz-config">
          <h2>Setup</h2>
          <label className="quiz-field">
            Topic
            <select value={topic} onChange={(e) => setTopic(e.target.value)}>
              {topics.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <div className="quiz-field">
            Sources
            <div className="quiz-source-grid">
              {SOURCES.map((source) => (
                <button
                  key={source}
                  type="button"
                  className={`quiz-source-chip ${sources.includes(source) ? "active" : ""}`}
                  onClick={() => toggleSource(source)}
                >
                  {source.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <label className="quiz-field">
            Question Count
            <input
              type="number"
              min={1}
              max={Math.max(1, eligibleQuestions.length)}
              value={questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
            />
          </label>

          <button type="button" className="top-bar-btn primary" disabled={!topic || eligibleQuestions.length === 0 || sources.length === 0} onClick={startQuiz}>
            Start Quiz
          </button>
        </article>

        <article className="card quiz-stats-card">
          <h2>Snapshot</h2>
          <div className="quiz-stat-grid">
            <div>
              <span>Available</span>
              <strong>{eligibleQuestions.length}</strong>
            </div>
            <div>
              <span>Completed Quizzes</span>
              <strong>{latestHistory.length}</strong>
            </div>
            <div>
              <span>Open Gaps</span>
              <strong>{state.gaps.filter((gap) => gap.status !== "closed").length}</strong>
            </div>
            <div>
              <span>Concept Mastery</span>
              <strong>{Math.round(state.readiness_axes.concept_mastery * 100)}%</strong>
            </div>
          </div>
        </article>
      </section>

      {started && activeQuestion && (
        <section className="card quiz-runner">
          <div className="quiz-runner-head">
            <h2>
              Question {activeIndex + 1} / {selectedQuestions.length}
            </h2>
            <div className="quiz-runner-meta">
              <span>{activeQuestion.source.toUpperCase()}</span>
              <span>{activeQuestion.concept}</span>
            </div>
          </div>

          <p className="quiz-question-text">{activeQuestion.question}</p>
          <div className="quiz-options">
            {activeQuestion.options.map((option) => {
              const checked = currentAnswer === option;
              return (
                <label key={option} className={`quiz-option-row ${checked ? "selected" : ""}`}>
                  <input
                    type="radio"
                    name={`question-${activeQuestion.question_id}`}
                    checked={checked}
                    onChange={() => setAnswers((prev) => ({ ...prev, [activeQuestion.question_id]: option }))}
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>

          <div className="quiz-runner-actions">
            <button type="button" onClick={() => setActiveIndex((index) => Math.max(0, index - 1))} disabled={activeIndex === 0}>
              Previous
            </button>
            <button type="button" onClick={() => markSubmitted(activeQuestion.question_id)} disabled={!currentAnswer}>
              Submit Answer
            </button>
            <button type="button" onClick={() => setActiveIndex((index) => Math.min(selectedQuestions.length - 1, index + 1))} disabled={activeIndex >= selectedQuestions.length - 1}>
              Next
            </button>
          </div>

          {currentSubmitted && (
            <p className="status-line">
              {result ? (getQuestionResult(activeQuestion.question_id)?.is_correct ? "Correct" : "Incorrect") : "Answer saved. Final correctness shown after final submit."}
            </p>
          )}

          <button type="button" className="top-bar-btn primary" onClick={() => void completeQuiz()} disabled={submitting}>
            {submitting ? "Submitting..." : "Finish Quiz"}
          </button>
          {submitError && <p className="status-line error">{submitError}</p>}
        </section>
      )}

      {result && (
        <section className="card quiz-summary">
          <h2>Result</h2>
          <div className="quiz-result-row">
            <span className="quiz-score-pill">
              {result.quiz.correct_answers}/{result.quiz.total_questions} ({Math.round(result.quiz.score * 100)}%)
            </span>
            <span className="quiz-gap-pill">New gaps: {result.new_gap_ids.length}</span>
          </div>
          <ul className="quiz-mastery-list">
            {result.topic_updates.map((item) => (
              <li key={item.topic}>
                <strong>{item.topic}</strong>
                <span>
                  {Math.round(item.before_mastery * 100)}% -&gt; {Math.round(item.after_mastery * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="quiz-bottom-grid">
        <article className="card quiz-history">
          <h2>Quiz History</h2>
          {latestHistory.length === 0 ? (
            <p className="status-line">No quizzes yet.</p>
          ) : (
            <div className="quiz-history-table">
              {latestHistory.slice(0, 8).map((item) => (
                <div key={item.quiz_id} className="quiz-history-row">
                  <span>{new Date(item.timestamp_utc).toLocaleString()}</span>
                  <span>{item.topic}</span>
                  <strong>
                    {item.correct_answers}/{item.total_questions}
                  </strong>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="card quiz-recommendations">
          <h2>Recommendations</h2>
          {recommendations.length === 0 ? (
            <p className="status-line">No recommendations yet.</p>
          ) : (
            <ul className="quiz-recommendation-list">
              {recommendations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </div>
  );
}
