import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { DeadlineBanner } from "../components/DeadlineBanner";
import { GapList } from "../components/GapList";
import { ReadinessRadarTopics } from "../components/ReadinessRadarTopics";
import { StatCards } from "../components/StatCards";
import { TopBar } from "../components/TopBar";
import { TopicMastery } from "../components/TopicMastery";
import { useLearningState } from "../context/LearningStateContext";

export function MissionControlPage() {
  const navigate = useNavigate();
  const { state, loading, error, liveAvailable } = useLearningState();

  const radarTopics = useMemo(
    () =>
      state.topics.map((topic) => ({
        name: topic.topic,
        label: topic.topic.length > 18 ? `${topic.topic.slice(0, 18)}...` : topic.topic,
        current: topic.mastery,
        target: Math.min(1, topic.mastery + 0.15),
      })),
    [state.topics]
  );

  const captureTimestamps = useMemo(
    () => Object.fromEntries(state.captures.map((capture) => [capture.capture_id, capture.timestamp_utc])),
    [state.captures]
  );

  return (
    <div className="page-shell page-fade">
      <TopBar onUploadDocs={() => navigate("/documents")} />
      {!liveAvailable && <p className="status-line">{error ?? "Using mock parity state."}</p>}
      {loading && <p className="status-line">Loading state...</p>}

      <DeadlineBanner
        dismissed={false}
        onDismiss={() => {}}
        onViewGaps={() => navigate("/gaps")}
        openGapsCount={state.gaps.filter((gap) => gap.status !== "closed").length}
        deadlines={[]}
        state={state}
      />

      <section id="mission-control" aria-label="Mission Control">
        <h2 className="section-heading">Mission Control</h2>
        <StatCards state={state} deadlines={[]} />
      </section>

      <section id="readiness-radar" className="overview-section" aria-label="Readiness and mastery">
        <h2 className="section-heading">Overview - Readiness and Mastery</h2>
        <div className="content-grid">
          <article className="card radar-card">
            <header>
              <h3>Readiness Radar</h3>
              <p>Current Mastery vs target by topic.</p>
            </header>
            {radarTopics.length === 0 ? <p className="status-line">No topic data yet.</p> : <ReadinessRadarTopics topics={radarTopics} showLive={liveAvailable} />}
          </article>
          <TopicMastery gaps={state.gaps} topics={radarTopics} />
        </div>
      </section>

      <section className="gaps-resources-section">
        <h2 className="section-heading">Gaps</h2>
        <div className="gaps-resources-grid">
          <GapList
            state={state}
            loading={loading}
            error={error}
            onCycleStatus={async () => {}}
            gaps={state.gaps}
            captureTimestamps={captureTimestamps}
          />
        </div>
      </section>
    </div>
  );
}
