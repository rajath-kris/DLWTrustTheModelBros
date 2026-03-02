import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { useBrainState } from "./BrainStateContext";
import { getCourseData, type CourseData, type CourseInfo, COURSES } from "../data/courses";
import { buildHybridCourseData } from "../data/courses/liveAdapter";

export type CourseId = "all" | string;

interface CourseContextValue {
  courseId: CourseId;
  setCourseId: (id: CourseId) => void;
  courses: CourseInfo[];
  courseData: CourseData | null;
  /** For "all" view: aggregated stats across courses. */
  allCoursesSummary: Array<{ course: CourseInfo; data: CourseData }>;
  liveAvailable: boolean;
  liveError: string | null;
}

const CourseContext = createContext<CourseContextValue | null>(null);

function buildEmptyFallback(course: CourseInfo): CourseData {
  return {
    id: course.id,
    name: course.name,
    accentColor: course.accentColor,
    topicScores: [],
    gaps: [],
    documents: [],
    deadlines: [],
    sessions: [],
    stats: {
      masteryPercent: 0,
      activeGaps: 0,
      criticalGaps: 0,
      highGaps: 0,
      nearestDeadlineName: "No upcoming deadline",
      nearestDeadlineDays: 0,
      nearestDeadlineReadiness: 0,
      sentinelSessionsThisWeek: 0,
    },
    captureTimestamps: {},
  };
}

function buildLiveCourseInfo(baseCourses: CourseInfo[], stateCourseRows: { course_id: string; course_name: string }[]): CourseInfo[] {
  const map = new Map<string, CourseInfo>();
  for (const item of baseCourses) {
    map.set(item.id, item);
  }
  for (const row of stateCourseRows) {
    const id = row.course_id;
    if (!id || id === "all" || map.has(id)) {
      continue;
    }
    map.set(id, {
      id,
      name: row.course_name || id.toUpperCase(),
      accentColor: "#6b7280",
    });
  }
  return Array.from(map.values());
}

export function CourseProvider({ children }: { children: React.ReactNode }) {
  const [courseId, setCourseIdState] = useState<CourseId>("all");
  const { state, liveAvailable, error } = useBrainState();

  const setCourseId = useCallback((id: CourseId) => {
    setCourseIdState(id);
  }, []);

  const courses = useMemo(() => buildLiveCourseInfo(COURSES, state.courses), [state.courses]);

  const allCoursesSummary = useMemo(() => {
    return courses
      .filter((course) => course.id !== "all")
      .map((course) => {
        const fallback = getCourseData(course.id) ?? buildEmptyFallback(course);
        return {
          course,
          data: buildHybridCourseData(fallback, state, { liveAvailable }),
        };
      });
  }, [courses, state, liveAvailable]);

  const courseData = useMemo(() => {
    if (courseId === "all") {
      return null;
    }
    const selectedCourse = courses.find((item) => item.id === courseId);
    const fallback =
      getCourseData(courseId) ??
      (selectedCourse
        ? buildEmptyFallback(selectedCourse)
        : buildEmptyFallback({
            id: courseId,
            name: courseId.toUpperCase(),
            accentColor: "#6b7280",
          }));
    return buildHybridCourseData(fallback, state, { liveAvailable });
  }, [courseId, courses, state, liveAvailable]);

  const value = useMemo<CourseContextValue>(
    () => ({
      courseId,
      setCourseId,
      courses,
      courseData,
      allCoursesSummary,
      liveAvailable,
      liveError: error,
    }),
    [courseId, setCourseId, courses, courseData, allCoursesSummary, liveAvailable, error]
  );

  return <CourseContext.Provider value={value}>{children}</CourseContext.Provider>;
}

export function useCourse(): CourseContextValue {
  const ctx = useContext(CourseContext);
  if (!ctx) {
    throw new Error("useCourse must be used within CourseProvider");
  }
  return ctx;
}
