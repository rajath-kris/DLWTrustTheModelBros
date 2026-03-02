/**
 * Mock quiz data for full flow demo: questions and mock prepare helper.
 * Scoring, mastery, and gap logic live in quizEngine.
 */

import type {
  QuestionBankItem,
  QuizPrepareResponse,
  QuizSourceType,
  KnowledgeGap,
} from "../types";
import { generateSubmitResponse } from "../quiz/quizEngine";

export type Difficulty = "Easy" | "Medium" | "Hard";

/** Extended for mock only; difficulty not in API */
export interface MockQuestionBankItem extends QuestionBankItem {
  difficulty?: Difficulty;
}

/** Quiz course options for mock (course-based segregation) */
export const MOCK_QUIZ_COURSES = [
  { id: "dsa", name: "Data Structures & Algorithms" },
  { id: "circuit", name: "Circuit Analysis" },
] as const;

export type MockQuizCourseId = (typeof MOCK_QUIZ_COURSES)[number]["id"];

export const MOCK_QUESTION_BANK: MockQuestionBankItem[] = [
  // --- DSA ---
  // Dynamic Programming
  {
    question_id: "mock-dp-1",
    topic: "Dynamic Programming",
    source: "pyq",
    concept: "Memoization",
    question: "What is the main benefit of memoization in recursive solutions?",
    options: [
      "Reduces code length",
      "Avoids recomputing same subproblems",
      "Eliminates base cases",
      "Increases stack depth",
    ],
    correct_answer: "Avoids recomputing same subproblems",
    explanation:
      "Memoization caches results of subproblems so each is solved only once, turning exponential time into polynomial.",
    course_id: "dsa",
    difficulty: "Easy",
  },
  {
    question_id: "mock-dp-2",
    topic: "Dynamic Programming",
    source: "tutorial",
    concept: "Optimal Substructure",
    question: "A problem has optimal substructure when:",
    options: [
      "It has only one solution",
      "An optimal solution contains optimal solutions to its subproblems",
      "It uses a greedy strategy",
      "It has no overlapping subproblems",
    ],
    correct_answer: "An optimal solution contains optimal solutions to its subproblems",
    explanation: "Optimal substructure means the best solution for the whole problem is built from best solutions for subproblems.",
    course_id: "dsa",
    difficulty: "Medium",
  },
  {
    question_id: "mock-dp-3",
    topic: "Dynamic Programming",
    source: "sentinel",
    concept: "Tabulation",
    question: "In bottom-up DP tabulation, fill order is typically:",
    options: [
      "Largest subproblem first",
      "Base cases first, then dependent states",
      "Random order",
      "Top-down only",
    ],
    correct_answer: "Base cases first, then dependent states",
    explanation: "Tabulation fills the table from smallest subproblems to the target, so dependencies are ready when needed.",
    course_id: "dsa",
    difficulty: "Medium",
  },
  // Graph Algorithms
  {
    question_id: "mock-graph-1",
    topic: "Graph Algorithms",
    source: "pyq",
    concept: "BFS/DFS",
    question: "Which traversal uses a stack (explicit or call stack)?",
    options: ["BFS only", "DFS only", "Both", "Neither"],
    correct_answer: "DFS only",
    explanation: "DFS goes deep first and uses a stack; BFS uses a queue for level order.",
    course_id: "dsa",
    difficulty: "Easy",
  },
  {
    question_id: "mock-graph-2",
    topic: "Graph Algorithms",
    source: "tutorial",
    concept: "Shortest Paths",
    question: "Dijkstra's algorithm is correct for graphs with:",
    options: [
      "Only negative weights",
      "Non-negative edge weights",
      "No cycles",
      "Only one source",
    ],
    correct_answer: "Non-negative edge weights",
    explanation: "With non-negative weights, the greedy choice (closest unvisited node) stays optimal.",
    course_id: "dsa",
    difficulty: "Medium",
  },
  {
    question_id: "mock-graph-3",
    topic: "Graph Algorithms",
    source: "sentinel",
    concept: "Cycle Detection",
    question: "In a directed graph, a back edge in DFS indicates:",
    options: ["A tree edge", "A cross edge", "A cycle", "Disconnected component"],
    correct_answer: "A cycle",
    explanation: "A back edge goes to an ancestor in the DFS tree, which implies a cycle.",
    course_id: "dsa",
    difficulty: "Hard",
  },
  // Binary Trees
  {
    question_id: "mock-tree-1",
    topic: "Binary Trees & Traversal",
    source: "pyq",
    concept: "Traversal Order",
    question: "In-order traversal of a BST gives:",
    options: ["Random order", "Sorted order", "Reverse sorted", "Level order"],
    correct_answer: "Sorted order",
    explanation: "In a BST, in-order visits left, root, right, which yields ascending order.",
    course_id: "dsa",
    difficulty: "Easy",
  },
  {
    question_id: "mock-tree-2",
    topic: "Binary Trees & Traversal",
    source: "tutorial",
    concept: "Tree Properties",
    question: "Height of a balanced BST with n nodes is:",
    options: ["O(n)", "O(log n)", "O(sqrt n)", "O(1)"],
    correct_answer: "O(log n)",
    explanation: "Balanced trees keep height logarithmic, so operations stay O(log n).",
    course_id: "dsa",
    difficulty: "Medium",
  },
  {
    question_id: "mock-tree-3",
    topic: "Binary Trees & Traversal",
    source: "sentinel",
    concept: "Traversal Order",
    question: "Which traversal is used to copy a tree?",
    options: ["In-order only", "Pre-order", "Post-order", "Any order works"],
    correct_answer: "Pre-order",
    explanation: "Pre-order (root first) lets you create the root then recurse to left and right subtrees.",
    course_id: "dsa",
    difficulty: "Easy",
  },
  // SQL (DSA-related / general CS)
  {
    question_id: "mock-sql-1",
    topic: "SQL Queries",
    source: "pyq",
    concept: "JOIN operations",
    question: "An INNER JOIN returns rows where:",
    options: [
      "At least one side matches",
      "Both sides have a match",
      "Left side has a match",
      "Right side has a match",
    ],
    correct_answer: "Both sides have a match",
    explanation: "INNER JOIN keeps only rows with matching keys in both tables.",
    course_id: "dsa",
    difficulty: "Easy",
  },
  {
    question_id: "mock-sql-2",
    topic: "SQL Queries",
    source: "tutorial",
    concept: "Aggregation",
    question: "HAVING is used to filter:",
    options: ["Rows before grouping", "Groups after GROUP BY", "Columns", "Joins"],
    correct_answer: "Groups after GROUP BY",
    explanation: "WHERE filters rows; HAVING filters groups after aggregation.",
    course_id: "dsa",
    difficulty: "Medium",
  },
  {
    question_id: "mock-sql-3",
    topic: "SQL Queries",
    source: "sentinel",
    concept: "Subqueries",
    question: "A correlated subquery is executed:",
    options: [
      "Once before the outer query",
      "Once for each row of the outer query",
      "Only when JOIN is used",
      "Never in production",
    ],
    correct_answer: "Once for each row of the outer query",
    explanation: "Correlated subqueries reference the outer row and run per outer row.",
    course_id: "dsa",
    difficulty: "Hard",
  },
  // --- Circuit Analysis ---
  {
    question_id: "mock-circuit-1",
    topic: "Basic Circuit Laws",
    source: "pyq",
    concept: "Kirchhoff's Current Law",
    question: "What does KCL state about currents at a node?",
    options: [
      "Sum of currents equals zero",
      "Current is constant throughout",
      "Voltage drops sum to zero",
      "Power is conserved",
    ],
    correct_answer: "Sum of currents equals zero",
    explanation: "KCL states that the algebraic sum of currents entering and leaving a node is zero.",
    course_id: "circuit",
    difficulty: "Easy",
  },
  {
    question_id: "mock-circuit-2",
    topic: "Basic Circuit Laws",
    source: "tutorial",
    concept: "Kirchhoff's Voltage Law",
    question: "KVL states that around any closed loop:",
    options: [
      "Current is constant",
      "The algebraic sum of voltage drops equals zero",
      "Resistance is constant",
      "Power is conserved",
    ],
    correct_answer: "The algebraic sum of voltage drops equals zero",
    explanation: "KVL states that the sum of voltage rises and drops around a closed loop is zero.",
    course_id: "circuit",
    difficulty: "Easy",
  },
  {
    question_id: "mock-circuit-3",
    topic: "Resistor Networks",
    source: "sentinel",
    concept: "Series and Parallel",
    question: "Two resistors in parallel have equivalent resistance:",
    options: [
      "Greater than the largest",
      "Less than the smallest",
      "Equal to the sum",
      "Equal to the product",
    ],
    correct_answer: "Less than the smallest",
    explanation: "Parallel resistance is 1/R_eq = 1/R1 + 1/R2, so R_eq < min(R1,R2).",
    course_id: "circuit",
    difficulty: "Easy",
  },
  {
    question_id: "mock-circuit-4",
    topic: "Resistor Networks",
    source: "pyq",
    concept: "Series and Parallel",
    question: "Voltage division applies to resistors in:",
    options: ["Parallel only", "Series only", "Both", "Neither"],
    correct_answer: "Series only",
    explanation: "In series, voltage divides in proportion to resistance; in parallel, current divides.",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-5",
    topic: "Capacitors & Inductors",
    source: "tutorial",
    concept: "RC/RL time constants",
    question: "The time constant τ for an RC circuit is:",
    options: ["R/C", "R + C", "R × C", "C/R"],
    correct_answer: "R × C",
    explanation: "τ = RC; it has units of seconds and characterizes the rate of charge/discharge.",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-6",
    topic: "Capacitors & Inductors",
    source: "sentinel",
    concept: "Impedance",
    question: "At DC (zero frequency), an ideal inductor behaves like:",
    options: ["Open circuit", "Short circuit", "Resistor", "Capacitor"],
    correct_answer: "Short circuit",
    explanation: "Inductor impedance jωL → 0 as ω → 0, so at DC it acts as a short.",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-7",
    topic: "AC Circuit Analysis",
    source: "pyq",
    concept: "Phasor analysis",
    question: "In phasor analysis, we represent a sinusoidal voltage as:",
    options: [
      "A time-varying vector",
      "A complex number (magnitude and phase)",
      "A real number only",
      "A frequency sweep",
    ],
    correct_answer: "A complex number (magnitude and phase)",
    explanation: "Phasors encode amplitude and phase as a complex number for steady-state AC analysis.",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-8",
    topic: "AC Circuit Analysis",
    source: "tutorial",
    concept: "Impedance",
    question: "The impedance of a capacitor C at frequency ω is:",
    options: ["jωC", "1/(jωC)", "ωC", "j/ωC"],
    correct_answer: "1/(jωC)",
    explanation: "Z_C = 1/(jωC); the capacitor opposes changes in voltage.",
    course_id: "circuit",
    difficulty: "Hard",
  },
  {
    question_id: "mock-circuit-9",
    topic: "Thevenin & Norton Theorems",
    source: "sentinel",
    concept: "Equivalent circuits",
    question: "Thevenin equivalent consists of:",
    options: [
      "A voltage source in series with a resistance",
      "A current source in parallel with a resistance",
      "Only resistors",
      "Only sources",
    ],
    correct_answer: "A voltage source in series with a resistance",
    explanation: "Any linear one-port can be replaced by V_th in series with R_th.",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-10",
    topic: "Op-Amps",
    source: "pyq",
    concept: "Ideal op-amp",
    question: "For an ideal op-amp in negative feedback, the input terminals have:",
    options: [
      "Large voltage difference",
      "Virtual short (same voltage)",
      "Zero current",
      "Infinite gain",
    ],
    correct_answer: "Virtual short (same voltage)",
    explanation: "Negative feedback drives the differential input to zero (virtual short).",
    course_id: "circuit",
    difficulty: "Medium",
  },
  {
    question_id: "mock-circuit-11",
    topic: "Op-Amps",
    source: "tutorial",
    concept: "Ideal op-amp",
    question: "Ideal op-amp has infinite:",
    options: [
      "Output resistance",
      "Input resistance and zero output resistance",
      "Input resistance, zero output resistance, infinite gain",
      "Bandwidth",
    ],
    correct_answer: "Input resistance, zero output resistance, infinite gain",
    explanation: "Ideal op-amp: infinite input Z, zero output Z, infinite open-loop gain.",
    course_id: "circuit",
    difficulty: "Easy",
  },
  {
    question_id: "mock-circuit-12",
    topic: "Frequency Response",
    source: "sentinel",
    concept: "Transfer functions",
    question: "A low-pass filter's gain at high frequencies:",
    options: ["Increases", "Stays constant", "Decreases toward zero", "Oscillates"],
    correct_answer: "Decreases toward zero",
    explanation: "Low-pass filters attenuate high frequencies; gain rolls off (e.g. -20 dB/decade).",
    course_id: "circuit",
    difficulty: "Easy",
  },
];

/** Default initial mastery (before quiz) for mock topic updates */
export const MOCK_INITIAL_MASTERY: Record<string, number> = {
  "Dynamic Programming": 0.5,
  "Graph Algorithms": 0.45,
  "Binary Trees & Traversal": 0.6,
  "SQL Queries": 0.4,
  "Basic Circuit Laws": 0.75,
  "Resistor Networks": 0.5,
  "Capacitors & Inductors": 0.4,
  "AC Circuit Analysis": 0.4,
  "Thevenin & Norton Theorems": 0.5,
  "Op-Amps": 0.45,
  "Frequency Response": 0.5,
};

function normalized(s: string): string {
  return s.trim().toLowerCase();
}

/**
 * Pick up to `count` questions from pool matching topic and sources.
 */
export function mockPrepare(
  topic: string,
  sources: QuizSourceType[],
  count: number,
  courseId: string
): QuizPrepareResponse {
  const pool = MOCK_QUESTION_BANK.filter((q) => {
    if (courseId !== "all" && q.course_id !== "all" && q.course_id !== courseId) return false;
    if (topic !== "All Topics" && normalized(q.topic) !== normalized(topic)) return false;
    return sources.includes(q.source);
  });
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  const questions = shuffled.slice(0, Math.max(1, Math.min(25, count))).map((q) => ({
    ...q,
    question_id: q.question_id,
    topic: q.topic,
    source: q.source,
    concept: q.concept,
    question: q.question,
    options: q.options,
    correct_answer: q.correct_answer,
    explanation: q.explanation ?? null,
    course_id: q.course_id,
  }));
  return {
    session_id: `mock-session-${Date.now()}`,
    topic: topic === "All Topics" ? (questions[0]?.topic ?? topic) : topic,
    questions,
    selection_summary: {
      gap_matched_count: 0,
      wrong_repeat_count: 0,
      deadline_boosted_count: 0,
      coverage_count: questions.length,
    },
  };
}

/**
 * Build submit response via QuizEngine (single source of truth for scoring/mastery/gaps).
 */
export function mockSubmit(
  questions: QuestionBankItem[],
  answers: Record<string, string>,
  topic: string,
  sources: QuizSourceType[],
  courseId: string
) {
  return generateSubmitResponse(questions, answers, topic, sources, courseId);
}

/**
 * Generate mock knowledge gaps from wrong answers for display in Gaps tab.
 */
export function mockGapsFromWrongAnswers(
  questions: QuestionBankItem[],
  answers: Record<string, string>,
  courseId: string
): KnowledgeGap[] {
  const gaps: KnowledgeGap[] = [];
  for (const q of questions) {
    const userAnswer = answers[q.question_id] ?? "";
    if (normalized(userAnswer) === normalized(q.correct_answer)) continue;
    gaps.push({
      gap_id: `mock-gap-${q.question_id}`,
      concept: q.concept,
      severity: 0.7,
      confidence: 0.8,
      basis_question: q.question,
      basis_answer_excerpt: q.correct_answer,
      gap_type: "concept",
      status: "open",
      capture_id: "",
      evidence_url: "",
      deadline_score: 0.5,
      priority_score: 0.7,
      course_id: courseId,
    });
  }
  return gaps;
}
