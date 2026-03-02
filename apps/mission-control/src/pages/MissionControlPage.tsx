import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCourse } from "../context/CourseContext";
import { useLearningState } from "../context/StateContext";
import { DeadlineBanner } from "../components/DeadlineBanner";
import { DocumentHub } from "../components/DocumentHub";
import { GapList } from "../components/GapList";
import { LearningLoopDiagram } from "../components/LearningLoopDiagram";
import { ReadinessRadarTopics } from "../components/ReadinessRadarTopics";
import { StatCards } from "../components/StatCards";
import { TopBar } from "../components/TopBar";
import { TopicMastery } from "../components/TopicMastery";

export function MissionControlPage() {
  const { courseId, courseData, allCoursesSummary, setCourseId } = useCourse();
  const { state } = useLearningState();
  const navigate = useNavigate();
  const [deadlineBannerDismissed, setDeadlineBannerDismissed] = useState(false);

  if (courseId === "all") {
    return (
      <div className="page-shell page-fade">
        <TopBar
          onExportReport={() => console.log("Export Report (placeholder)")}
          onUploadDocs={() => navigate("/documents")}
        />
        <section className="all-courses-view" aria-label="All Courses">
          <h2 className="section-heading">ALL COURSES</h2>
          <div className="course-health-cards">
            {allCoursesSummary.map(({ course, data }) => (
              <article key={course.id} className="card course-health-card">
                <div className="course-health-card-header">
                  <span className="course-health-dot" style={{ background: course.accentColor }} aria-hidden />
                  <h3>{course.name}</h3>
                </div>
                <p className="course-health-mastery">Overall Mastery: {data.stats.masteryPercent}%</p>
                <p className="course-health-gaps">Active Gaps: {data.stats.activeGaps}</p>
                <p className="course-health-deadline">
                  Nearest: {data.stats.nearestDeadlineName} in {data.stats.nearestDeadlineDays}d
                </p>
                <button
                  type="button"
                  className="top-bar-btn primary"
                  onClick={() => {
                    setCourseId(course.id as "cs2040" | "ee2001");
                    navigate("/");
                  }}
                >
                  Go to Course
                </button>
              </article>
            ))}
          </div>
          <div className="all-courses-stats">
            <p>Total Sentinel sessions this week: {allCoursesSummary.reduce((s, { data }) => s + data.stats.sentinelSessionsThisWeek, 0)}</p>
          </div>
        </section>
      </div>
    );
  }

  if (!courseData) {
    return (
      <div className="page-shell page-fade">
        <TopBar />
        <p className="status-line">Select a course.</p>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="page-shell page-fade">
        <TopBar />
        <p className="status-line">Loading learning state...</p>
      </div>
    );
  }

  const captureTimestampMap = Object.fromEntries(
    state.captures.map((capture) => [capture.capture_id, capture.timestamp_utc])
  );
  const weakestTopic =
    courseData.topicScores.length > 0
      ? courseData.topicScores.reduce((acc, t) => (t.current < acc.current ? t : acc))
      : null;
  const allStrong =
    courseData.topicScores.length > 0 &&
    courseData.topicScores.every((t) => t.current >= 0.8);

  return (
    <div className="page-shell page-fade">
      <TopBar
        onExportReport={() => console.log("Export Report (placeholder)")}
        onUploadDocs={() => navigate("/documents")}
      />
      <DeadlineBanner
        dismissed={deadlineBannerDismissed}
        onDismiss={() => setDeadlineBannerDismissed(true)}
        onViewGaps={() => navigate("/gaps")}
        openGapsCount={state.gaps.filter((gap) => gap.status !== "closed").length}
        deadlines={courseData.deadlines}
        state={state}
      />
      <section id="mission-control" aria-label="Mission Control">
        <StatCards state={state} deadlines={courseData.deadlines} />
      </section>
      <section id="readiness-radar" className="overview-section" aria-label="Readiness and mastery">
        <h2 className="section-heading">OVERVIEW – READINESS & MASTERY</h2>
        <div className="content-grid">
          <article className="card radar-card">
            <header>
              <h3>Readiness Radar</h3>
              <p>Current Mastery vs Target (Deadline).</p>
            </header>
            <ReadinessRadarTopics topics={courseData.topicScores} showLive />
            <dl className="axis-legend axis-legend-swatches">
              <div>
                <span className="legend-swatch legend-current" aria-hidden />
                <span>Current Mastery</span>
              </div>
              <div>
                <span className="legend-swatch legend-target" aria-hidden />
                <span>Target (Deadline)</span>
              </div>
            </dl>
            <div className="radar-description">
              <p className="radar-insight">
                This graph compares your current mastery (blue) to your deadline target (purple) across six topics.
              </p>
              {allStrong ? (
                <p className="radar-insight radar-focus">You&apos;re on track; keep reviewing to maintain mastery.</p>
              ) : weakestTopic ? (
                <p className="radar-insight radar-focus">
                  Focus on <strong>{weakestTopic.name}</strong> — it&apos;s your weakest area and furthest from your target.
                </p>
              ) : null}
            </div>
          </article>
          <TopicMastery gaps={courseData.gaps} topics={courseData.topicScores} />
        </div>
      </section>
      <section className="dashboard-section">
        <LearningLoopDiagram />
      </section>
      <section className="gaps-resources-section">
        <h2 className="section-heading">GAPS & RESOURCES</h2>
        <div className="gaps-resources-grid">
          <GapList
            state={state}
            loading={false}
            error={null}
            onCycleStatus={async () => {}}
            gaps={state.gaps}
            captureTimestamps={{ ...courseData.captureTimestamps, ...captureTimestampMap }}
          />
          <DocumentHub sectionId="document-hub" documents={courseData.documents} />
        </div>
      </section>
    </div>
  );
}
