import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { getCourseData, COURSES } from "../data/courses";
import type { CourseData, CourseInfo } from "../data/courses";

export type CourseId = "all" | "cs2040" | "ee2001";

interface CourseContextValue {
  courseId: CourseId;
  setCourseId: (id: CourseId) => void;
  courses: CourseInfo[];
  courseData: CourseData | null;
  /** For "all" view: aggregated stats across courses. */
  allCoursesSummary: Array<{ course: CourseInfo; data: CourseData }>;
}

const CourseContext = createContext<CourseContextValue | null>(null);

export function CourseProvider({ children }: { children: React.ReactNode }) {
  const [courseId, setCourseIdState] = useState<CourseId>("all");

  const setCourseId = useCallback((id: CourseId) => {
    setCourseIdState(id);
  }, []);

  const courseData = useMemo(() => {
    if (courseId === "all") return null;
    return getCourseData(courseId) ?? null;
  }, [courseId]);

  const allCoursesSummary = useMemo(() => {
    return COURSES.map((course) => {
      const data = getCourseData(course.id);
      return { course, data: data! };
    }).filter((x) => x.data != null);
  }, []);

  const value = useMemo<CourseContextValue>(
    () => ({
      courseId,
      setCourseId,
      courses: COURSES,
      courseData,
      allCoursesSummary,
    }),
    [courseId, setCourseId, courseData, allCoursesSummary]
  );

  return <CourseContext.Provider value={value}>{children}</CourseContext.Provider>;
}

export function useCourse(): CourseContextValue {
  const ctx = useContext(CourseContext);
  if (!ctx) throw new Error("useCourse must be used within CourseProvider");
  return ctx;
}
