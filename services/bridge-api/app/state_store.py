from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import (
    CaptureEvent,
    KnowledgeGap,
    LearningState,
    QuestionBankItem,
    QuizRecord,
    ReadinessAxes,
    utc_now_iso,
)


DEFAULT_QUESTION_BANK: list[QuestionBankItem] = [
    QuestionBankItem(
        question_id="qb-tree-postorder",
        topic="Binary Trees & Traversal",
        source="pyq",
        concept="Traversal Order",
        question="Which traversal visits the root node last?",
        options=["In-order", "Pre-order", "Post-order", "Level-order"],
        correct_answer="Post-order",
        explanation="Post-order processes left subtree, right subtree, then root.",
    ),
    QuestionBankItem(
        question_id="qb-tree-height",
        topic="Binary Trees & Traversal",
        source="tutorial",
        concept="Tree Properties",
        question="What is the maximum number of nodes in a binary tree of height h (root at height 0)?",
        options=["2^h - 1", "2^(h+1) - 1", "2h", "h^2"],
        correct_answer="2^(h+1) - 1",
        explanation="Each level doubles node count, so sum of geometric series gives 2^(h+1)-1.",
    ),
    QuestionBankItem(
        question_id="qb-dp-overlap",
        topic="Dynamic Programming",
        source="tutorial",
        concept="DP Fundamentals",
        question="Dynamic programming is most effective when a problem has:",
        options=[
            "Greedy-choice only",
            "Overlapping subproblems and optimal substructure",
            "No recursion",
            "Only sorted input",
        ],
        correct_answer="Overlapping subproblems and optimal substructure",
        explanation="DP reuses repeated subproblems while preserving optimal structure.",
    ),
    QuestionBankItem(
        question_id="qb-dp-tabulation",
        topic="Dynamic Programming",
        source="pyq",
        concept="DP Tabulation",
        question="In tabulation, what is usually computed first?",
        options=["Largest subproblem", "Random states", "Base cases", "Final answer only"],
        correct_answer="Base cases",
        explanation="Tabulation builds solutions bottom-up from base cases.",
    ),
    QuestionBankItem(
        question_id="qb-graph-bfs",
        topic="Graph Algorithms",
        source="sentinel",
        concept="Breadth-First Search",
        question="Which data structure is typically used in BFS?",
        options=["Stack", "Queue", "Priority Queue", "Set"],
        correct_answer="Queue",
        explanation="BFS explores nodes layer by layer via a FIFO queue.",
    ),
    QuestionBankItem(
        question_id="qb-graph-dijkstra",
        topic="Graph Algorithms",
        source="pyq",
        concept="Shortest Paths",
        question="Dijkstra's algorithm is invalid when a graph contains:",
        options=["Undirected edges", "Positive weights", "Negative edge weights", "Sparse connectivity"],
        correct_answer="Negative edge weights",
        explanation="Negative edges can invalidate the greedy relaxation ordering.",
    ),
]


class StateStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists() or self.file_path.read_text(encoding="utf-8").strip() == "":
            self.write(LearningState())

    def read(self) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            self._ensure_quiz_defaults(state)
            return state

    def write(self, state: LearningState) -> None:
        with self._lock:
            self._ensure_quiz_defaults(state)
            self._write_unlocked(state)

    def append_capture(
        self,
        event: CaptureEvent,
        new_gaps: list[KnowledgeGap],
        readiness_axes: ReadinessAxes,
    ) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            self._ensure_quiz_defaults(state)
            state.captures.append(event)
            state.gaps.extend(new_gaps)
            state.readiness_axes = readiness_axes
            self._write_unlocked(state)
            return state

    def append_quiz(
        self,
        quiz: QuizRecord,
        new_gaps: list[KnowledgeGap],
        readiness_axes: ReadinessAxes,
    ) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            self._ensure_quiz_defaults(state)
            state.quizzes.append(quiz)
            state.gaps.extend(new_gaps)
            state.readiness_axes = readiness_axes
            self._write_unlocked(state)
            return state

    def update_gap_status(self, gap_id: str, status: str) -> LearningState | None:
        with self._lock:
            state = self._read_unlocked()
            self._ensure_quiz_defaults(state)
            target = next((gap for gap in state.gaps if gap.gap_id == gap_id), None)
            if target is None:
                return None
            target.status = status
            self._write_unlocked(state)
            return state

    def _read_unlocked(self) -> LearningState:
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        state = LearningState.model_validate(payload)
        self._ensure_quiz_defaults(state)
        return state

    def _write_unlocked(self, state: LearningState) -> None:
        state.updated_at = utc_now_iso()
        tmp_path = self.file_path.with_suffix(".tmp")
        tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp_path, self.file_path)

    def _ensure_quiz_defaults(self, state: LearningState) -> None:
        if not state.question_bank:
            state.question_bank = [item.model_copy(deep=True) for item in DEFAULT_QUESTION_BANK]
        if state.quizzes is None:
            state.quizzes = []
