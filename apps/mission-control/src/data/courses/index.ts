import type { CourseData, CourseInfo } from "./types";
import { CS2040_DATA } from "./cs2040";
import { EE2001_DATA } from "./ee2001";

export const COURSES: CourseInfo[] = [
  { id: "cs2040", name: "CS2040 — Data Structures & Algorithms", accentColor: "#3b82f6" },
  { id: "ee2001", name: "EE2001 — Circuit Analysis", accentColor: "#f97316" },
];

export function getCourseData(id: string): CourseData | null {
  if (id === "cs2040") return CS2040_DATA;
  if (id === "ee2001") return EE2001_DATA;
  return null;
}

export { CS2040_DATA } from "./cs2040";
export { EE2001_DATA } from "./ee2001";
export type { CourseData, CourseInfo, CourseStats, MockDeadline, MockDocument, MockSession } from "./types";
