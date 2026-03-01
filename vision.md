# Sentinel AI: The Ambient OS Learning Loop

**Vision Statement:** A system-level "Learning Autopilot" that lives on your desktop, monitors your active study environment across all apps (PDFs, IDEs, Browser), and intervenes with Socratic guidance to map real-time struggle to long-term academic readiness.

---

## 1. The Core Architecture: The OS-Native Loop
- **The Sentinel (The "Eye"):** A Python-based desktop application using `mss` (screenshots) and `keyboard` (global hotkeys) to "see" your active window.
- **The Overlay (The "Socratic Bubble"):** A frameless, transparent `PyQt6` window that floats over your content, allowing for zero-navigation interaction.
- **The Brain (The "Mission Control"):** A local React-based dashboard that processes Sentinel data into mastery and readiness metrics.

---

## 2. Core Features (The "Must-Haves")
- **Global Trigger (`Alt+S`):** Instantly captures the active window or a user-selected region.
- **Multi-Modal Capture (Azure AI Vision):** Interprets diagrams, circuits, and equations from any app (Acrobat, VS Code, Chrome).
- **Socratic Teaching Model:** Instead of providing answers, the Sentinel asks guided questions to build intuition.
- **The Readiness Radar:** A dynamic Spider Chart in the Brain visualizing **Mastery** vs. **Deadline Proximity**.
- **Knowledge Gap Tracker:** A prioritized list of conceptual weaknesses, each linked to a **screenshot** of the specific moment the student struggled.

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

### 3.3 UX Quality Gates (MVP)
- **Focus safety:** Overlay must not steal focus from the learning app.
- **Dismissibility:** `Esc` must close selector/overlay immediately.
- **Latency visibility:** User always sees immediate feedback after trigger, even before cloud response returns.
- **State consistency:** Mission Control state should match the bridge state file and stream events.
- **Failure transparency:** Error states must be explicit, not silent.

---

## 4. The Bug-Radar: 36-Hour Technical Risks

To ensure your 2 CS students do not drown, here are the **5 Critical Bug Zones**:

| Component | Potential Bug / Failure | The 36-Hour Fix |
| :--- | :--- | :--- |
| **The Overlay (PyQt6)** | **Focus Stealing:** The overlay might steal focus from the PDF reader, making it hard to scroll while the bubble is open. | Add an `Esc` key listener to close the overlay instantly. |
| **Screen Scaling (mss)** | **Coordinate Shift:** On 4K or Retina displays, the screenshot might be shifted, causing the AI to see the wrong part of the screen. | Use `mss` with monitor scaling factors. **Test this in Hour 1.** |
| **Azure API (Vision)** | **Latency & OCR Errors:** Sending a 4K screenshot is slow and might misread complex math symbols (like `\int` or `\sum`). | **Crop the image** before sending to Azure. Only send the highlighted area to reduce latency. |
| **Intelligence (Gaps)** | **Hallucination:** The AI might identify a gap that does not exist because it lacks the full syllabus context. | **The Syllabus Anchor:** Always include `syllabus.json` in the system prompt so the AI knows the course boundaries. |
| **The Bridge (FastAPI)** | **CORS & Port Conflicts:** The React Dashboard might fail to talk to the Python app due to browser security or a blocked port. | Use `CORSMiddleware` in FastAPI and hardcode the port to `8000`. |

---

## 5. The USP: The Seamless Learning Loop
The unique value is that **Sentinel AI is app-agnostic**.

1. **Input:** Student reads a complex diagram in a desktop PDF reader.
2. **Trigger:** Student hits `Alt+S` and drags a box over the diagram.
3. **Action:** Sentinel (Azure AI) interprets the diagram and asks a Socratic question in a floating overlay.
4. **Update:** The Brain instantly updates the Readiness Radar via a local FastAPI bridge.
5. **Insight:** The student sees their gap closing without ever leaving their PDF reader.

---

## 6. Technical Implementation for the 36-Hour Sprint
- **The Eye:** Python `mss` + `keyboard` + `PyQt6` (Frameless).
- **The Brain:** React + FastAPI + `state.json`.
- **Microsoft Track Alignment:** Highlight the **Multi-Modal** nature, using **Azure AI Vision** to bridge the gap between pixels and insights.
