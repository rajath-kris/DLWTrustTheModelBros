from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .grounding import extract_supported_text
from .models import CourseDocument, LearningState, QuestionBankItem, TopicCatalogItem, utc_now_iso
from .openai_clients import _OpenAIChatClient, _extract_json_blob, _normalize_text


MAX_TOPICS_PER_DOCUMENT = 6
MAX_QUESTIONS_PER_TOPIC = 2
MAX_QUESTIONS_PER_UPLOAD = 12
TOPIC_EXCERPT_MAX_CHARS = 1800
FALLBACK_SENTENCE_MAX_CHARS = 180
LEGACY_GENERIC_SNIPPETS = (
    "a core principle of",
    "an unrelated history timeline",
    "a random syntax list without reasoning",
    "a hardware purchasing checklist",
    "when solving a problem on",
    "memorize an answer pattern without understanding",
    "skip assumptions and jump to a final answer",
)
FALLBACK_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "about",
    "when",
    "where",
    "which",
    "using",
    "their",
    "there",
    "these",
    "those",
    "should",
    "could",
    "would",
    "while",
    "what",
    "why",
    "how",
}


def _normalize_topic_name(value: str) -> str:
    compact = " ".join(value.strip().split()).lower()
    return re.sub(r"[^a-z0-9]+", "-", compact).strip("-")


def _topic_catalog_id(course_id: str, parent_topic_id: str, normalized_name: str) -> str:
    safe = normalized_name or "topic"
    return f"{course_id}:{parent_topic_id}:{safe}"[:120]


def dedupe_topics(topics: list[str], limit: int = MAX_TOPICS_PER_DOCUMENT) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in topics:
        compact = " ".join(raw.split()).strip(" -_:;,.")
        if len(compact) < 3:
            continue
        normalized = _normalize_topic_name(compact)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(compact[:96])
        if len(ordered) >= limit:
            break
    return ordered


def _fallback_topic_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem
    compact = " ".join(re.split(r"[_\-]+", stem)).strip()
    if len(compact) < 3:
        return None
    return compact[:80]


def extract_topic_candidates(text: str, filename: str, limit: int = MAX_TOPICS_PER_DOCUMENT) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        compact = " ".join(line.split()).strip()
        if not compact:
            continue
        heading_match = re.match(r"^(?:#{1,6}\s*|\d+[\).\s-]+)?([A-Za-z][A-Za-z0-9&/(),:+\-\s]{3,90})$", compact)
        if heading_match:
            candidates.append(heading_match.group(1))
            continue
        bullet_match = re.match(r"^(?:[-*\u2022]\s+)([A-Za-z][A-Za-z0-9&/(),:+\-\s]{3,90})$", compact)
        if bullet_match:
            candidates.append(bullet_match.group(1))

    if len(candidates) < 2:
        for sentence in re.split(r"[.;:\n]+", text):
            compact = " ".join(sentence.split()).strip()
            if 8 <= len(compact) <= 80 and len(compact.split()) <= 8:
                candidates.append(compact)

    fallback = _fallback_topic_from_filename(filename)
    if fallback:
        candidates.append(fallback)

    return dedupe_topics(candidates, limit=limit)


def _topic_excerpt(text: str, topic: str, max_chars: int = TOPIC_EXCERPT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    topic_tokens = [token for token in re.split(r"[^A-Za-z0-9]+", topic.lower()) if token]
    lower = text.lower()
    for token in topic_tokens:
        idx = lower.find(token)
        if idx >= 0:
            start = max(0, idx - int(max_chars * 0.25))
            end = min(len(text), start + max_chars)
            return text[start:end]
    return text[:max_chars]


def _normalize_options(raw_options: object) -> list[str]:
    if not isinstance(raw_options, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_options:
        value = _normalize_text(item, max_chars=180)
        if value is None:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _clean_sentence(value: str, *, max_chars: int = FALLBACK_SENTENCE_MAX_CHARS) -> str | None:
    compact = " ".join(value.replace("\u2022", " ").split()).strip(" -_:;,.")
    if len(compact) < 28 or len(compact.split()) < 5:
        return None
    if len(compact) <= max_chars:
        return compact
    trimmed = compact[: max_chars - 3].rstrip(" ,;:.")
    return f"{trimmed}..."


def _extract_excerpt_sentences(doc_excerpt: str, *, limit: int = 10) -> list[str]:
    text = doc_excerpt.replace("\r", "\n")
    raw_parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in raw_parts:
        sentence = _clean_sentence(raw)
        if sentence is None:
            continue
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(sentence)
        if len(ordered) >= limit:
            break
    return ordered


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in FALLBACK_STOPWORDS
    }


def _sentence_topic_score(sentence: str, *, topic_tokens: set[str]) -> float:
    if not sentence:
        return 0.0
    if not topic_tokens:
        return float(len(sentence))
    sentence_tokens = _tokenize(sentence)
    overlap = len(sentence_tokens & topic_tokens)
    return float(overlap) * 1000.0 + float(len(sentence_tokens))


def _select_fallback_sentences(topic: str, doc_excerpt: str) -> tuple[str, str]:
    sentences = _extract_excerpt_sentences(doc_excerpt)
    if not sentences:
        return (
            f"The uploaded material frames {topic} as a concept that must be reasoned through, not memorized.",
            f"The notes for {topic} emphasize using evidence from the problem statement before choosing a method.",
        )

    topic_tokens = _tokenize(topic)
    ranked = sorted(
        sentences,
        key=lambda sentence: _sentence_topic_score(sentence, topic_tokens=topic_tokens),
        reverse=True,
    )
    primary = ranked[0]
    secondary = next((candidate for candidate in ranked[1:] if candidate != primary), primary)
    return primary, secondary


def _material_aligned_options(correct: str, *, topic: str) -> list[str]:
    options = [
        correct,
        f"The material says {topic} should be solved by skipping assumptions and jumping to a final answer.",
        f"The material frames {topic} as unrelated to this topic and not worth analyzing.",
        f"The material prioritizes memorizing one pattern for {topic} without checking why it works.",
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for option in options:
        normalized = option.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(option)
    return deduped


def is_generic_generated_question(item: QuestionBankItem) -> bool:
    if not item.generated:
        return False
    haystack_parts = [item.question, item.concept, item.explanation or "", *item.options]
    haystack = " ".join(part.lower() for part in haystack_parts if part)
    return any(snippet in haystack for snippet in LEGACY_GENERIC_SNIPPETS)


def _fallback_questions(
    topic: str,
    *,
    doc_excerpt: str,
    course_id: str,
    parent_topic_id: str,
    doc_id: str | None,
    origin_material_id: str | None,
    origin_topic_id: str,
) -> list[QuestionBankItem]:
    concept = f"{topic} (uploaded material)"
    primary_sentence, secondary_sentence = _select_fallback_sentences(topic, doc_excerpt)
    if secondary_sentence == primary_sentence:
        secondary_sentence = (
            f"The uploaded material links {topic} to step-by-step reasoning based on the provided context."
        )
    q1_options = _material_aligned_options(primary_sentence, topic=topic)
    q2_options = _material_aligned_options(secondary_sentence, topic=topic)
    return [
        QuestionBankItem(
            topic=topic,
            source="tutorial",
            concept=concept,
            question=f"Based on the uploaded material for {topic}, which statement is explicitly supported?",
            options=q1_options,
            correct_answer=primary_sentence,
            explanation=f"This option quotes the material excerpt tied to {topic}.",
            course_id=course_id,
            topic_id=parent_topic_id,
            origin_doc_id=doc_id,
            origin_material_id=origin_material_id,
            origin_topic_id=origin_topic_id,
            generated=True,
        ),
        QuestionBankItem(
            topic=topic,
            source="tutorial",
            concept=concept,
            question=f"Which additional point also appears in the same uploaded material for {topic}?",
            options=q2_options,
            correct_answer=secondary_sentence,
            explanation=f"This choice is another sentence grounded in the same {topic} material.",
            course_id=course_id,
            topic_id=parent_topic_id,
            origin_doc_id=doc_id,
            origin_material_id=origin_material_id,
            origin_topic_id=origin_topic_id,
            generated=True,
        ),
    ]


def _parse_generated_questions(
    raw_content: str,
    *,
    topic: str,
    course_id: str,
    parent_topic_id: str,
    doc_id: str | None,
    origin_material_id: str | None,
    origin_topic_id: str,
    max_questions: int,
) -> list[QuestionBankItem]:
    blob = _extract_json_blob(raw_content)
    if not isinstance(blob, dict):
        return []
    raw_questions = blob.get("questions")
    if not isinstance(raw_questions, list):
        return []

    parsed: list[QuestionBankItem] = []
    seen_questions: set[str] = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question = _normalize_text(item.get("question"), max_chars=320)
        if question is None:
            continue
        question_key = question.lower()
        if question_key in seen_questions:
            continue
        seen_questions.add(question_key)

        concept = _normalize_text(item.get("concept"), max_chars=140) or topic
        options = _normalize_options(item.get("options"))
        if len(options) < 2:
            continue
        correct_answer = _normalize_text(item.get("correct_answer"), max_chars=180)
        if correct_answer is None:
            continue
        option_lookup = {opt.lower(): opt for opt in options}
        matched_correct = option_lookup.get(correct_answer.lower())
        if matched_correct is None:
            continue
        explanation = _normalize_text(item.get("explanation"), max_chars=320)

        parsed.append(
            QuestionBankItem(
                topic=topic,
                source="tutorial",
                concept=concept,
                question=question,
                options=options,
                correct_answer=matched_correct,
                explanation=explanation,
                course_id=course_id,
                topic_id=parent_topic_id,
                origin_doc_id=doc_id,
                origin_material_id=origin_material_id,
                origin_topic_id=origin_topic_id,
                generated=True,
            )
        )
        if len(parsed) >= max_questions:
            break

    return parsed


@dataclass
class QuizSeedResult:
    topics_added: int
    questions_added: int
    warnings: list[str]


class QuizSeeder:
    def __init__(self, settings: Settings) -> None:
        self._chat_client = _OpenAIChatClient(settings)

    def seed_document(
        self,
        *,
        state: LearningState,
        document: CourseDocument,
        file_path: Path,
        replace_existing_doc_questions: bool = True,
        allow_llm: bool = True,
    ) -> QuizSeedResult:
        warnings: list[str] = []
        extracted_text, parse_warning = extract_supported_text(file_path)
        if parse_warning and parse_warning.startswith("Unsupported document type for grounding"):
            warnings.append(parse_warning)
            return QuizSeedResult(topics_added=0, questions_added=0, warnings=warnings)
        if parse_warning and extracted_text == "No text detected.":
            warnings.append(parse_warning)
            return QuizSeedResult(topics_added=0, questions_added=0, warnings=warnings)

        text = " ".join(extracted_text.split())
        if not text:
            warnings.append("No extractable text found in document.")
            return QuizSeedResult(topics_added=0, questions_added=0, warnings=warnings)

        if replace_existing_doc_questions:
            state.question_bank = [
                item
                for item in state.question_bank
                if not (item.generated and item.origin_doc_id == document.doc_id)
            ]

        topic_candidates = extract_topic_candidates(extracted_text, document.name)
        if not topic_candidates:
            topic_candidates = dedupe_topics([document.name], limit=1)

        now = utc_now_iso()
        topics_added = 0
        selected_topics: list[TopicCatalogItem] = []
        for topic_name in topic_candidates:
            normalized_name = _normalize_topic_name(topic_name)
            if not normalized_name:
                continue
            existing = next(
                (
                    item
                    for item in state.topics
                    if item.course_id == document.course_id
                    and item.parent_topic_id == document.topic_id
                    and item.normalized_name == normalized_name
                ),
                None,
            )
            if existing is None:
                topic = TopicCatalogItem(
                    topic_id=_topic_catalog_id(document.course_id, document.topic_id, normalized_name),
                    course_id=document.course_id,
                    parent_topic_id=document.topic_id,
                    name=topic_name,
                    normalized_name=normalized_name,
                    source_doc_ids=[document.doc_id],
                    created_at=now,
                    updated_at=now,
                )
                state.topics.append(topic)
                selected_topics.append(topic)
                topics_added += 1
            else:
                if document.doc_id not in existing.source_doc_ids:
                    existing.source_doc_ids.append(document.doc_id)
                existing.updated_at = now
                selected_topics.append(existing)

        questions_added = 0
        total_budget = MAX_QUESTIONS_PER_UPLOAD
        for topic in selected_topics:
            if total_budget <= 0:
                break
            excerpt = _topic_excerpt(extracted_text, topic.name)
            per_topic_budget = min(MAX_QUESTIONS_PER_TOPIC, total_budget)
            generated_questions = self._generate_seed_questions(
                topic=topic.name,
                origin_topic_id=topic.topic_id,
                doc_excerpt=excerpt,
                course_id=document.course_id,
                parent_topic_id=document.topic_id,
                doc_id=document.doc_id,
                origin_material_id=None,
                max_questions=per_topic_budget,
                allow_llm=allow_llm,
            )
            if not generated_questions:
                warnings.append(f"No valid generated questions for topic '{topic.name}'.")
                continue
            state.question_bank.extend(generated_questions)
            questions_added += len(generated_questions)
            total_budget -= len(generated_questions)

        return QuizSeedResult(topics_added=topics_added, questions_added=questions_added, warnings=warnings)

    def seed_material(
        self,
        *,
        state: LearningState,
        course_id: str,
        topic_id: str,
        topic_name: str,
        material_id: str,
        material_name: str,
        extracted_text: str,
        replace_existing_material_questions: bool = True,
        allow_llm: bool = True,
    ) -> QuizSeedResult:
        warnings: list[str] = []
        text = " ".join((extracted_text or "").split())
        if not text:
            warnings.append("No extractable text found in topic material.")
            return QuizSeedResult(topics_added=0, questions_added=0, warnings=warnings)

        if replace_existing_material_questions:
            state.question_bank = [
                item
                for item in state.question_bank
                if not (item.generated and item.origin_material_id == material_id)
            ]

        topic_candidates = extract_topic_candidates(extracted_text, material_name)
        if topic_name and topic_name not in topic_candidates:
            topic_candidates.insert(0, topic_name)
        topic_candidates = dedupe_topics(topic_candidates or [material_name], limit=MAX_TOPICS_PER_DOCUMENT)

        questions_added = 0
        total_budget = MAX_QUESTIONS_PER_UPLOAD
        for candidate_topic_name in topic_candidates:
            if total_budget <= 0:
                break
            excerpt = _topic_excerpt(extracted_text, candidate_topic_name)
            per_topic_budget = min(MAX_QUESTIONS_PER_TOPIC, total_budget)
            generated_questions = self._generate_seed_questions(
                topic=candidate_topic_name,
                origin_topic_id=topic_id,
                doc_excerpt=excerpt,
                course_id=course_id,
                parent_topic_id=topic_id,
                doc_id=None,
                origin_material_id=material_id,
                max_questions=per_topic_budget,
                allow_llm=allow_llm,
            )
            if not generated_questions:
                warnings.append(f"No valid generated questions for topic '{candidate_topic_name}'.")
                continue
            state.question_bank.extend(generated_questions)
            questions_added += len(generated_questions)
            total_budget -= len(generated_questions)

        return QuizSeedResult(topics_added=0, questions_added=questions_added, warnings=warnings)

    def _generate_seed_questions(
        self,
        *,
        topic: str,
        origin_topic_id: str,
        doc_excerpt: str,
        course_id: str,
        parent_topic_id: str,
        doc_id: str | None,
        origin_material_id: str | None,
        max_questions: int,
        allow_llm: bool,
    ) -> list[QuestionBankItem]:
        fallback = _fallback_questions(
            topic,
            doc_excerpt=doc_excerpt,
            course_id=course_id,
            parent_topic_id=parent_topic_id,
            doc_id=doc_id,
            origin_material_id=origin_material_id,
            origin_topic_id=origin_topic_id,
        )[:max_questions]
        if not allow_llm or not self._chat_client.configured:
            return fallback

        system_prompt = (
            "You generate MCQ quiz items from study notes. "
            "Return strict JSON only with shape: "
            '{"questions":[{"concept":"...","question":"...","options":["..."],"correct_answer":"...","explanation":"..."}]}. '
            "Do not include markdown. Keep questions concise and concept-focused. "
            "Every question and correct answer must be directly supported by the provided excerpt. "
            "Reuse specific terms from the excerpt and avoid generic placeholders."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Course ID: {course_id}\n"
            f"Topic ID: {parent_topic_id}\n"
            f"Topic tag (must align): {origin_topic_id}\n"
            f"Generate up to {max_questions} questions from this excerpt:\n"
            f"{doc_excerpt[:TOPIC_EXCERPT_MAX_CHARS]}"
        )
        raw = self._chat_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=600,
        )
        if raw is None:
            return fallback

        parsed = _parse_generated_questions(
            raw,
            topic=topic,
            course_id=course_id,
            parent_topic_id=parent_topic_id,
            doc_id=doc_id,
            origin_material_id=origin_material_id,
            origin_topic_id=origin_topic_id,
            max_questions=max_questions,
        )
        return parsed or fallback
