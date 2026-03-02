import { useState, useRef, useEffect, useCallback } from "react";
import { useCourse } from "../context/CourseContext";
import {
  format,
  differenceInDays,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isToday,
  isSameDay,
  addMonths,
  subMonths,
  startOfDay,
  endOfDay,
} from "date-fns";
import type { MockDeadline } from "../data/courses";
import { COURSES, getCourseData } from "../data/courses";

type ExtendedDeadline = MockDeadline & {
  courseId?: string;
  courseName?: string;
  accentColor?: string;
};

function getReadinessColor(readiness: number): string {
  return readiness < 60 ? "#e74c3c" : readiness < 80 ? "#f59e0b" : "#22c55e";
}

export function SchedulePage() {
  const { courseId, courseData, allCoursesSummary, courses } = useCourse();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [popover, setPopover] = useState<{ anchor: DOMRect; deadlines: ExtendedDeadline[] } | null>(null);
  const [userAddedDeadlines, setUserAddedDeadlines] = useState<ExtendedDeadline[]>([]);
  const [highlightDeadlineId, setHighlightDeadlineId] = useState<string | null>(null);

  const baseDeadlines: ExtendedDeadline[] =
    courseId === "all"
      ? allCoursesSummary.flatMap(({ data }) =>
          data.deadlines.map((d) => ({
            ...d,
            courseId: data.id,
            courseName: data.name,
            accentColor: data.accentColor,
          }))
        )
      : courseData?.deadlines.map((d) => ({
          ...d,
          courseId: courseData.id,
          courseName: courseData.name,
          accentColor: courseData.accentColor,
        })) ?? [];

  const displayDeadlines: ExtendedDeadline[] = [...baseDeadlines, ...userAddedDeadlines];

  const today = startOfDay(new Date());
  const upcoming = useCallback(() => {
    return [...displayDeadlines]
      .filter((d) => new Date(d.due_date) >= today)
      .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
  }, [displayDeadlines])();

  const panelDeadlines =
    selectedDate === null
      ? upcoming
      : [...displayDeadlines]
          .filter((d) => new Date(d.due_date) <= endOfDay(selectedDate))
          .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const days = eachDayOfInterval({ start: monthStart, end: monthEnd });

  const courseBadge =
    courseId === "all" ? "All" : courseData?.id === "cs2040" ? "CS2040" : courseData?.id === "ee2001" ? "EE2001" : courseId;

  const handleDayClick = useCallback(
    (day: Date, dayDeadlines: ExtendedDeadline[], cellEl: HTMLDivElement) => {
      if (selectedDate !== null && isSameDay(day, selectedDate)) {
        setSelectedDate(null);
        setPopover(null);
        return;
      }
      setSelectedDate(day);
      if (dayDeadlines.length > 0) {
        setPopover({ anchor: cellEl.getBoundingClientRect(), deadlines: dayDeadlines });
      } else {
        setPopover(null);
      }
    },
    [selectedDate]
  );

  const handleAddSave = useCallback(
    (payload: { name: string; courseId: string; dueDate: string; type: string }) => {
      const course = getCourseData(payload.courseId) ?? COURSES.find((c) => c.id === payload.courseId);
      const name = payload.name.trim();
      const dueDate = payload.dueDate;
      if (!name || !dueDate || !course) return;
      const extended: ExtendedDeadline = {
        id: crypto.randomUUID(),
        name,
        due_date: new Date(dueDate).toISOString(),
        readiness_score: 0,
        courseId: course.id,
        courseName: course.name,
        accentColor: course.accentColor,
      };
      setUserAddedDeadlines((prev) => [...prev, extended]);
      setHighlightDeadlineId(extended.id);
      setAddModalOpen(false);
    },
    []
  );

  useEffect(() => {
    if (!highlightDeadlineId) return;
    const t = setTimeout(() => setHighlightDeadlineId(null), 600);
    return () => clearTimeout(t);
  }, [highlightDeadlineId]);

  if (!courseData && courseId !== "all") {
    return (
      <div className="page-shell page-fade">
        <h1>Schedule</h1>
        <p className="status-line">Select a course.</p>
      </div>
    );
  }

  const emptyMessage =
    selectedDate === null
      ? "No upcoming deadlines. Add one with + Add Deadline."
      : "No deadlines around this date.";

  return (
    <div className="page-shell page-fade">
      <header className="schedule-page-header">
        <div className="schedule-page-title-row">
          <h1>Schedule</h1>
          <span className="pill pill-course-badge">{courseBadge}</span>
          <button type="button" className="top-bar-btn primary" onClick={() => setAddModalOpen(true)}>
            + Add Deadline
          </button>
        </div>
      </header>

      <div className="schedule-page-layout">
        <div className="schedule-calendar-wrap">
          <div className="schedule-calendar-header">
            <button type="button" className="schedule-nav-btn" onClick={() => setCurrentMonth((m) => subMonths(m, 1))}>
              ←
            </button>
            <h2 className="schedule-month-title">{format(currentMonth, "MMMM yyyy")}</h2>
            <button type="button" className="schedule-nav-btn" onClick={() => setCurrentMonth((m) => addMonths(m, 1))}>
              →
            </button>
          </div>
          <div className="schedule-calendar-grid">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <div key={d} className="schedule-calendar-weekday">
                {d}
              </div>
            ))}
            {Array.from({ length: monthStart.getDay() }, (_, i) => (
              <div key={`pad-${i}`} className="schedule-calendar-day schedule-calendar-day-pad" />
            ))}
            {days.map((day) => {
              const dayDeadlines = displayDeadlines.filter(
                (d) =>
                  isSameMonth(new Date(d.due_date), day) &&
                  format(new Date(d.due_date), "yyyy-MM-dd") === format(day, "yyyy-MM-dd")
              );
              const isSelected = selectedDate !== null && isSameDay(day, selectedDate);
              return (
                <div
                  key={day.toISOString()}
                  role="button"
                  tabIndex={0}
                  className={`schedule-calendar-day ${isToday(day) ? "schedule-calendar-day-today" : ""} ${isSelected ? "schedule-calendar-day-selected" : ""}`}
                  onClick={(e) => {
                    const target = e.currentTarget;
                    handleDayClick(day, dayDeadlines, target);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleDayClick(day, dayDeadlines, e.currentTarget);
                    }
                  }}
                >
                  <span className="schedule-day-num">{format(day, "d")}</span>
                  {dayDeadlines.length > 0 && (
                    <div className="schedule-day-dots">
                      {dayDeadlines.slice(0, 3).map((d) => (
                        <span
                          key={d.id}
                          className="schedule-day-dot"
                          style={{ background: getReadinessColor(d.readiness_score ?? 0) }}
                          title={d.name}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <aside className="schedule-upcoming">
          <h3>Upcoming Deadlines</h3>
          {panelDeadlines.length === 0 ? (
            <p className="schedule-empty">{emptyMessage}</p>
          ) : (
            <ul className="schedule-upcoming-list">
              {panelDeadlines.map((d) => {
                const daysLeft = differenceInDays(new Date(d.due_date), new Date());
                const readiness = d.readiness_score ?? 0;
                const daysClass =
                  daysLeft <= 3
                    ? "schedule-upcoming-days-urgent"
                    : daysLeft <= 7
                      ? "schedule-upcoming-days-warning"
                      : "schedule-upcoming-days-ok";
                return (
                  <li
                    key={d.id}
                    className={`schedule-upcoming-item ${highlightDeadlineId === d.id ? "schedule-upcoming-item-inserted" : ""}`}
                  >
                    <span
                      className="schedule-upcoming-course"
                      style={{ borderColor: d.accentColor ?? "#6b7280" }}
                    >
                      {d.courseId?.toUpperCase() ?? "—"}
                    </span>
                    <span className="schedule-upcoming-name">{d.name}</span>
                    <span className={`schedule-upcoming-days ${daysClass}`}>{daysLeft}d</span>
                    <div className="schedule-upcoming-readiness-group">
                      <div className="schedule-upcoming-readiness">
                        <div
                          className="schedule-readiness-bar"
                          style={{
                            width: `${Math.min(100, Math.max(0, readiness))}%`,
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
        </aside>
      </div>

      {popover !== null && (
        <div
          className="schedule-day-popover"
          style={{
            position: "fixed",
            left: popover.anchor.left,
            bottom: window.innerHeight - popover.anchor.top + 8,
            zIndex: 400,
          }}
        >
          {popover.deadlines.map((d) => {
            const daysLeft = differenceInDays(new Date(d.due_date), new Date());
            const readiness = d.readiness_score ?? 0;
            return (
              <div key={d.id} className="schedule-popover-item">
                <strong>{d.name}</strong>
                <span className="schedule-popover-course" style={{ borderColor: d.accentColor ?? "#6b7280" }}>
                  {d.courseId?.toUpperCase() ?? "—"}
                </span>
                <span>{daysLeft}d left</span>
                <span>Readiness: {readiness}%</span>
              </div>
            );
          })}
        </div>
      )}

      {popover !== null && (
        <div
          className="schedule-popover-backdrop"
          aria-hidden
          onClick={() => setPopover(null)}
          onKeyDown={(e) => e.key === "Escape" && setPopover(null)}
        />
      )}

      {addModalOpen && (
        <AddDeadlineModal
          currentCourseId={courseId === "all" ? null : courseId}
          courses={courses}
          onSave={handleAddSave}
          onClose={() => setAddModalOpen(false)}
        />
      )}
    </div>
  );
}

const DEADLINE_TYPES = ["Exam", "Quiz", "Assignment", "Lab Report"] as const;

function AddDeadlineModal({
  currentCourseId,
  courses,
  onSave,
  onClose,
}: {
  currentCourseId: string | null;
  courses: { id: string; name: string }[];
  onSave: (payload: { name: string; courseId: string; dueDate: string; type: string }) => void;
  onClose: () => void;
}) {
  const defaultCourseId = currentCourseId && currentCourseId !== "all" ? currentCourseId : courses[0]?.id ?? "cs2040";
  const [name, setName] = useState("");
  const [courseId, setCourseId] = useState(defaultCourseId);
  const [dueDate, setDueDate] = useState("");
  const [type, setType] = useState<string>(DEADLINE_TYPES[0]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || !dueDate) return;
    onSave({ name: trimmed, courseId, dueDate, type });
    setName("");
    setDueDate("");
    setType(DEADLINE_TYPES[0]);
    setCourseId(defaultCourseId);
  };

  return (
    <div className="schedule-modal-backdrop" onClick={onClose}>
      <div className="schedule-modal" onClick={(e) => e.stopPropagation()}>
        <div className="schedule-modal-header">
          <h2>Add Deadline</h2>
          <button type="button" className="gap-detail-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <form className="schedule-modal-form" onSubmit={handleSubmit}>
          <label>Deadline name</label>
          <input
            type="text"
            placeholder="e.g. Mid-Term Exam"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <label>Course</label>
          <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <label>Date</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />
          <label>Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {DEADLINE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button type="submit" className="top-bar-btn primary">
            Save
          </button>
        </form>
      </div>
    </div>
  );
}
