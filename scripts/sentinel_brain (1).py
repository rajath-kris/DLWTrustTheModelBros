import base64
import io
import json
import os
import re
import time
from datetime import datetime
from typing import Any

import fitz  # pymupdf
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

STATE_FILE = "state.json"
NOTES_FILE = "lecture_notes.pdf"
MAX_REPLY_WORDS = 90
CORE_FOCUS_TOKENS = {
    "question",
    "problem",
    "topic",
    "concept",
    "module",
    "chapter",
    "tutorial",
    "lecture",
    "note",
    "notes",
    "diagram",
    "figure",
    "equation",
    "example",
    "step",
    "hint",
    "screenshot",
    "assignment",
    "exercise",
    "exam",
}
OFFTOPIC_HINT_TOKENS = {
    "weather",
    "rain",
    "raining",
    "restaurant",
    "movie",
    "song",
    "football",
    "nba",
    "cricket",
    "holiday",
    "flight",
    "travel",
    "dating",
    "game",
    "netflix",
}
GUIDANCE_HINT_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in [
        r"\b(confused|unclear|unsure|not sure)\b",
        r"\b(stuck|lost|no idea)\b",
        r"\b(i (?:do not|don't) know)\b",
        r"\b(i (?:might be|am) wrong)\b",
        r"\b(help|hint)\b",
    ]
]
COMPLETION_PATTERNS = [
    r"\bi (have|ve)?\s*(solved|done|finished)\b",
    r"\bi (got|get) it\b",
    r"\bi understand now\b",
    r"\bim done\b",
    r"\bthanks\b",
    r"\bthank you\b",
    r"\bthat (is|was) enough\b",
]
TOPIC_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "your",
    "about",
    "what",
    "which",
    "where",
    "when",
    "why",
    "how",
    "are",
    "was",
    "were",
    "is",
    "am",
    "be",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "it",
    "im",
    "ive",
    "you",
    "bro",
    "btw",
    "today",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _tokenize(text: str) -> list[str]:
    tokens = [w for w in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(w) > 1]
    normalized: list[str] = []
    for token in tokens:
        if token.endswith("s") and len(token) > 3:
            token = token[:-1]
        normalized.append(token)
    return normalized


def _parse_bridge_capture_payload(raw_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in (raw_text or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = " ".join(key.strip().lower().split())
        parsed[normalized_key] = " ".join(value.strip().split())
    return parsed


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 140) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        chunk = text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks or [text]


def _safe_json_load(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def load_lecture_notes(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        return "No lecture notes uploaded yet."

    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    return text[:24000]


def load_state(state_file: str = STATE_FILE) -> dict[str, Any]:
    default_state = {
        "gaps": {},
        "sessions": [],
        "meta": {
            "running_summary": "",
            "last_summary_turn": 0,
        },
    }
    if not os.path.exists(state_file):
        return default_state

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return default_state
    data.setdefault("gaps", {})
    data.setdefault("sessions", [])
    data.setdefault("meta", {})
    data["meta"].setdefault("running_summary", "")
    data["meta"].setdefault("last_summary_turn", 0)
    return data


def save_state(state: dict[str, Any], state_file: str = STATE_FILE) -> None:
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def encode_image(pil_image) -> str:
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class SentinelSession:
    def __init__(
        self,
        notes_path: str = NOTES_FILE,
        state_file: str = STATE_FILE,
        model: str | None = None,
        aux_model: str | None = None,
    ):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Put it in a .env file.")

        self.client = OpenAI(api_key=api_key)
        self.model = model or os.getenv("SENTINEL_TUTOR_MODEL", "gpt-4o")
        self.aux_model = aux_model or os.getenv("SENTINEL_AUX_MODEL", "gpt-4o-mini")
        self.state_file = state_file
        self.state = load_state(state_file)
        self.lecture_notes = load_lecture_notes(notes_path)
        self.note_chunks = _chunk_text(self.lecture_notes, chunk_size=1200, overlap=140)
        self.current_topic = None
        self.running_summary = self.state["meta"].get("running_summary", "")
        self.max_tail_messages = 8
        self.summary_every_turns = 6

        # Keep only user/assistant turns here. The system prompt is rebuilt each reply.
        self.conversation_history: list[dict[str, Any]] = []

    def _call_chat_with_retry(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        retries: int = 5,
    ):
        delay = 8
        last_error = None
        for _ in range(retries):
            try:
                return self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except RateLimitError as exc:
                last_error = exc
                time.sleep(delay)
                delay = min(30, int(delay * 1.5))
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected chat completion failure without error.")

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            return " ".join(text_parts).strip()
        return ""

    def _select_note_context(self, query: str, k: int = 3) -> str:
        if not self.note_chunks:
            return "No lecture notes uploaded yet."
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return "\n\n".join(self.note_chunks[:k])

        scored: list[tuple[int, str]] = []
        for chunk in self.note_chunks:
            chunk_tokens = set(_tokenize(chunk))
            score = len(query_tokens & chunk_tokens)
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [chunk for score, chunk in scored[:k] if score > 0]
        if not top:
            top = self.note_chunks[:k]
        return "\n\n---\n\n".join(top)

    def _summarize_gap_snapshot(self) -> str:
        gaps = self.state.get("gaps", {})
        if not gaps:
            return "None yet."

        ranked = sorted(
            gaps.items(),
            key=lambda item: (item[1].get("mastery", 0.5), -item[1].get("attempts", 0)),
        )[:6]
        compact = {}
        for topic, data in ranked:
            compact[topic] = {
                "mastery": round(float(data.get("mastery", 0.5)), 3),
                "attempts": int(data.get("attempts", 0)),
                "confused_about": data.get("confused_about", ""),
                "knows": data.get("knows", [])[:4],
            }
        return json.dumps(compact, indent=2)

    def _build_topic_lexicon(self) -> set[str]:
        lexicon = set(CORE_FOCUS_TOKENS)
        if self.current_topic:
            lexicon.update(_tokenize(self.current_topic))
        for topic in list(self.state.get("gaps", {}).keys())[:8]:
            lexicon.update(_tokenize(topic))
        for item in self.state.get("sessions", [])[-8:]:
            if item.get("reply_mode") in {"diagnostic", "socratic"}:
                lexicon.update(_tokenize(str(item.get("user_text", ""))))
        return lexicon

    def _is_completion_intent(self, user_text: str) -> bool:
        lowered = user_text.lower().strip()
        if not lowered:
            return False
        if any(pattern.search(lowered) for pattern in GUIDANCE_HINT_PATTERNS):
            return False
        for pattern in COMPLETION_PATTERNS:
            if re.search(pattern, lowered):
                return True
        return False

    def _is_off_topic(self, user_text: str, screenshot_pil=None) -> bool:
        if screenshot_pil is not None:
            return False
        text = user_text.strip().lower()
        if not text:
            return False
        if len(self.conversation_history) < 2:
            return False
        if re.search(r"\b(stuck|confused|question|problem|topic|equation|notes|tutorial)\b", text):
            return False

        tokens = set(_tokenize(text))
        content_tokens = {t for t in tokens if t not in TOPIC_STOPWORDS}
        if not content_tokens:
            return False
        if content_tokens & OFFTOPIC_HINT_TOKENS:
            return True

        lexicon = self._build_topic_lexicon()
        content_lexicon = {t for t in lexicon if t not in TOPIC_STOPWORDS}
        overlap = len(content_tokens & content_lexicon)
        # treat as off-topic if there is zero topical overlap for non-trivial prompts
        if overlap == 0 and len(content_tokens) >= 2:
            return True
        return False

    def _offtopic_nudge_reply(self) -> str:
        focus = ""
        if self.current_topic and self.current_topic in self.state.get("gaps", {}):
            focus = self.state["gaps"][self.current_topic].get("confused_about", "")
        if focus:
            return (
                f"Good question, and let's reconnect to this notes/tutorial task: "
                f"are you currently stuck on {focus} in this current question?"
            )
        return (
            "Thanks for sharing that, and let's reconnect to this notes/tutorial task: "
            "which step is blocking you right now in this question?"
        )

    def _closure_reply(self) -> str:
        return "Nice work, you made solid progress on this question. We can stop here for now."

    def _build_system_prompt(self, query: str, require_diagnostic: bool) -> str:
        selected_notes = self._select_note_context(query, k=3)
        diagnostic_rule = (
            "The latest message included a screenshot. Your reply MUST be a diagnostic question first."
            if require_diagnostic
            else "Keep advancing with exactly one Socratic question."
        )
        running_summary = self.running_summary or "No prior summary yet."
        gap_snapshot = self._summarize_gap_snapshot()
        return f"""You are Sentinel AI, an encouraging Socratic tutor.

NON-NEGOTIABLE RULES:
1. Never provide final answers or full explanations.
2. Use only the lecture notes excerpt below as knowledge.
3. Reply must be plain text, max {MAX_REPLY_WORDS} words.
4. Exactly one question mark in the reply.
5. No numbered lists or bullet points.
6. Evaluate the learner's latest input first: mention one thing they got right or wrong in natural language, then ask one targeted Socratic question.
   Do not quote the learner verbatim unless the exact wording is essential.
7. If the required knowledge is absent in notes, say exactly:
"This doesn't seem to be in your uploaded notes. Do you want to check?"
8. {diagnostic_rule}
9. Calibrate by distance from the right path:
- Far off: encourage, re-anchor to the current topic, ask a simpler next-step question.
- Partly right: acknowledge what is useful, then probe the missing reasoning link.
- Close: acknowledge progress, then ask a deeper why/how question.
10. Evaluate the learner message each turn for:
- what is correct,
- what is missing or mistaken,
- the smallest next reasoning step.
Your question must target that missing step directly.
11. Avoid repeating the same opening sentence across turns; vary wording naturally.

KNOWN STUDENT PROFILE (dynamic):
{gap_snapshot}

EARLIER CONVERSATION SUMMARY:
{running_summary}

RELEVANT LECTURE NOTES EXCERPT:
{selected_notes}
"""

    def _build_windowed_messages(self, query: str, require_diagnostic: bool) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._build_system_prompt(query, require_diagnostic)}]
        messages.extend(self.conversation_history[-self.max_tail_messages :])
        return messages

    def _find_violations(self, text: str, mode: str) -> list[str]:
        violations: list[str] = []
        words = text.split()
        limit = 35 if mode == "closure" else MAX_REPLY_WORDS
        if len(words) > limit:
            violations.append(f"Too long ({len(words)} words).")
        question_marks = text.count("?")
        if mode in {"diagnostic", "socratic", "nudge"} and question_marks != 1:
            violations.append("Reply must contain exactly one question mark.")
        if mode == "closure" and question_marks > 1:
            violations.append("Closure reply can contain at most one question mark.")
        if re.search(r"(^|\n)\s*([0-9]+\.)", text):
            violations.append("No numbered lists allowed.")
        if re.search(r"(^|\n)\s*[-*]\s+", text):
            violations.append("No bullet lists allowed.")
        banned = [
            "the answer is",
            "therefore",
            "this means",
            "we know that",
            "hence",
            "final expression",
        ]
        lowered = text.lower()
        if mode in {"diagnostic", "socratic", "nudge"} and any(phrase in lowered for phrase in banned):
            violations.append("Contains direct explanation language.")
        sentence_count = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
        max_sentences = 3 if mode != "closure" else 3
        if sentence_count > max_sentences:
            violations.append("Too many sentences.")
        if mode == "diagnostic" and not re.search(r"\b(what|which|how|where|why|do you|can you)\b", lowered):
            violations.append("Screenshot response must be diagnostic.")
        return violations

    def _repair_reply(self, draft_reply: str, violations: list[str], mode: str) -> str:
        if mode == "diagnostic":
            mode_line = "Use one diagnostic question after a short, specific evaluation of the learner's current attempt."
        elif mode == "closure":
            mode_line = "Use a concise closure statement and do not force extra questions."
        elif mode == "nudge":
            mode_line = "Use one nudge question that redirects back to the current study task after a short, specific evaluation."
        else:
            mode_line = "Use one Socratic question after a short, specific evaluation of what is right/wrong."
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict response editor. Rewrite to satisfy ALL constraints. "
                    "Return plain text only, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Constraints: <= {35 if mode == 'closure' else MAX_REPLY_WORDS} words, "
                    f"{'at most one' if mode == 'closure' else 'exactly one'} question mark, "
                    "no bullets, no numbered lists. "
                    f"{mode_line}\nViolations: {violations}\nOriginal:\n{draft_reply}\nRewrite:"
                ),
            },
        ]
        response = self._call_chat_with_retry(
            model=self.aux_model,
            messages=repair_messages,
            max_tokens=120,
            temperature=0,
            retries=4,
        )
        return (response.choices[0].message.content or "").strip()

    def _fallback_reply(self, mode: str) -> str:
        if mode == "diagnostic":
            return "Good start, what do you already understand about the key concepts in this screenshot?"
        if mode == "nudge":
            return self._offtopic_nudge_reply()
        if mode == "closure":
            return self._closure_reply()
        return "Nice effort so far, which single step feels most unclear right now so we can resolve just that part first?"

    def _coerce_question_reply(self, draft_reply: str, mode: str) -> str:
        compact = " ".join((draft_reply or "").split()).strip()
        if not compact:
            return self._fallback_reply(mode)
        if mode == "closure":
            return self._closure_reply()
        if mode == "nudge":
            return self._offtopic_nudge_reply()

        # Keep one concise question from the model output instead of falling back to canned text.
        candidate = compact
        if "?" in compact:
            chunks = [chunk.strip() for chunk in compact.split("?") if chunk.strip()]
            if chunks:
                q_chunks = [
                    chunk
                    for chunk in chunks
                    if re.search(r"\b(what|which|how|why|where|when|who|can|could|would|should|do|does|did|is|are)\b", chunk, flags=re.IGNORECASE)
                ]
                candidate = (q_chunks[-1] if q_chunks else chunks[-1]).strip()
        question_start = re.search(
            r"\b(what|which|how|why|where|when|who|can|could|would|should)\b",
            candidate,
            flags=re.IGNORECASE,
        )
        if question_start is None:
            question_start = re.search(r"\b(do|does|did|is|are)\s+(you|we|i)\b", candidate, flags=re.IGNORECASE)
        if question_start and question_start.start() > 0:
            candidate = candidate[question_start.start() :].strip()
        candidate = candidate.rstrip(".! ")
        if not candidate:
            return self._fallback_reply(mode)
        if not candidate.endswith("?"):
            candidate = f"{candidate}?"
        words = candidate.split()
        if len(words) > MAX_REPLY_WORDS:
            candidate = " ".join(words[:MAX_REPLY_WORDS]).rstrip(".! ")
            if not candidate.endswith("?"):
                candidate = f"{candidate}?"
        return candidate

    def _enforce_reply_rules(self, draft_reply: str, mode: str) -> str:
        cleaned = " ".join((draft_reply or "").split()).strip()
        violations = self._find_violations(cleaned, mode)
        if not violations:
            return cleaned

        repaired = self._repair_reply(cleaned, violations, mode)
        repaired_clean = " ".join(repaired.split()).strip()
        repaired_violations = self._find_violations(repaired_clean, mode)
        if not repaired_violations:
            return repaired_clean
        coerced = self._coerce_question_reply(repaired_clean or cleaned, mode)
        coerced_violations = self._find_violations(coerced, mode)
        if not coerced_violations:
            return coerced
        return self._fallback_reply(mode)

    def _append_user_message(self, user_text: str, screenshot_pil=None) -> None:
        if screenshot_pil is None:
            self.conversation_history.append({"role": "user", "content": user_text})
            return

        b64 = encode_image(screenshot_pil)
        content = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        self.conversation_history.append({"role": "user", "content": content})

    def _extract_learner_text(self, raw_input: str) -> str:
        parsed = _parse_bridge_capture_payload(raw_input)
        learner = parsed.get("learner response", "").strip()
        if learner and learner.lower() != "none":
            return learner
        return " ".join((raw_input or "").split()).strip()

    def _build_query_text(self, raw_input: str) -> str:
        parsed = _parse_bridge_capture_payload(raw_input)
        learner = self._extract_learner_text(raw_input)
        parts = [
            learner,
            parsed.get("vision summary", ""),
            parsed.get("detected tags", ""),
            parsed.get("ocr text", ""),
            parsed.get("grounding context", ""),
        ]
        normalized_parts = []
        for part in parts:
            value = " ".join((part or "").split()).strip()
            if not value or value.lower() == "none":
                continue
            normalized_parts.append(value)
        return " | ".join(normalized_parts) or learner

    def _ensure_gap_entry(self, topic: str) -> dict[str, Any]:
        gaps = self.state["gaps"]
        if topic not in gaps:
            gaps[topic] = {
                "attempts": 0,
                "mastery": 0.5,
                "last_seen": _now_iso(),
                "gap_description": "",
                "knows": [],
                "confused_about": "",
                "evidence": [],
            }
        return gaps[topic]

    def _canonicalize_topic(self, topic: str) -> str:
        candidate = " ".join(topic.strip().split())
        if not candidate:
            return candidate
        candidate_tokens = set(_tokenize(candidate))
        if not candidate_tokens:
            return candidate

        for existing in self.state["gaps"].keys():
            existing_tokens = set(_tokenize(existing))
            if not existing_tokens:
                continue
            overlap = len(candidate_tokens & existing_tokens)
            denom = max(len(candidate_tokens), len(existing_tokens))
            similarity = overlap / denom if denom else 0.0
            if similarity >= 0.6:
                return existing
            lower_candidate = candidate.lower()
            lower_existing = existing.lower()
            if lower_candidate in lower_existing or lower_existing in lower_candidate:
                return existing
        return candidate

    def _extract_and_save_gap(self) -> None:
        try:
            text_msgs: list[dict[str, str]] = []
            for msg in self.conversation_history[-6:]:
                content = self._extract_text_content(msg.get("content"))
                if content:
                    text_msgs.append({"role": msg["role"], "content": content})
            if not text_msgs:
                return

            extract_messages = [
                {
                    "role": "system",
                    "content": (
                        "Analyze this tutoring excerpt and return ONLY valid JSON:\n"
                        "{\n"
                        '  "topic": "specific concept",\n'
                        '  "student_knows": ["short items"],\n'
                        '  "student_confused_about": "short phrase",\n'
                        '  "mastery_delta": -0.05\n'
                        "}\n"
                        "Use small mastery_delta in [-0.15, 0.15]."
                    ),
                },
                {"role": "user", "content": json.dumps(text_msgs)},
            ]
            response = self._call_chat_with_retry(
                model=self.aux_model,
                messages=extract_messages,
                max_tokens=160,
                temperature=0,
                retries=4,
            )
            parsed = _safe_json_load(response.choices[0].message.content or "{}")
            topic = str(parsed.get("topic", "")).strip()
            if not topic:
                return
            topic = self._canonicalize_topic(topic)

            entry = self._ensure_gap_entry(topic)
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            delta = parsed.get("mastery_delta", 0)
            try:
                delta_value = float(delta)
            except (TypeError, ValueError):
                delta_value = 0.0
            delta_value = _clamp(delta_value, -0.15, 0.15)
            entry["mastery"] = round(_clamp(float(entry.get("mastery", 0.5)) + delta_value, 0.0, 1.0), 3)

            knows = parsed.get("student_knows", [])
            if isinstance(knows, list):
                merged = set(str(k).strip() for k in entry.get("knows", []) if str(k).strip())
                merged.update(str(k).strip() for k in knows if str(k).strip())
                entry["knows"] = sorted(merged)[:12]

            confused_about = str(parsed.get("student_confused_about", "")).strip()
            if confused_about:
                entry["confused_about"] = confused_about
                entry["gap_description"] = confused_about

            evidence = entry.get("evidence", [])
            evidence.append({"time": _now_iso(), "delta": delta_value, "confused_about": confused_about})
            entry["evidence"] = evidence[-20:]
            entry["last_seen"] = _now_iso()
            self.current_topic = topic
        except Exception as exc:
            print(f"[Sentinel] Gap extraction failed (non-critical): {exc}")

    def _maybe_refresh_summary(self) -> None:
        sessions = self.state.get("sessions", [])
        turn_count = len(sessions)
        last_summary_turn = int(self.state["meta"].get("last_summary_turn", 0))
        if turn_count == 0 or turn_count - last_summary_turn < self.summary_every_turns:
            return

        recent = sessions[last_summary_turn:turn_count]
        compact_recent = [
            {"u": item.get("user_text", ""), "a": item.get("assistant_reply", "")}
            for item in recent[-self.summary_every_turns :]
        ]

        summary_messages = [
            {
                "role": "system",
                "content": (
                    "Update a tutoring memory summary in <=90 words. Include: topic focus, "
                    "what student knows, and what remains unclear. Plain text only."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "previous_summary": self.running_summary,
                        "new_turns": compact_recent,
                    }
                ),
            },
        ]
        response = self._call_chat_with_retry(
            model=self.aux_model,
            messages=summary_messages,
            max_tokens=130,
            temperature=0,
            retries=4,
        )
        self.running_summary = (response.choices[0].message.content or "").strip()
        self.state["meta"]["running_summary"] = self.running_summary
        self.state["meta"]["last_summary_turn"] = turn_count

    def chat(self, user_text: str, screenshot_pil=None) -> str:
        learner_text = self._extract_learner_text(user_text)
        query_text = self._build_query_text(user_text)

        if self._is_completion_intent(learner_text):
            mode = "closure"
            draft_reply = self._closure_reply()
        elif self._is_off_topic(learner_text, screenshot_pil=screenshot_pil):
            mode = "nudge"
            draft_reply = self._offtopic_nudge_reply()
        else:
            mode = "diagnostic" if screenshot_pil is not None else "socratic"
            draft_reply = ""

        self._append_user_message(learner_text, screenshot_pil)

        if mode in {"closure", "nudge"}:
            reply = self._enforce_reply_rules(draft_reply, mode)
        else:
            request_messages = self._build_windowed_messages(query_text, screenshot_pil is not None)
            response = self._call_chat_with_retry(
                model=self.model,
                messages=request_messages,
                max_tokens=220,
                temperature=0.2,
                retries=5,
            )
            draft_reply = response.choices[0].message.content or ""
            reply = self._enforce_reply_rules(draft_reply, mode)

        self.conversation_history.append({"role": "assistant", "content": reply})
        self.state["sessions"].append(
            {
                "time": _now_iso(),
                "user_text": learner_text,
                "assistant_reply": reply,
                "draft_reply": draft_reply,
                "had_screenshot": screenshot_pil is not None,
                "topic_at_turn": self.current_topic,
                "reply_mode": mode,
            }
        )

        if mode in {"diagnostic", "socratic"}:
            self._extract_and_save_gap()
        self._maybe_refresh_summary()
        save_state(self.state, self.state_file)
        return reply

    def mark_understood(self) -> None:
        if not self.current_topic:
            return
        entry = self._ensure_gap_entry(self.current_topic)
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["mastery"] = round(_clamp(float(entry.get("mastery", 0.5)) + 0.08, 0.0, 1.0), 3)
        entry["last_seen"] = _now_iso()
        save_state(self.state, self.state_file)

    def mark_confused(self) -> None:
        if not self.current_topic:
            return
        entry = self._ensure_gap_entry(self.current_topic)
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["mastery"] = round(_clamp(float(entry.get("mastery", 0.5)) - 0.08, 0.0, 1.0), 3)
        entry["last_seen"] = _now_iso()
        save_state(self.state, self.state_file)

    def new_topic(self) -> None:
        self.conversation_history = []
        self.current_topic = None

    def get_gaps_for_dashboard(self) -> dict[str, Any]:
        return self.state


if __name__ == "__main__":
    from PIL import Image

    print("=== Sentinel AI Test (Hardened) ===")
    print("Requires .env with OPENAI_API_KEY and optional lecture_notes.pdf")

    session = SentinelSession()
    test_image = Image.new("RGB", (400, 300), color=(255, 255, 255))

    r1 = session.chat("I need help understanding this", screenshot_pil=test_image)
    print(f"\nTurn 1 -> {r1}")

    r2 = session.chat("I know some basics, but I do not understand how to apply them to this question.")
    print(f"\nTurn 2 -> {r2}")

    r3 = session.chat("I still don't get why this step works, even though I can see the formula.")
    print(f"\nTurn 3 -> {r3}")

    print("\n=== Current Gap State ===")
    print(json.dumps(session.get_gaps_for_dashboard(), indent=2))
