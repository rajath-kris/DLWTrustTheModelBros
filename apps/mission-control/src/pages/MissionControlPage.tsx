import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { differenceInDays, startOfDay } from "date-fns";
import { useCourse } from "../context/CourseContext";
import { DeadlineBanner } from "../components/DeadlineBanner";
import { DocumentHub } from "../components/DocumentHub";
import { GapList } from "../components/GapList";
import { LearningLoopDiagram } from "../components/LearningLoopDiagram";
import { ReadinessRadarTopics } from "../components/ReadinessRadarTopics";
import { StatCards } from "../components/StatCards";
import { TopBar } from "../components/TopBar";
import { TopicMastery } from "../components/TopicMastery";
import type { MockDeadline } from "../data/courses";
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

interface UpcomingDeadlineItem {
  id: string;
  name: string;
  due_date: string;
  readiness_score?: number;
  courseId: string;
  courseName: string;
  accentColor: string;
}

interface DeadlineSourceCourse {
  id: string;
  name: string;
  accentColor: string;
  deadlines: MockDeadline[];
}

function getReadinessColor(readiness: number): string {
  return readiness < 60 ? "#e74c3c" : readiness < 80 ? "#f59e0b" : "#22c55e";
}

function getReadinessPercent(readiness: number | undefined): number {
  if (readiness == null) return 0;
  const normalized = readiness <= 1 ? readiness * 100 : readiness;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function buildUpcomingDeadlines(
  courseId: string,
  courseData: DeadlineSourceCourse | null,
  allCoursesSummary: Array<{ data: DeadlineSourceCourse }>
): UpcomingDeadlineItem[] {
  const today = startOfDay(new Date()).getTime();
  const scopedCourses = courseId === "all" ? allCoursesSummary.map(({ data }) => data) : courseData ? [courseData] : [];

  return scopedCourses
    .flatMap((course) =>
      course.deadlines.map((deadline) => ({
        ...deadline,
        courseId: course.id,
        courseName: course.name,
        accentColor: course.accentColor,
      }))
    )
    .filter((deadline) => {
      const dueTime = new Date(deadline.due_date).getTime();
      return Number.isFinite(dueTime) && dueTime >= today;
    })
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
}

function UpcomingDeadlinesPanel({
  deadlines,
  onOpenSchedule,
}: {
  deadlines: UpcomingDeadlineItem[];
  onOpenSchedule: () => void;
}) {
  const visibleDeadlines = deadlines.slice(0, 6);

  return (
    <section className="dashboard-section mission-upcoming-section" aria-label="Upcoming deadlines">
      <div className="mission-upcoming-header">
        <h2 className="section-heading">UPCOMING DEADLINES</h2>
        <button type="button" className="top-bar-btn" onClick={onOpenSchedule}>
          Open Schedule
        </button>
      </div>
      <aside className="schedule-upcoming mission-upcoming-card">
        {visibleDeadlines.length === 0 ? (
          <p className="schedule-empty">No upcoming deadlines. Add one in Schedule.</p>
        ) : (
          <ul className="schedule-upcoming-list">
            {visibleDeadlines.map((deadline) => {
              const daysLeft = differenceInDays(new Date(deadline.due_date), new Date());
              const readiness = getReadinessPercent(deadline.readiness_score);
              const daysClass =
                daysLeft <= 3
                  ? "schedule-upcoming-days-urgent"
                  : daysLeft <= 7
                    ? "schedule-upcoming-days-warning"
                    : "schedule-upcoming-days-ok";
              return (
                <li key={`${deadline.courseId}-${deadline.id}`} className="schedule-upcoming-item">
                  <span className="schedule-upcoming-course" style={{ borderColor: deadline.accentColor }}>
                    {deadline.courseId.toUpperCase()}
                  </span>
                  <span className="schedule-upcoming-name">{deadline.name}</span>
                  <span className={`schedule-upcoming-days ${daysClass}`}>{daysLeft}d</span>
                  <div className="schedule-upcoming-readiness-group">
                    <div className="schedule-upcoming-readiness">
                      <div
                        className="schedule-readiness-bar"
                        style={{
                          width: `${readiness}%`,
                          background: getReadinessColor(readiness),
                        }}
                      />
                    </div>
                    <span className="schedule-upcoming-pct">{readiness}%</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {deadlines.length > visibleDeadlines.length && (
          <p className="mission-upcoming-overflow">Showing next {visibleDeadlines.length} deadlines.</p>
        )}
      </aside>
    </section>
  );
}

export function MissionControlPage() {
  const { courseId, courseData, allCoursesSummary, setCourseId, liveAvailable, liveError } = useCourse();
  const navigate = useNavigate();
  const [deadlineBannerDismissed, setDeadlineBannerDismissed] = useState(false);
  const upcomingDeadlines = buildUpcomingDeadlines(courseId, courseData, allCoursesSummary);

  if (courseId === "all") {
    return (
      <div className="page-shell page-fade">
        <TopBar
          onExportReport={() => console.log("Export Report (placeholder)")}
          onUploadDocs={() => navigate("/courses")}
        />
        <section className="dashboard-section card mission-home-cta" aria-label="Courses setup">
          <h2 className="section-heading">SETUP COURSES TO START SENTINEL</h2>
          <p className="status-line">
            Home no longer lists course cards. Use Courses to create courses, add topics, upload docs, and bind Sentinel sessions.
          </p>
          <div className="mission-home-cta-actions">
            <button type="button" className="top-bar-btn primary" onClick={() => navigate("/courses")}>
              Open Courses
            </button>
            {allCoursesSummary.length > 0 && (
              <button
                type="button"
                className="top-bar-btn"
                onClick={() => {
                  const firstCourseId = allCoursesSummary[0]?.course.id;
                  if (!firstCourseId) {
                    return;
                  }
                  setCourseId(firstCourseId);
                  navigate("/");
                }}
              >
                View First Course Dashboard
              </button>
            )}
          </div>
        </section>
        <section className="dashboard-section">
          <UpcomingDeadlinesPanel
            deadlines={upcomingDeadlines}
            onOpenSchedule={() => navigate("/schedule")}
          />
        </section>
        <section className="dashboard-section">
          <LearningLoopDiagram />
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
      <UpcomingDeadlinesPanel
        deadlines={upcomingDeadlines}
        onOpenSchedule={() => navigate("/schedule")}
      />
      <section id="readiness-radar" className="overview-section" aria-label="Readiness and mastery">
        <h2 className="section-heading">OVERVIEW - READINESS & MASTERY</h2>
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
                  Focus on <strong>{weakestTopic.name}</strong> - it&apos;s your weakest area and furthest from your target.
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

