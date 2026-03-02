import { useEffect, useMemo, useState } from "react";
import { useLearningState } from "../context/StateContext";
import type {
  QuestionBankItem,
  QuizRecord,
  QuizSourceType,
  QuizSubmissionResponse,
} from "../types";

type QuizSession = {
  topic: string;
  sources: QuizSourceType[];
  questions: QuestionBankItem[];
  answers: Record<string, string>;
  submitted: Record<string, boolean>;
};

type QuizRecommendation = {
  id: string;
  topic: string;
  title: string;
  reason: string;
  sources: QuizSourceType[];
  questions: number;
};

const SOURCE_LABELS: Record<QuizSourceType, string> = {
  pyq: "PYQs",
  tutorial: "Tutorials",
  sentinel: "Sentinel-Captured Questions",
};

function sourcePrettyName(source: QuizSourceType): string {
  return SOURCE_LABELS[source];
}

function quizPercent(quiz: QuizRecord): number {
  return Math.round((quiz.score.correct / quiz.score.total) * 100);
}

function mean(numbers: number[]): number {
  if (numbers.length === 0) return 0;
  return numbers.reduce((sum, item) => sum + item, 0) / numbers.length;
}

export function QuizTab() {
  const { state, loading, error: stateError, reload, submitQuiz, source } = useLearningState();
  const [error, setError] = useState<string | null>(null);

  const [selectedTopic, setSelectedTopic] = useState("All Topics");
  const [selectedSources, setSelectedSources] = useState<QuizSourceType[]>(["pyq", "tutorial", "sentinel"]);
  const [questionCount, setQuestionCount] = useState(5);

  const [session, setSession] = useState<QuizSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentFeedback, setCurrentFeedback] = useState<boolean | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizSubmissionResponse | null>(null);
  const [impactSummary, setImpactSummary] = useState<{
    topicName: string;
    before: number;
    after: number;
    newGapConcepts: string[];
  } | null>(null);

  useEffect(() => {
    setError(stateError);
  }, [stateError]);

  const topicOptions = useMemo(() => {
    const fromTopics = state?.topics.map((topic) => topic.name) ?? [];
    const fromBank = Array.from(new Set((state?.question_bank ?? []).map((q) => q.topic)));
    return ["All Topics", ...Array.from(new Set([...fromTopics, ...fromBank]))];
  }, [state]);

  const filteredPool = useMemo(() => {
    if (!state) return [];
    return state.question_bank.filter((question) => {
      const topicMatch = selectedTopic === "All Topics" || question.topic === selectedTopic;
      const sourceMatch = selectedSources.includes(question.source_type);
      return topicMatch && sourceMatch;
    });
  }, [selectedSources, selectedTopic, state]);

  const history = useMemo(
    () => [...(state?.quizzes ?? [])].sort((a, b) => new Date(b.date_taken).getTime() - new Date(a.date_taken).getTime()),
    [state]
  );

  const average7d = useMemo(() => {
    const weekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
    const recent = history.filter((quiz) => new Date(quiz.date_taken).getTime() >= weekAgo);
    if (recent.length === 0) return 0;
    return Math.round(mean(recent.map(quizPercent)));
  }, [history]);

  const recommendations = useMemo<QuizRecommendation[]>(() => {
    if (!state) return [];

    const recommended: QuizRecommendation[] = [];
    const openGaps = state.gaps
      .filter((gap) => gap.status !== "closed")
      .sort((a, b) => b.priority_score - a.priority_score)
      .slice(0, 3);

    openGaps.forEach((gap) => {
      const matchedTopic =
        state.topics.find((topic) => gap.concept.toLowerCase().includes(topic.name.toLowerCase().split(" ")[0].toLowerCase()))?.name ??
        state.question_bank.find((question) => gap.concept.toLowerCase().includes(question.topic.toLowerCase().split(" ")[0].toLowerCase()))?.topic ??
        "All Topics";

      recommended.push({
        id: `gap-${gap.gap_id}`,
        topic: matchedTopic,
        title: `${matchedTopic}: Reinforcement`,
        reason: `High-priority gap: ${gap.concept}`,
        sources: ["tutorial", "pyq"],
        questions: 8,
      });
    });

    const lastQuiz = history[0];
    if (lastQuiz) {
      const missedConcepts = Array.from(
        new Set(lastQuiz.questions.filter((question) => !question.is_correct).map((question) => question.concept))
      );
      if (missedConcepts.length > 0) {
        recommended.push({
          id: `missed-${lastQuiz.id}`,
          topic: lastQuiz.topic,
          title: `${lastQuiz.topic}: Missed Concepts Drill`,
          reason: `You missed ${missedConcepts.length} concept(s) in your latest quiz`,
          sources: lastQuiz.sources.length > 0 ? lastQuiz.sources : ["tutorial"],
          questions: 6,
        });
      }
    }

    return recommended.slice(0, 4);
  }, [history, state]);

  const currentQuestion = session?.questions[currentIndex] ?? null;
  const currentAnswer = currentQuestion ? session?.answers[currentQuestion.id] ?? "" : "";
  const allAnswered = session ? session.questions.every((question) => Boolean(session.answers[question.id])) : false;
  const submittedCount = session ? Object.values(session.submitted).filter(Boolean).length : 0;

  function toggleSource(source: QuizSourceType) {
    setSelectedSources((existing) => {
      if (existing.includes(source)) return existing.filter((item) => item !== source);
      return [...existing, source];
    });
  }

  function startQuiz() {
    if (!state) return;
    const pool = filteredPool;
    const count = Math.min(Math.max(questionCount, 3), 25);
    const shuffled = [...pool].sort(() => Math.random() - 0.5);
    const picked = shuffled.slice(0, count);

    if (picked.length === 0) {
      setError("No questions available for the current topic/source filters.");
      return;
    }

    setError(null);
    setResult(null);
    setImpactSummary(null);
    setCurrentFeedback(null);
    setCurrentIndex(0);
    setSession({
      topic: selectedTopic,
      sources: selectedSources,
      questions: picked,
      answers: {},
      submitted: {},
    });
  }

  function onSelectAnswer(questionId: string, answer: string) {
    setSession((existing) => {
      if (!existing) return existing;
      return { ...existing, answers: { ...existing.answers, [questionId]: answer } };
    });
  }

  function submitCurrentAnswer() {
    if (!session || !currentQuestion) return;
    const answer = session.answers[currentQuestion.id];
    if (!answer) return;
    const isCorrect = answer.trim().toLowerCase() === currentQuestion.correct_answer.trim().toLowerCase();
    setCurrentFeedback(isCorrect);
    setSession((existing) => {
      if (!existing) return existing;
      return {
        ...existing,
        submitted: { ...existing.submitted, [currentQuestion.id]: true },
      };
    });
  }

  async function completeQuiz() {
    if (!session || !state || !allAnswered) return;

    const targetTopicName = session.topic === "All Topics"
      ? session.questions[0]?.topic ?? "All Topics"
      : session.topic;
    const beforeMastery = state.topics.find((topic) => topic.name === targetTopicName)?.mastery_score ?? 0;

    try {
      setSubmitting(true);
      setError(null);
      const response = await submitQuiz({
        topic: targetTopicName,
        sources: session.sources,
        answers: session.questions.map((question) => ({
          question_id: question.id,
          user_answer: session.answers[question.id] ?? "",
        })),
      });
      setResult(response);
      await reload();

      const updatedTopic = response.topic_updates[0];
      const newGapConcepts = response.quiz.questions
        .filter((question) => !question.is_correct)
        .map((question) => question.concept)
        .filter((concept, index, arr) => arr.indexOf(concept) === index);
      setImpactSummary({
        topicName: updatedTopic?.name ?? targetTopicName,
        before: beforeMastery,
        after: updatedTopic?.mastery_score ?? beforeMastery,
        newGapConcepts,
      });
      setSession(null);
      setCurrentIndex(0);
      setCurrentFeedback(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Quiz submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  function useRecommendation(recommendation: QuizRecommendation) {
    setSelectedTopic(recommendation.topic);
    setSelectedSources(recommendation.sources);
    setQuestionCount(recommendation.questions);
  }

  if (loading) {
    return (
      <div className="page-shell page-fade">
        <h1>Quiz</h1>
        <p className="status-line">Loading quiz workspace…</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-fade">
      <header className="quiz-header">
        <div>
          <h1>Quiz</h1>
          <p className="quiz-header-subtitle">Practice by topic, validate understanding, and update mastery metrics.</p>
        </div>
        <div className="quiz-header-chips">
          <span className="pill quiz-pill">Source: {source}</span>
          <span className="pill quiz-pill">{history[0] ? `Last quiz: ${new Date(history[0].date_taken).toLocaleString()}` : "Last quiz: -"} </span>
          <span className="pill quiz-pill">Avg score (7d): {average7d}%</span>
        </div>
      </header>

      {error && <p className="status-line quiz-error">{error}</p>}

      <div className="quiz-layout">
        <section className="quiz-workspace">
          <article className="card quiz-card">
            <h2>Create Quiz</h2>
            <p className="quiz-muted">Configure scope and start a focused practice run.</p>
            <div className="quiz-form-grid">
              <label className="quiz-field">
                <span>Topic / Module</span>
                <select
                  value={selectedTopic}
                  onChange={(event) => setSelectedTopic(event.target.value)}
                  className="quiz-select"
                >
                  {topicOptions.map((topic) => (
                    <option key={topic} value={topic}>
                      {topic}
                    </option>
                  ))}
                </select>
              </label>

              <div className="quiz-field">
                <span>Question Sources</span>
                <div className="quiz-source-list">
                  {(["pyq", "tutorial", "sentinel"] as QuizSourceType[]).map((source) => (
                    <label key={source} className="quiz-source-option">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(source)}
                        onChange={() => toggleSource(source)}
                      />
                      <span>{sourcePrettyName(source)}</span>
                    </label>
                  ))}
                </div>
              </div>

              <label className="quiz-field">
                <span>Number of Questions</span>
                <input
                  type="number"
                  className="quiz-number"
                  min={3}
                  max={25}
                  value={questionCount}
                  onChange={(event) => setQuestionCount(Number(event.target.value || 5))}
                />
              </label>
            </div>

            <div className="quiz-config-footer">
              <p className="quiz-muted">
                Question pool: {filteredPool.length} available • Estimated time: ~{Math.max(1, Math.round(questionCount * 1.2))} min
              </p>
              <button
                type="button"
                className="top-bar-btn primary"
                onClick={startQuiz}
                disabled={selectedSources.length === 0 || filteredPool.length === 0}
              >
                Start Quiz
              </button>
            </div>
          </article>

          {session && currentQuestion && (
            <article className="card quiz-card">
              <div className="quiz-progress-head">
                <p>Question {currentIndex + 1} of {session.questions.length}</p>
                <p>Submitted: {submittedCount}/{session.questions.length}</p>
              </div>
              <div className="quiz-progress-track">
                <span
                  className="quiz-progress-value"
                  style={{ width: `${((currentIndex + 1) / session.questions.length) * 100}%` }}
                />
              </div>
              <div className="quiz-question-meta">
                <span className="pill quiz-pill">{currentQuestion.topic}</span>
                <span className="pill quiz-pill">{sourcePrettyName(currentQuestion.source_type)}</span>
              </div>
              <p className="quiz-question-text">{currentQuestion.question_text}</p>
              <div className="quiz-options">
                {currentQuestion.options.map((option) => (
                  <label key={option} className="quiz-option">
                    <input
                      type="radio"
                      name={`question-${currentQuestion.id}`}
                      value={option}
                      checked={currentAnswer === option}
                      onChange={(event) => onSelectAnswer(currentQuestion.id, event.target.value)}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>

              <div className="quiz-actions">
                <button
                  type="button"
                  className="top-bar-btn"
                  onClick={() => {
                    setCurrentIndex((idx) => Math.max(0, idx - 1));
                    setCurrentFeedback(null);
                  }}
                  disabled={currentIndex === 0}
                >
                  Previous Question
                </button>
                <button
                  type="button"
                  className="top-bar-btn primary"
                  onClick={submitCurrentAnswer}
                  disabled={!currentAnswer || Boolean(session.submitted[currentQuestion.id])}
                >
                  Submit Answer
                </button>
                <button
                  type="button"
                  className="top-bar-btn"
                  onClick={() => {
                    setCurrentIndex((idx) => Math.min(session.questions.length - 1, idx + 1));
                    setCurrentFeedback(null);
                  }}
                  disabled={currentIndex === session.questions.length - 1}
                >
                  Next Question
                </button>
              </div>

              {session.submitted[currentQuestion.id] && (
                <div className={`quiz-feedback ${currentFeedback ? "correct" : "incorrect"}`} aria-live="polite">
                  <p>{currentFeedback ? "Correct" : "Incorrect"}</p>
                  <p>Correct answer: {currentQuestion.correct_answer}</p>
                </div>
              )}

              <div className="quiz-submit-wrap">
                <button
                  type="button"
                  className="top-bar-btn primary"
                  onClick={completeQuiz}
                  disabled={!allAnswered || submitting}
                >
                  {submitting ? "Submitting..." : "Complete Quiz"}
                </button>
              </div>
            </article>
          )}

          {result && impactSummary && (
            <article className="card quiz-card">
              <h2>Quiz Results</h2>
              <p className="quiz-score-hero">
                {result.quiz.score.correct}/{result.quiz.score.total} correct ({quizPercent(result.quiz)}%)
              </p>
              <div className="quiz-impact-list">
                <p>
                  Mastery for <strong>{impactSummary.topicName}</strong> changed from{" "}
                  <strong>{Math.round(impactSummary.before * 100)}%</strong> to{" "}
                  <strong>{Math.round(impactSummary.after * 100)}%</strong>.
                </p>
                {impactSummary.newGapConcepts.length > 0 ? (
                  <p>New or reinforced gaps: {impactSummary.newGapConcepts.join(", ")}</p>
                ) : (
                  <p>No new knowledge gaps were added from this attempt.</p>
                )}
              </div>
            </article>
          )}
        </section>

        <aside className="quiz-insights">
          <article className="card quiz-card">
            <h2>Recommended Quizzes</h2>
            {recommendations.length === 0 ? (
              <p className="quiz-muted">No recommendations yet. Complete a quiz to unlock personalized suggestions.</p>
            ) : (
              <ul className="quiz-recommendation-list">
                {recommendations.map((item) => (
                  <li key={item.id} className="quiz-recommendation-item">
                    <h3>{item.title}</h3>
                    <p>{item.reason}</p>
                    <p className="quiz-muted">
                      {item.questions} questions • {item.sources.map(sourcePrettyName).join(" + ")}
                    </p>
                    <button type="button" className="top-bar-btn" onClick={() => useRecommendation(item)}>
                      Use Setup
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="card quiz-card">
            <h2>Past Quizzes</h2>
            {history.length === 0 ? (
              <p className="quiz-muted">No quiz attempts yet.</p>
            ) : (
              <ul className="quiz-history-list">
                {history.slice(0, 8).map((quiz) => (
                  <li key={quiz.id} className="quiz-history-item">
                    <div>
                      <p className="quiz-history-topic">{quiz.topic}</p>
                      <p className="quiz-muted">{new Date(quiz.date_taken).toLocaleString()}</p>
                    </div>
                    <div className="quiz-history-score">
                      <strong>{quiz.score.correct}/{quiz.score.total}</strong>
                      <span>{quizPercent(quiz)}%</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </aside>
      </div>
    </div>
  );
}
