import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCourse } from "../context/CourseContext";
import { DeadlineBanner } from "../components/DeadlineBanner";
import { DocumentHub } from "../components/DocumentHub";
import { GapList } from "../components/GapList";
import { LearningLoopDiagram } from "../components/LearningLoopDiagram";
import { ReadinessRadarTopics } from "../components/ReadinessRadarTopics";
import { StatCards } from "../components/StatCards";
import { TopBar } from "../components/TopBar";
import { TopicMastery } from "../components/TopicMastery";
import type { LearningState } from "../types";
import { emptyState } from "../api";

function buildStateFromCourseData(courseData: NonNullable<ReturnType<typeof useCourse>["courseData"]>): LearningState {
  const s = courseData.stats;
  return {
    ...emptyState,
    readiness_axes: { ...emptyState.readiness_axes, concept_mastery: s.masteryPercent / 100 },
    gaps: courseData.gaps,
    captures: Array.from({ length: s.sentinelSessionsThisWeek }, (_, i) => ({
      capture_id: `mock-${i}`,
      timestamp_utc: new Date().toISOString(),
      app_name: "",
      window_title: "",
      socratic_prompt: "",
      gaps: [],
    })),
  };
}

export function MissionControlPage() {
  const { courseId, courseData, allCoursesSummary, setCourseId, liveAvailable, liveError } = useCourse();
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
          <section className="dashboard-section">
            <LearningLoopDiagram />
          </section>
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

  const state = buildStateFromCourseData(courseData);
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
        openGapsCount={courseData.stats.activeGaps}
        deadlines={courseData.deadlines}
        state={state}
      />
      <section id="mission-control" aria-label="Mission Control">
        {!liveAvailable && <p className="status-line">{liveError ?? "Live data unavailable. Showing fallback dashboard slices."}</p>}
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
      <section className="gaps-resources-section">
        <h2 className="section-heading">GAPS & RESOURCES</h2>
        <div className="gaps-resources-grid">
          <GapList
            state={state}
            loading={false}
            error={null}
            onCycleStatus={async () => {}}
            gaps={courseData.gaps}
            captureTimestamps={courseData.captureTimestamps}
          />
          <DocumentHub sectionId="document-hub" documents={courseData.documents} />
        </div>
      </section>
    </div>
  );
}
