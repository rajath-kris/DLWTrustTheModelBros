# Sentinel AI: The Ambient OS Learning Loop

**Vision Statement:** A system-level "Learning Autopilot" that lives on your desktop, monitors your active study environment across all apps (PDFs, IDEs, Browser), and intervenes with Socratic guidance to map real-time struggle to long-term academic readiness.

---

## 1. The Core Architecture: The OS-Native Loop
- **The Sentinel (The "Eye"):** A Python-based desktop application using `mss` (screenshots) and `keyboard` (global hotkeys) to "see" your active window.
- **The Overlay (The "Socratic Bubble"):** A frameless, transparent `PyQt6` window that floats over your content, allowing for zero-navigation interaction.
- **The Bridge Intelligence Layer (The "Scoring Engine"):** A FastAPI + Python layer that owns canonical gap prioritization and readiness scoring logic (`services/bridge-api/app/readiness.py`).
- **The Course Context Layer (The "Grounding Memory"):** A local store for uploaded slides/course materials used to anchor prompting and gap detection to real class context.
- **The Brain (The "Mission Control"):** A local React-based dashboard that visualizes bridge-provided metrics and state in real time.

---

## 2. Core Features (The "Must-Haves")
- **Global Trigger (`Alt+S`):** Instantly captures the active window or a user-selected region.
- **Multi-Modal Capture (Vision + OCR):** Interprets diagrams, circuits, and equations from any app (Acrobat, VS Code, Chrome).
- **Socratic Teaching Model:** Instead of providing answers, the Sentinel asks guided questions to build intuition.
- **Socratic Turn Loop + Micro-Checks:** After key Socratic turns, the system asks short micro questions to measure understanding and update confidence in detected gaps.
- **The Readiness Radar:** A dynamic Spider Chart in the Brain visualizing **Mastery** vs. **Deadline Proximity**.
- **Knowledge Gap Tracker:** A prioritized list of conceptual weaknesses, each linked to a **screenshot** of the specific moment the student struggled and the follow-up micro-check evidence.
- **Topic Mastery + Next Study Actions:** Mission Control surfaces per-topic mastery and an explicit "what to study next" plan.
- **Course Material Upload + Grounding:** Students can upload slides/course files so prompts and guidance stay grounded in course context.

### 2.1 Quiz Tab (MCQ Readiness Loop)
- **Topic-based quiz generation from course sources:** Generate MCQs from PYQs and tutorials for selected topics.
- **Readiness + knowledge-gap measurement through quiz performance:** Quiz accuracy and error patterns directly update readiness and gap signals.
- **Improvement path via quizzes:** If a learner wants to improve readiness score and close gaps, the system should guide them into targeted quizzes.
- **Deadline-aware repetition:** As quiz/test deadlines approach, repeat previously wrong questions and relevant previously captured question contexts.
- **Exam-time recommendation mode:** When actual tests are near, recommend quizzes topic-by-topic.

---

## 3. UI Goals (Sentinel + Mission Control)

### 3.1 Sentinel Overlay UI Goals
- **Zero-navigation interaction:** Student stays in the current app (PDF, IDE, browser) and never needs to switch windows.
- **Fast status clarity:** Overlay should clearly communicate `Selecting` -> `Analyzing capture...` -> `Socratic prompt` or `Error`.
- **Non-intrusive behavior:** Overlay remains readable but does not block normal study flow; student can dismiss instantly with `Esc`.
- **Context-aware placement:** Bubble appears near the captured region, flips or clamps at screen edges, and remains fully visible.
- **Readable prompt design:** Strong contrast, clean typography, sensible width bounds, selectable text, and wrapped long prompts.
- **Reliable fallback messaging:** If capture or bridge fails, show actionable text (for example, bridge down, invalid capture, retry advice).

### 3.2 Mission Control UI Goals
- **Single-screen awareness:** One screen should show readiness status, current risk, and active knowledge gaps without extra navigation.
- **Live state updates:** Dashboard reacts to SSE/API updates so readiness and gap list change as soon as a capture is processed.
- **Readiness radar legibility:** Axes and values are easy to parse at a glance; values remain normalized and consistent.
- **Prioritized gap workflow:** Gap list defaults to priority order, supports status filtering (`open`, `reviewing`, `closed`), and fast status cycling.
- **Evidence-first debugging:** Every gap links to the source screenshot so users can inspect exactly where the struggle happened.
- **Trustworthy timestamps and source context:** Show latest update time and latest Socratic prompt context.
- **Topic-first intelligence:** Show topic breakdown, topic mastery, and per-topic trajectory.
- **Actionable next step guidance:** Show concrete next study actions tied to priority gaps and upcoming deadlines.
- **Course-context traceability:** Let users inspect which uploaded slides/materials were used as context for each guidance event.

### 3.3 UX Quality Gates (MVP)
- **Focus safety:** Overlay must not steal focus from the learning app.
- **Dismissibility:** `Esc` must close selector/overlay immediately.
- **Latency visibility:** User always sees immediate feedback after trigger, even before cloud response returns.
- **State consistency:** Mission Control state should match the bridge state file and stream events.
- **Failure transparency:** Error states must be explicit, not silent.
- **Learning-loop continuity:** Every captured doubt should progress through prompting, understanding check, and state update without dead ends.

### 3.4 UI Maintainability Gates (MVP)
- **Reusable Sentinel UI primitives:** Extract repeatable overlay and selector UI pieces (action buttons, status blocks, input row, style tokens) into reusable components.
- **Single source styling tokens:** Keep font, color, spacing, and animation constants centralized to reduce one-off styling drift.
- **Feature-safe refactors:** UI structural refactors must preserve focus safety, dismissibility, and placement behavior.

---

## 4. The Bug-Radar: 36-Hour Technical Risks

To ensure your 2 CS students do not drown, here are the **5 Critical Bug Zones**:

| Component | Potential Bug / Failure | The 36-Hour Fix |
| :--- | :--- | :--- |
| **The Overlay (PyQt6)** | **Focus Stealing:** The overlay might steal focus from the PDF reader, making it hard to scroll while the bubble is open. | Add an `Esc` key listener to close the overlay instantly. |
| **Screen Scaling (mss)** | **Coordinate Shift:** On 4K or Retina displays, the screenshot might be shifted, causing the AI to see the wrong part of the screen. | Use `mss` with monitor scaling factors. **Test this in Hour 1.** |
| **Vision API** | **Latency & OCR Errors:** Sending a 4K screenshot is slow and might misread complex math symbols (like `\int` or `\sum`). | **Crop the image** before sending to the vision model. Only send the highlighted area to reduce latency. |
| **Intelligence (Gaps)** | **Hallucination:** The AI might identify a gap that does not exist because it lacks the full syllabus context. | **The Syllabus Anchor:** Always include `syllabus.json` in the system prompt so the AI knows the course boundaries. |
| **The Bridge (FastAPI)** | **CORS & Port Conflicts:** The React Dashboard might fail to talk to the Python app due to browser security or a blocked port. | Use `CORSMiddleware` in FastAPI and hardcode the port to `8000`. |

---

## 5. The USP: The Seamless Learning Loop
The unique value is that **Sentinel AI is app-agnostic**.

1. **Input:** Student reads a complex diagram in a desktop PDF reader.
2. **Trigger:** Student hits `Alt+S` and drags a box over the diagram.
3. **Action:** Sentinel interprets the diagram and asks a Socratic question in a floating overlay.
4. **Check:** Sentinel issues micro questions to validate understanding after responses.
5. **Update:** The Bridge writes gap/readiness/topic signals and Mission Control updates instantly.
6. **Insight:** The student sees topic mastery, next study actions, and deadline-linked risk without leaving flow.

---

## 6. Technical Implementation for the 36-Hour Sprint
- **The Eye:** Python `mss` + `keyboard` + `PyQt6` (Frameless).
- **The Brain:** React + FastAPI + `state.json`.
- **Micro-Check Engine:** Lightweight follow-up question generation and scoring layer tied to turns.
- **Context Ingestion:** Slide upload pipeline (file storage + extract/index + context linking) for course-grounded prompting.
- **Implementation Alignment:** Highlight the **Multi-Modal** nature, using vision + OCR interpretation to bridge the gap between pixels and insights.

---

## 7. Additional Product Modes (Post-MVP)
- **Ambient Auto-Capture Mode (Opt-In):** Sentinel can suggest or trigger captures without a hotkey when repeated struggle signals are detected.
- **Safety Constraints for Ambient Mode:** Must be user-toggleable, visible when active, privacy-bounded, and instantly pausable with `Esc`.
- **MVP Boundary:** The mandatory MVP trigger remains `Alt+S`; ambient mode is a controlled extension, not a replacement for the baseline flow.

---

## 8. MVP Definition: Enforced Learning Loop
The MVP is considered complete only when this end-to-end loop is enforced:

1. **Capture a real doubt:** User triggers Sentinel (`Alt+S`) from any app and selects a region tied to a concrete question/doubt.
2. **Socratic guidance first:** System responds with thought-provoking prompts, not direct final answers.
3. **Understanding check:** System asks micro questions after key turns to verify understanding.
4. **Gap decision update:** User responses from Socratic turns + micro checks update gap confidence/severity.
5. **Mission Control insight delivery:** Dashboard reflects topic breakdown, topic mastery, deadline pressure, and recommended next study actions.
6. **Course grounding:** Uploaded slide/course materials are available as context and traceable in guidance output.

### 8.1 Explicit MVP Deliverables
- **Sentinel Overlay Deliverables**
  - Capture-triggered Socratic conversation loop.
  - Inline micro-question checks after selected turns.
  - Fast dismissibility, non-focus-stealing baseline behavior, and clear failure states.
- **Bridge/API Deliverables**
  - Turn and micro-check events persisted to canonical state.
  - Gap updates include evidence lineage (capture + prompt/micro-check context).
  - Topic-level mastery and recommendation fields computed from state.
- **Mission Control Deliverables**
  - Topic breakdown and mastery views.
  - "What to study next" recommendations prioritized by gap severity and deadlines.
  - Deadline-aware risk visibility and evidence drill-down.
- **Course Context Deliverables**
  - Upload pathway for slides/course docs.
  - Extracted context usable in prompting and explainable in UI.
