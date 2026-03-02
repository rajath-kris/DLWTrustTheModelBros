export interface MockDocument {
  doc_id?: string;
  course_id?: string;
  topic_id?: string;
  course_label?: string;
  topic_label?: string;
  name: string;
  size: string;
  upload_date: string;
  type: "anchor" | "pdf" | "other";
  path?: string;
  is_anchor?: boolean;
}

export const MOCK_DOCUMENTS: MockDocument[] = [
  {
    name: "CS2040_Syllabus.pdf",
    size: "1.2 MB",
    upload_date: "2026-02-28",
    type: "anchor",
    path: "/path/to/CS2040_Syllabus.pdf",
  },
  {
    name: "Lecture_07_Trees.pdf",
    size: "3.4 MB",
    upload_date: "2026-02-25",
    type: "pdf",
    path: "/path/to/Lecture_07_Trees.pdf",
  },
  {
    name: "Lecture_08_DP.pdf",
    size: "2.1 MB",
    upload_date: "2026-02-24",
    type: "pdf",
    path: "/path/to/Lecture_08_DP.pdf",
  },
  {
    name: "Practice_Problems_W8.pdf",
    size: "0.8 MB",
    upload_date: "2026-02-23",
    type: "other",
    path: "/path/to/Practice_Problems_W8.pdf",
  },
];
