import { useMemo } from "react";
import { useCourse } from "../context/CourseContext";
import { useBrainState } from "../context/BrainStateContext";
import { format, addDays, differenceInDays } from "date-fns";

interface PlanDay {
  date: Date;
  topics: { name: string; minutes: number; mastery: number }[];
  completed: boolean;
}

function buildPlan(courseData: { deadlines: { due_date: string }[]; topicScores: { name: string; current: number }[] }): PlanDay[] {
  const upcoming = courseData.deadlines
    .filter((d) => new Date(d.due_date) >= new Date())
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
  if (upcoming.length === 0) return [];
  const nearest = new Date(upcoming[0].due_date);
  const daysUntil = Math.max(1, differenceInDays(nearest, new Date()));
  const sortedTopics = [...courseData.topicScores].sort((a, b) => a.current - b.current);
  const plan: PlanDay[] = [];
  for (let i = 0; i < Math.min(7, daysUntil); i++) {
    const date = addDays(new Date(), i);
    const topicIndex = i % sortedTopics.length;
    const topic = sortedTopics[topicIndex];
    plan.push({
      date,
      topics: [{ name: topic.name, minutes: 45 + (i % 3) * 15, mastery: Math.round(topic.current * 100) }],
      completed: false,
    });
  }
  return plan;
}

function buildPlanFromStudyActions(
  actions: { title: string; eta_minutes: number; topic_id: string }[],
  topicScores: { name: string; current: number }[]
): PlanDay[] {
  return actions.slice(0, 7).map((action, idx) => {
    const topic = topicScores.find((item) => item.name.toLowerCase().includes(action.topic_id.replace(/-/g, " ")));
    return {
      date: addDays(new Date(), idx),
      topics: [
        {
          name: action.title,
          minutes: action.eta_minutes,
          mastery: Math.round((topic?.current ?? 0.6) * 100),
        },
      ],
      completed: false,
    };
  });
}

export function StudyPlannerPage() {
  const { courseId, courseData } = useCourse();
  const { state } = useBrainState();
  const liveActions = useMemo(
    () => state.study_actions.filter((item) => courseId === "all" || item.course_id === courseId),
    [state.study_actions, courseId]
  );
  const plan = useMemo(() => {
    if (courseData && liveActions.length > 0) {
      return buildPlanFromStudyActions(liveActions, courseData.topicScores);
    }
    return courseData ? buildPlan(courseData) : [];
  }, [courseData, liveActions]);
  const hasDeadlines = courseData && courseData.deadlines.some((d) => new Date(d.due_date) >= new Date());

  const courseBadge = courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

  if (!courseData && courseId !== "all") {
    return (
      <div className="page-shell page-fade">
        <h1>Study Planner</h1>
        <p className="status-line">Select a course.</p>
      </div>
    );
  }

  if (courseId === "all" && liveActions.length === 0) {
    return (
      <div className="page-shell page-fade">
        <h1>Study Planner</h1>
        <p className="status-line">Select a single course to see your study plan.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-fade">
      <header className="planner-page-header">
        <div className="planner-page-title-row">
          <h1>Study Planner</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <button type="button" className="top-bar-btn primary">Regenerate Plan</button>
        </div>
      </header>
      <p className="planner-intro">
        Your plan is based on current mastery, knowledge gaps, and days until deadlines.
      </p>

      {!hasDeadlines && liveActions.length === 0 ? (
        <div className="planner-empty">
          Add a deadline in Schedule to generate your study plan.
        </div>
      ) : (
        <>
          <section className="planner-timeline">
            <h2>Day-by-day plan</h2>
            <ul className="planner-day-list">
              {plan.map((day) => (
                <li key={day.date.toISOString()} className="planner-day-card">
                  <div className="planner-day-header">
                    <span className="planner-day-date">{format(day.date, "EEE, MMM d")}</span>
                    <label className="planner-day-check">
                      <input type="checkbox" defaultChecked={day.completed} />
                      Done
                    </label>
                  </div>
                  <ul className="planner-day-topics">
                    {day.topics.map((t) => (
                      <li key={t.name} className="planner-day-topic">
                        <span className="planner-topic-name">{t.name}</span>
                        <span className="planner-topic-meta">{t.minutes} min · {t.mastery}% mastery</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </section>
          <section className="planner-projection">
            <h2>Readiness projection</h2>
            <div className="planner-chart-wrap">
              <div className="planner-chart-legend">
                <span className="planner-legend-dot planner-legend-with-plan" /> With Plan
                <span className="planner-legend-dot planner-legend-current" /> Current Pace
              </div>
              <div className="planner-chart-bars">
                {[70, 75, 82, 88, 92].map((v, i) => (
                  <div key={i} className="planner-chart-bar-row">
                    <span className="planner-chart-label">{`D${i + 1}`}</span>
                    <div className="planner-chart-track">
                      <div className="planner-chart-bar planner-chart-with-plan" style={{ width: `${v}%` }} />
                    </div>
                    <div className="planner-chart-track">
                      <div className="planner-chart-bar planner-chart-current" style={{ width: `${Math.max(0, v - 8 - i * 2)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
