import { useCourse } from "../context/CourseContext";
import { useLearningState } from "../context/LearningStateContext";

export function PreferencesPage() {
  const { courses } = useCourse();
  const { dataSource, setDataSource } = useLearningState();

  return (
    <div className="page-shell page-fade">
      <header className="prefs-page-header">
        <h1>Preferences</h1>
      </header>

      <section className="prefs-section">
        <h2 className="prefs-section-title">User profile</h2>
        <div className="prefs-form">
          <label>Display name</label>
          <input type="text" defaultValue="Alex Kim" placeholder="Display name" />
          <label>Year / cohort</label>
          <input type="text" defaultValue="CS Year 2" placeholder="e.g. CS Year 2" />
        </div>
      </section>

      <section className="prefs-section">
        <h2 className="prefs-section-title">Notifications</h2>
        <div className="prefs-form">
          <label className="prefs-check-label">
            <input type="checkbox" defaultChecked />
            Remind me before deadlines
          </label>
          <label className="prefs-check-label">
            <input type="checkbox" defaultChecked />
            Weekly readiness summary
          </label>
        </div>
      </section>

      <section className="prefs-section">
        <h2 className="prefs-section-title">Data source</h2>
        <p className="prefs-desc">Choose whether Mission Control uses mock parity data or live bridge API state.</p>
        <div className="prefs-form">
          <label className="prefs-check-label">
            <input
              type="radio"
              name="data-source"
              checked={dataSource === "mock"}
              onChange={() => setDataSource("mock")}
            />
            Mock (parity adapter)
          </label>
          <label className="prefs-check-label">
            <input
              type="radio"
              name="data-source"
              checked={dataSource === "bridge"}
              onChange={() => setDataSource("bridge")}
            />
            Bridge API (live)
          </label>
        </div>
      </section>

      <section className="prefs-section">
        <h2 className="prefs-section-title">Sentinel hotkey</h2>
        <p className="prefs-desc">Global shortcut to open region capture.</p>
        <div className="prefs-hotkey-display">Alt + S</div>
      </section>

      <section className="prefs-section">
        <h2 className="prefs-section-title">Theme</h2>
        <p className="prefs-desc">Dark theme only for now.</p>
      </section>

      <section className="prefs-section">
        <h2 className="prefs-section-title">Course management</h2>
        <p className="prefs-desc">Add, remove, or rename courses. Set accent colors.</p>
        <ul className="prefs-course-list">
          {courses.map((c) => (
            <li key={c.id} className="prefs-course-item">
              <span className="prefs-course-dot" style={{ background: c.accentColor }} />
              <span className="prefs-course-name">{c.name}</span>
              <button type="button" className="prefs-course-btn">Rename</button>
              <button type="button" className="prefs-course-btn prefs-course-btn-remove">Remove</button>
            </li>
          ))}
        </ul>
        <button type="button" className="top-bar-btn primary">+ Add Course</button>
      </section>
    </div>
  );
}
