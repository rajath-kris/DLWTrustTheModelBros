<<<<<<< Updated upstream
﻿import { useEffect, useMemo, useState } from "react";
=======
import { Outlet, Route, Routes } from "react-router-dom";
import { CourseProvider } from "./context/CourseContext";
import { BrainStateProvider } from "./context/BrainStateContext";
import { StateProvider } from "./context/LearningStateContext";
import { AppSidebar } from "./components/AppSidebar";
import {
  MissionControlPage,
  KnowledgeGapsPage,
  QuizPage,
  SchedulePage,
  StudyPlannerPage,
  DocumentHubPage,
  SessionHistoryPage,
  AskSentinelPage,
  PreferencesPage,
} from "./pages";
>>>>>>> Stashed changes

import { API_BASE, emptyState, fetchState, openEventStream, updateGapStatus } from "./api";
import { RadarChart } from "./components/RadarChart";
import type { GapStatus, KnowledgeGap, LearningState, ServerEventEnvelope } from "./types";

type FilterId = "all" | GapStatus;

const FILTERS: Array<{ id: FilterId; label: string }> = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "reviewing", label: "Reviewing" },
  { id: "closed", label: "Closed" },
];

const STATUS_ORDER: GapStatus[] = ["open", "reviewing", "closed"];

function nextStatus(current: GapStatus): GapStatus {
  const idx = STATUS_ORDER.indexOf(current);
  return STATUS_ORDER[(idx + 1) % STATUS_ORDER.length];
}

function formatPercent(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString();
}

function metric(gaps: KnowledgeGap[], selector: (gap: KnowledgeGap) => number): number {
  if (gaps.length === 0) {
    return 0;
  }
  return selector(gaps.reduce((best, item) => (selector(item) > selector(best) ? item : best)));
}

export default function App() {
  const [state, setState] = useState<LearningState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterId>("all");

  useEffect(() => {
    let stream: EventSource | null = null;
    let mounted = true;

    async function hydrate() {
      try {
        const fresh = await fetchState();
        if (mounted) {
          setState(fresh);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Could not load state.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    hydrate();

    stream = openEventStream((message) => {
      try {
        const envelope = JSON.parse(message.data) as ServerEventEnvelope;
        if (envelope.payload?.state) {
          setState(envelope.payload.state);
        }
      } catch {
        // Ignore malformed stream events.
      }
    });

    stream.onerror = () => {
      setError("Live stream disconnected. Reconnect by refreshing after API restart.");
    };

    return () => {
      mounted = false;
      stream?.close();
    };
  }, []);

  const filteredGaps = useMemo(() => {
    const rows = filter === "all" ? state.gaps : state.gaps.filter((gap) => gap.status === filter);
    return [...rows].sort((a, b) => b.priority_score - a.priority_score);
  }, [state.gaps, filter]);

  const latestCapture = state.captures[state.captures.length - 1];

  const totalOpen = state.gaps.filter((gap) => gap.status === "open").length;
  const criticalPriority = metric(state.gaps, (gap) => gap.priority_score);
  const topDeadline = metric(state.gaps, (gap) => gap.deadline_score);

  async function handleCycleStatus(gap: KnowledgeGap) {
    const target = nextStatus(gap.status);
    try {
      await updateGapStatus(gap.gap_id, target);
      setState((prev) => ({
        ...prev,
        gaps: prev.gaps.map((item) => (item.gap_id === gap.gap_id ? { ...item, status: target } : item)),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update gap status.");
    }
  }

  return (
<<<<<<< Updated upstream
    <main className="page-shell">
      <section className="hero-panel">
        <div>
          <p className="hero-kicker">Sentinel AI</p>
          <h1>Mission Control</h1>
          <p className="hero-copy">
            Real-time readiness from ambient study captures. API: <code>{API_BASE}</code>
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Last update</span>
            <strong>{formatTimestamp(state.updated_at)}</strong>
          </div>
          <div>
            <span>Latest prompt</span>
            <strong>{latestCapture?.socratic_prompt || "No captures yet"}</strong>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <article>
          <p>Open Gaps</p>
          <h2>{totalOpen}</h2>
        </article>
        <article>
          <p>Highest Priority</p>
          <h2>{formatPercent(criticalPriority)}</h2>
        </article>
        <article>
          <p>Top Deadline Pressure</p>
          <h2>{formatPercent(topDeadline)}</h2>
        </article>
      </section>

      <section className="content-grid">
        <article className="card radar-card">
          <header>
            <h3>Readiness Radar</h3>
            <p>Mastery vs deadline and retention pressure.</p>
          </header>
          <RadarChart axes={state.readiness_axes} />
          <dl className="axis-legend">
            <div>
              <dt>Mastery</dt>
              <dd>{formatPercent(state.readiness_axes.concept_mastery)}</dd>
            </div>
            <div>
              <dt>Deadline</dt>
              <dd>{formatPercent(state.readiness_axes.deadline_pressure)}</dd>
            </div>
            <div>
              <dt>Retention</dt>
              <dd>{formatPercent(state.readiness_axes.retention_risk)}</dd>
            </div>
            <div>
              <dt>Transfer</dt>
              <dd>{formatPercent(state.readiness_axes.problem_transfer)}</dd>
            </div>
            <div>
              <dt>Consistency</dt>
              <dd>{formatPercent(state.readiness_axes.consistency)}</dd>
            </div>
          </dl>
        </article>

        <article className="card gaps-card">
          <header className="gaps-head">
            <div>
              <h3>Knowledge Gap Tracker</h3>
              <p>Sorted by severity and deadline proximity.</p>
            </div>
            <div className="filter-group">
              {FILTERS.map((item) => (
                <button
                  key={item.id}
                  className={item.id === filter ? "filter active" : "filter"}
                  onClick={() => setFilter(item.id)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </header>

          {loading ? <p className="status-line">Loading state...</p> : null}
          {error ? <p className="status-line error">{error}</p> : null}

          <div className="gap-list">
            {filteredGaps.length === 0 ? (
              <p className="status-line">No gaps in this filter.</p>
            ) : (
              filteredGaps.map((gap) => (
                <article key={gap.gap_id} className={`gap-row status-${gap.status}`}>
                  <div className="gap-main">
                    <h4>{gap.concept}</h4>
                    <p>
                      Severity {formatPercent(gap.severity)} | Confidence {formatPercent(gap.confidence)} | Priority{" "}
                      {formatPercent(gap.priority_score)}
                    </p>
                    <p className="gap-id">{gap.gap_id}</p>
                  </div>

                  <a href={gap.evidence_url} target="_blank" rel="noreferrer" className="evidence-link">
                    <img src={gap.evidence_url} alt={`Evidence for ${gap.concept}`} loading="lazy" />
                    <span>Evidence</span>
                  </a>

                  <button type="button" onClick={() => handleCycleStatus(gap)} className="status-button">
                    {gap.status}
                  </button>
                </article>
              ))
            )}
          </div>
        </article>
      </section>
    </main>
=======
    <StateProvider>
      <BrainStateProvider>
        <CourseProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<MissionControlPage />} />
              <Route path="gaps" element={<KnowledgeGapsPage />} />
              <Route path="quiz" element={<QuizPage />} />
              <Route path="schedule" element={<SchedulePage />} />
              <Route path="planner" element={<StudyPlannerPage />} />
              <Route path="documents" element={<DocumentHubPage />} />
              <Route path="history" element={<SessionHistoryPage />} />
              <Route path="ask" element={<AskSentinelPage />} />
              <Route path="preferences" element={<PreferencesPage />} />
            </Route>
          </Routes>
        </CourseProvider>
      </BrainStateProvider>
    </StateProvider>
>>>>>>> Stashed changes
  );
}
