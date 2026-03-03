#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_APP_ROOT = REPO_ROOT / "services" / "bridge-api"
if str(BRIDGE_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_APP_ROOT))

from app.config import settings  # noqa: E402
from app.models import CourseDocument, CourseSummary, QuestionBankItem, TopicCatalogItem, utc_now_iso  # noqa: E402
from app.openai_clients import OpenAIVisionClient  # noqa: E402
from app.readiness import calculate_readiness  # noqa: E402
from app.state_store import StateStore  # noqa: E402
from app.topic_store import TopicStore  # noqa: E402


@dataclass(frozen=True)
class SeedQuestion:
    concept: str
    question: str
    options: list[str]
    answer: str
    explanation: str
    source: str = "tutorial"


@dataclass(frozen=True)
class SeedTopic:
    topic_id: str
    topic_name: str
    material_name: str
    material_filename: str
    material_text: str
    questions: list[SeedQuestion]


@dataclass(frozen=True)
class SeedCourse:
    course_id: str
    course_name: str
    topics: list[SeedTopic]


SEED_COURSES: list[SeedCourse] = [
    SeedCourse(
        course_id="demo-ds",
        course_name="Demo Data Structures",
        topics=[
            SeedTopic(
                topic_id="demo-ds-arrays-hashing",
                topic_name="Arrays and Hashing",
                material_name="Arrays and Hashing Quick Notes",
                material_filename="arrays_hashing_notes.txt",
                material_text=(
                    "Arrays store elements in contiguous memory and allow O(1) indexed access.\n"
                    "Hash tables map keys to buckets via a hash function and typically support O(1) average lookup.\n"
                    "Collision handling can use chaining or open addressing.\n"
                    "Load factor affects performance and rehashing policy.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="Array access complexity",
                        question="What is the average time complexity for reading array[i] in a dynamic array?",
                        options=["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                        answer="O(1)",
                        explanation="Arrays provide direct indexed access using base + offset arithmetic.",
                    ),
                    SeedQuestion(
                        concept="Hash table collisions",
                        question="Which is a standard strategy to resolve collisions in a hash table?",
                        options=["Chaining", "Merge sort", "Recursion depth limiting", "Backtracking"],
                        answer="Chaining",
                        explanation="Chaining stores multiple elements in a bucket, usually via a linked structure.",
                    ),
                ],
            ),
            SeedTopic(
                topic_id="demo-ds-linked-lists",
                topic_name="Linked Lists",
                material_name="Linked Lists Core Concepts",
                material_filename="linked_lists_core.txt",
                material_text=(
                    "A singly linked list stores nodes with data and next pointers.\n"
                    "Insertion at head is O(1).\n"
                    "Searching for a value is O(n) in the worst case.\n"
                    "Doubly linked lists add prev pointers to support O(1) backward navigation.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="Linked list insertion",
                        question="What is the time complexity of inserting a node at the head of a singly linked list?",
                        options=["O(1)", "O(log n)", "O(n)", "O(n^2)"],
                        answer="O(1)",
                        explanation="Only pointer reassignment is needed for head insertion.",
                    ),
                    SeedQuestion(
                        concept="Linked list search",
                        question="Why is searching for an element in a linked list typically O(n)?",
                        options=[
                            "Nodes must be traversed sequentially",
                            "Pointer arithmetic is expensive",
                            "Hashing is required",
                            "Linked lists are always sorted",
                        ],
                        answer="Nodes must be traversed sequentially",
                        explanation="There is no direct index access; traversal is node by node.",
                    ),
                ],
            ),
            SeedTopic(
                topic_id="demo-ds-stacks-queues",
                topic_name="Stacks and Queues",
                material_name="Stacks and Queues Fundamentals",
                material_filename="stacks_queues_fundamentals.txt",
                material_text=(
                    "A stack follows LIFO order with push and pop operations.\n"
                    "A queue follows FIFO order with enqueue and dequeue operations.\n"
                    "Stacks are used in function call management and expression evaluation.\n"
                    "Queues are used in BFS and scheduling systems.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="Stack behavior",
                        question="Which ordering rule does a stack follow?",
                        options=["LIFO", "FIFO", "Sorted ascending", "Randomized"],
                        answer="LIFO",
                        explanation="A stack pops the most recently pushed element first.",
                    ),
                    SeedQuestion(
                        concept="Queue operations",
                        question="Which operation removes an element from a queue?",
                        options=["Dequeue", "Push", "Pop", "Peek"],
                        answer="Dequeue",
                        explanation="Queue removal happens from the front via dequeue.",
                    ),
                ],
            ),
        ],
    ),
    SeedCourse(
        course_id="eee",
        course_name="EEE Fundamentals",
        topics=[
            SeedTopic(
                topic_id="eee-circuit-laws",
                topic_name="Circuit Laws",
                material_name="KCL and KVL Notes",
                material_filename="kcl_kvl_notes.txt",
                material_text=(
                    "Kirchhoff's Current Law (KCL): algebraic sum of currents at a node is zero.\n"
                    "Kirchhoff's Voltage Law (KVL): algebraic sum of voltages around a loop is zero.\n"
                    "Ohm's Law: V = I * R.\n"
                    "Nodal and mesh analysis apply these laws systematically.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="KCL",
                        question="What does Kirchhoff's Current Law state for a circuit node?",
                        options=[
                            "Sum of entering and leaving currents is zero",
                            "Voltage drop equals current times resistance",
                            "Power in equals power out for all loads",
                            "Current is constant in all branches",
                        ],
                        answer="Sum of entering and leaving currents is zero",
                        explanation="KCL enforces conservation of charge at a node.",
                    ),
                    SeedQuestion(
                        concept="Ohm's law",
                        question="If current is 2 A through a 5 ohm resistor, what is the voltage across it?",
                        options=["10 V", "2.5 V", "0.4 V", "7 V"],
                        answer="10 V",
                        explanation="V = I * R = 2 * 5 = 10 volts.",
                    ),
                ],
            ),
            SeedTopic(
                topic_id="eee-ac-analysis",
                topic_name="AC Analysis",
                material_name="Phasors and Impedance",
                material_filename="phasors_impedance.txt",
                material_text=(
                    "In AC steady state, sinusoidal signals can be represented as phasors.\n"
                    "Impedance generalizes resistance: Z_R = R, Z_L = j*omega*L, Z_C = 1/(j*omega*C).\n"
                    "Series impedances add directly.\n"
                    "Power factor indicates phase difference between voltage and current.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="Inductor impedance",
                        question="What is the impedance of an ideal inductor in phasor form?",
                        options=["jωL", "1/(jωC)", "R", "ωL"],
                        answer="jωL",
                        explanation="Inductive reactance is represented as jωL.",
                    ),
                    SeedQuestion(
                        concept="Series impedances",
                        question="How are impedances combined in a series AC circuit?",
                        options=[
                            "They are added directly",
                            "Their reciprocals are added",
                            "The largest impedance dominates only",
                            "They are multiplied and divided by frequency",
                        ],
                        answer="They are added directly",
                        explanation="Series elements carry the same current, so impedances sum.",
                    ),
                ],
            ),
            SeedTopic(
                topic_id="eee-semiconductor-basics",
                topic_name="Semiconductor Basics",
                material_name="PN Junction Essentials",
                material_filename="pn_junction_essentials.txt",
                material_text=(
                    "A PN junction diode allows significant current in forward bias and very small current in reverse bias.\n"
                    "Forward voltage for silicon diodes is approximately 0.7 V in many practical models.\n"
                    "Reverse breakdown occurs when reverse voltage exceeds a device-specific threshold.\n"
                    "Rectifier circuits use diode conduction directionality.\n"
                ),
                questions=[
                    SeedQuestion(
                        concept="Diode biasing",
                        question="In which bias condition does a PN junction diode typically conduct strongly?",
                        options=["Forward bias", "Reverse bias", "Zero bias only", "Breakdown only"],
                        answer="Forward bias",
                        explanation="Forward bias lowers the barrier and allows substantial carrier flow.",
                    ),
                    SeedQuestion(
                        concept="Silicon diode drop",
                        question="What is a common approximate forward voltage drop of a silicon diode?",
                        options=["0.7 V", "5 V", "0.07 V", "2.2 V"],
                        answer="0.7 V",
                        explanation="0.7 V is a widely used engineering approximation for silicon diodes.",
                    ),
                ],
            ),
        ],
    ),
]


def _sanitize_filename(raw_name: str) -> str:
    base = Path(raw_name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return cleaned[:180] or "upload.bin"


def _deterministic_uuid(seed: str) -> str:
    return str(uuid5(NAMESPACE_DNS, seed))


def _ensure_course(state, course_id: str, course_name: str) -> bool:
    normalized = course_id.strip().lower()
    for row in state.courses:
        if row.course_id.strip().lower() == normalized:
            row.course_name = course_name
            return False
    state.courses.append(CourseSummary(course_id=course_id, course_name=course_name))
    return True


def _ensure_state_topic(state, *, topic_id: str, topic_name: str, course_id: str, source_doc_id: str) -> bool:
    normalized_topic = topic_id.strip().lower()
    normalized_course = course_id.strip().lower()
    for row in state.topics:
        if row.topic_id.strip().lower() != normalized_topic:
            continue
        row.course_id = course_id
        row.parent_topic_id = topic_id
        row.name = topic_name
        row.normalized_name = " ".join(topic_name.lower().split())
        if source_doc_id not in row.source_doc_ids:
            row.source_doc_ids.append(source_doc_id)
        row.updated_at = utc_now_iso()
        return False

    state.topics.append(
        TopicCatalogItem(
            topic_id=topic_id,
            course_id=course_id,
            parent_topic_id=topic_id,
            name=topic_name,
            normalized_name=" ".join(topic_name.lower().split()),
            source_doc_ids=[source_doc_id],
        )
    )
    return True


def _ensure_document(state, *, course_id: str, topic_id: str, topic_name: str, filename: str, body_text: str) -> bool:
    safe_filename = _sanitize_filename(filename)
    doc_id = _deterministic_uuid(f"seed-doc:{course_id}:{topic_id}:{safe_filename}")
    stored_name = f"{doc_id}_{safe_filename}"
    folder = settings.documents_dir / course_id
    folder.mkdir(parents=True, exist_ok=True)
    target_path = folder / stored_name
    target_path.write_text(body_text, encoding="utf-8")
    file_url = f"http://{settings.bridge_host}:{settings.bridge_port}/course-documents/{course_id}/{stored_name}"

    for row in state.documents:
        if row.doc_id != doc_id:
            continue
        row.course_id = course_id
        row.topic_id = topic_id
        row.name = topic_name
        row.size_bytes = target_path.stat().st_size
        row.type = "txt"
        row.file_url = file_url
        row.is_anchor = False
        return False

    state.documents.append(
        CourseDocument(
            doc_id=doc_id,
            course_id=course_id,
            topic_id=topic_id,
            name=topic_name,
            size_bytes=target_path.stat().st_size,
            type="txt",
            file_url=file_url,
            is_anchor=False,
        )
    )
    return True


def _ensure_topic_material(topic_store: TopicStore, *, topic_id: str, material_name: str, filename: str, body_text: str) -> bool:
    safe_filename = _sanitize_filename(filename)
    existing = topic_store.list_materials(topic_id)
    for row in existing:
        if Path(row.original_filename).name.lower() == safe_filename.lower():
            return False
    topic_store.add_material(
        topic_id=topic_id,
        material_name=material_name,
        material_type="txt",
        original_filename=safe_filename,
        file_bytes=body_text.encode("utf-8"),
    )
    return True


def _ensure_question(
    state,
    *,
    course_id: str,
    topic_id: str,
    topic_name: str,
    seed_question: SeedQuestion,
    ordinal: int,
) -> bool:
    question_id = _deterministic_uuid(f"seed-q:{course_id}:{topic_id}:{ordinal}:{seed_question.question}")
    for row in state.question_bank:
        if row.question_id == question_id:
            row.course_id = course_id
            row.topic_id = topic_id
            row.origin_topic_id = topic_id
            row.topic = topic_name
            row.concept = seed_question.concept
            row.source = seed_question.source
            row.question = seed_question.question
            row.options = list(seed_question.options)
            row.correct_answer = seed_question.answer
            row.explanation = seed_question.explanation
            row.generated = True
            return False

    state.question_bank.append(
        QuestionBankItem(
            question_id=question_id,
            topic=topic_name,
            source=seed_question.source,
            concept=seed_question.concept,
            question=seed_question.question,
            options=list(seed_question.options),
            correct_answer=seed_question.answer,
            explanation=seed_question.explanation,
            course_id=course_id,
            topic_id=topic_id,
            origin_topic_id=topic_id,
            generated=True,
        )
    )
    return True


def main() -> int:
    state_store = StateStore(settings.state_file)
    vision_client = OpenAIVisionClient(settings)
    topics = TopicStore(settings.topics_dir, vision_client)
    state = state_store.read()

    created_courses = 0
    upserted_topics = 0
    created_documents = 0
    created_materials = 0
    created_questions = 0

    for seed_course in SEED_COURSES:
        if _ensure_course(state, seed_course.course_id, seed_course.course_name):
            created_courses += 1

        for topic in seed_course.topics:
            topics.upsert_topic(topic.topic_id, topic.topic_name, seed_course.course_id)
            upserted_topics += 1

            if _ensure_document(
                state,
                course_id=seed_course.course_id,
                topic_id=topic.topic_id,
                topic_name=topic.material_name,
                filename=topic.material_filename,
                body_text=topic.material_text,
            ):
                created_documents += 1

            if _ensure_topic_material(
                topics,
                topic_id=topic.topic_id,
                material_name=topic.material_name,
                filename=topic.material_filename,
                body_text=topic.material_text,
            ):
                created_materials += 1

            source_doc_id = _deterministic_uuid(
                f"seed-doc:{seed_course.course_id}:{topic.topic_id}:{_sanitize_filename(topic.material_filename)}"
            )
            _ensure_state_topic(
                state,
                topic_id=topic.topic_id,
                topic_name=topic.topic_name,
                course_id=seed_course.course_id,
                source_doc_id=source_doc_id,
            )

            for index, question in enumerate(topic.questions, start=1):
                if _ensure_question(
                    state,
                    course_id=seed_course.course_id,
                    topic_id=topic.topic_id,
                    topic_name=topic.topic_name,
                    seed_question=question,
                    ordinal=index,
                ):
                    created_questions += 1

    state.readiness_axes = calculate_readiness(state.gaps)
    state_store.write(state)

    summary = {
        "ok": True,
        "state_file": str(settings.state_file),
        "topics_index": str(settings.topics_dir / "index.json"),
        "created_courses": created_courses,
        "upserted_topics": upserted_topics,
        "created_documents": created_documents,
        "created_materials": created_materials,
        "created_questions": created_questions,
        "total_courses": len(state.courses),
        "total_topics": len(state.topics),
        "total_documents": len(state.documents),
        "total_question_bank": len(state.question_bank),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
