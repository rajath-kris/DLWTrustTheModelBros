from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from uuid import uuid4

from .models import (
    CaptureEvent,
    KnowledgeGap,
    LearningState,
    QuestionBankItem,
    QuizRecord,
    ReadinessAxes,
    TopicMastery,
    utc_now_iso,
)


DEFAULT_TOPICS: list[TopicMastery] = [
    TopicMastery(topic_id="trees", name="Binary Trees & Traversal", mastery_score=0.62),
    TopicMastery(topic_id="dp", name="Dynamic Programming", mastery_score=0.58),
    TopicMastery(topic_id="graphs", name="Graph Algorithms", mastery_score=0.66),
    TopicMastery(topic_id="sorting", name="Sorting & Searching", mastery_score=0.72),
]

DEFAULT_QUESTION_BANK: list[QuestionBankItem] = [
    QuestionBankItem(
        id="q-tree-postorder",
        topic="Binary Trees & Traversal",
        question_text="Which traversal visits the root node last?",
        options=["In-order", "Pre-order", "Post-order", "Level-order"],
        correct_answer="Post-order",
        source="PYQ_2025_Q3",
        source_type="pyq",
        concept="Tree Traversals",
    ),
    QuestionBankItem(
        id="q-tree-height",
        topic="Binary Trees & Traversal",
        question_text="What is the maximum number of nodes in a binary tree of height h (root at height 0)?",
        options=["2^h - 1", "2^(h+1) - 1", "2h", "h^2"],
        correct_answer="2^(h+1) - 1",
        source="CS2040_Tutorial_3_Q1",
        source_type="tutorial",
        concept="Tree Properties",
    ),
    QuestionBankItem(
        id="q-dp-overlap",
        topic="Dynamic Programming",
        question_text="Dynamic programming is most effective when a problem has:",
        options=["Greedy-choice only", "Overlapping subproblems and optimal substructure", "No recursion", "Only sorted input"],
        correct_answer="Overlapping subproblems and optimal substructure",
        source="CS2040_Tutorial_6_Q2",
        source_type="tutorial",
        concept="DP Fundamentals",
    ),
    QuestionBankItem(
        id="q-dp-transition",
        topic="Dynamic Programming",
        question_text="In tabulation, what is usually computed first?",
        options=["Largest subproblem", "Random states", "Base cases", "Final answer only"],
        correct_answer="Base cases",
        source="PYQ_2024_Q7",
        source_type="pyq",
        concept="DP Tabulation",
    ),
    QuestionBankItem(
        id="q-graph-bfs",
        topic="Graph Algorithms",
        question_text="Which data structure is typically used in BFS?",
        options=["Stack", "Queue", "Priority Queue", "Set"],
        correct_answer="Queue",
        source="SENTINEL_CAPTURE_12",
        source_type="sentinel",
        captured_from_sentinel=True,
        concept="BFS",
    ),
    QuestionBankItem(
        id="q-graph-dijkstra",
        topic="Graph Algorithms",
        question_text="Dijkstra's algorithm fails with:",
        options=["Undirected edges", "Positive weights", "Negative edge weights", "Sparse graphs"],
        correct_answer="Negative edge weights",
        source="PYQ_2023_Q5",
        source_type="pyq",
        concept="Shortest Paths",
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
            return self._read_unlocked()

    def write(self, state: LearningState) -> None:
        with self._lock:
            self._write_unlocked(state)

    def append_capture(
        self,
        event: CaptureEvent,
        new_gaps: list[KnowledgeGap],
        readiness_axes: ReadinessAxes,
    ) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            state.captures.append(event)
            state.gaps.extend(new_gaps)
            state.readiness_axes = readiness_axes
            self._ensure_quiz_defaults(state)
            self._write_unlocked(state)
            return state

    def append_quiz(
        self,
        quiz: QuizRecord,
        updated_topics: list[TopicMastery],
        new_gaps: list[KnowledgeGap],
        readiness_axes: ReadinessAxes,
    ) -> LearningState:
        with self._lock:
            state = self._read_unlocked()
            self._ensure_quiz_defaults(state)
            state.quizzes.append(quiz)
            state.gaps.extend(new_gaps)
            self._upsert_topics(state, updated_topics)
            state.readiness_axes = readiness_axes
            self._write_unlocked(state)
            return state

    def update_gap_status(self, gap_id: str, status: str) -> LearningState | None:
        with self._lock:
            state = self._read_unlocked()
            target = next((gap for gap in state.gaps if gap.gap_id == gap_id), None)
            if target is None:
                return None
            target.status = status
            self._ensure_quiz_defaults(state)
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
        if not state.topics:
            state.topics = [item.model_copy(deep=True) for item in DEFAULT_TOPICS]
        if not state.question_bank:
            state.question_bank = [item.model_copy(deep=True) for item in DEFAULT_QUESTION_BANK]
        if state.quizzes is None:
            state.quizzes = []

    def _upsert_topics(self, state: LearningState, topics: list[TopicMastery]) -> None:
        index_by_id = {topic.topic_id: idx for idx, topic in enumerate(state.topics)}
        for topic in topics:
            existing_idx = index_by_id.get(topic.topic_id)
            if existing_idx is not None:
                state.topics[existing_idx] = topic
                continue
            new_topic = topic.model_copy(deep=True)
            if not new_topic.topic_id:
                new_topic.topic_id = f"topic-{uuid4()}"
            state.topics.append(new_topic)
