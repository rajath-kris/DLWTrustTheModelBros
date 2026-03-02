import { useState, useRef, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useCourse, type CourseId } from "../context/CourseContext";

const BRAIN_ICON = (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <path
      d="M12 4a4 4 0 0 1 4 4v1a3 3 0 0 1 2 5.58v1.06a2 2 0 0 1-1.11 1.79l-1.39.6a2 2 0 0 0-1.11 1.79V18a2 2 0 0 1-4 0v-.18a2 2 0 0 0-1.11-1.79l-1.39-.6A2 2 0 0 1 6 14.64v-1.06a3 3 0 0 1 2-5.58V8a4 4 0 0 1 4-4z"
      fill="#8b5cf6"
      stroke="#7c3aed"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
    <path d="M9 10h.01M15 10h.01M9.5 14a3.5 3.5 0 0 0 5 0" stroke="#7c3aed" strokeWidth="1.2" strokeLinecap="round" />
  </svg>
);

const ICONS = {
  chart: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
    </svg>
  ),
  map: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  ),
  calendar: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  book: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /><line x1="8" y1="6" x2="16" y2="6" /><line x1="8" y1="10" x2="16" y2="10" />
    </svg>
  ),
  folder: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  ),
  clock: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  chat: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  gear: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  chevron: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  collapse: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  ),
  expand: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M9 18l6-6-6-6" />
    </svg>
  ),
};

const NAV_ITEMS = [
  { id: "mission-control", path: "/", label: "Mission Control", icon: ICONS.chart },
  { id: "study-gaps", path: "/gaps", label: "Knowledge Gaps", icon: ICONS.map },
  { id: "schedule", path: "/schedule", label: "Schedule", icon: ICONS.calendar },
  { id: "planner", path: "/planner", label: "Study Planner", icon: ICONS.book },
  { id: "documents", path: "/documents", label: "Document Hub", icon: ICONS.folder },
  { id: "history", path: "/history", label: "Session History", icon: ICONS.clock },
  { id: "ask", path: "/ask", label: "Ask Sentinel", icon: ICONS.chat },
  { id: "preferences", path: "/preferences", label: "Preferences", icon: ICONS.gear },
];

function getCourseLabel(courseId: CourseId, courses: { id: string; name: string }[]): string {
  if (courseId === "all") return "All Courses";
  const c = courses.find((x) => x.id === courseId);
  const short = c?.name.split("—")[0]?.trim() ?? courseId;
  return short;
}

function getCourseAccent(courseId: CourseId, courses: { id: string; accentColor: string }[]): string {
  if (courseId === "all") return "#6b7280";
  const c = courses.find((x) => x.id === courseId);
  return c?.accentColor ?? "#6b7280";
}

export function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { courseId, setCourseId, courses } = useCourse();
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const pathname = location.pathname;

  useEffect(() => {
    if (!popoverOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) setPopoverOpen(false);
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [popoverOpen]);

  const courseLabel = getCourseLabel(courseId, courses);
  const accentColor = getCourseAccent(courseId, courses);

  return (
    <aside className={`app-sidebar app-sidebar-new ${collapsed ? "app-sidebar-collapsed" : ""}`} role="navigation" aria-label="Main navigation">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon" aria-hidden>{BRAIN_ICON}</div>
        {!collapsed && (
          <>
            <span className="sidebar-logo-title">The Brain</span>
            <span className="sidebar-logo-subtitle">SENTINEL AI</span>
          </>
        )}
      </div>

      {!collapsed && (
        <div className="sidebar-course-switcher" ref={popoverRef}>
          <button
            type="button"
            className="sidebar-course-pill"
            onClick={() => setPopoverOpen((o) => !o)}
            aria-expanded={popoverOpen}
            aria-haspopup="listbox"
          >
            <span className="sidebar-course-dot" style={{ background: accentColor }} aria-hidden />
            <span className="sidebar-course-label">{courseLabel}</span>
            <span className="sidebar-course-chevron">{ICONS.chevron}</span>
          </button>
          {popoverOpen && (
            <div className="sidebar-course-popover" role="listbox">
              <button
                type="button"
                className="sidebar-course-option"
                onClick={() => { setCourseId("all"); setPopoverOpen(false); }}
              >
                All Courses
              </button>
              {courses.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="sidebar-course-option"
                  onClick={() => { setCourseId(c.id as CourseId); setPopoverOpen(false); }}
                >
                  {c.name}
                </button>
              ))}
              <div className="sidebar-course-add">+ Add Course</div>
            </div>
          )}
        </div>
      )}

      <nav className="sidebar-nav sidebar-nav-new">
        <ul className="sidebar-nav-list">
          <li>
            <NavItem
              path="/"
              label="Mission Control"
              icon={ICONS.chart}
              pathname={pathname}
              collapsed={collapsed}
              accentColor={pathname === "/" ? accentColor : undefined}
              onClick={() => navigate("/")}
            />
          </li>
        </ul>

        {!collapsed && <div className="sidebar-nav-group-label">STUDY</div>}
        <ul className="sidebar-nav-list">
          <li><NavItem path="/gaps" label="Knowledge Gaps" icon={ICONS.map} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/gaps")} /></li>
          <li><NavItem path="/schedule" label="Schedule" icon={ICONS.calendar} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/schedule")} /></li>
          <li><NavItem path="/planner" label="Study Planner" icon={ICONS.book} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/planner")} /></li>
        </ul>

        {!collapsed && <div className="sidebar-nav-group-label">RESOURCES</div>}
        <ul className="sidebar-nav-list">
          <li><NavItem path="/documents" label="Document Hub" icon={ICONS.folder} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/documents")} /></li>
          <li><NavItem path="/history" label="Session History" icon={ICONS.clock} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/history")} /></li>
        </ul>

        <ul className="sidebar-nav-list">
          <li><NavItem path="/ask" label="Ask Sentinel" icon={ICONS.chat} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/ask")} /></li>
        </ul>

        <ul className="sidebar-nav-list">
          <li><NavItem path="/preferences" label="Preferences" icon={ICONS.gear} pathname={pathname} collapsed={collapsed} onClick={() => navigate("/preferences")} /></li>
        </ul>
      </nav>

      <div className="sidebar-collapse-wrap">
        <button
          type="button"
          className="sidebar-collapse-btn"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? ICONS.expand : ICONS.collapse}
        </button>
      </div>

      <div className="sidebar-user">
        <div className="sidebar-user-avatar" aria-hidden>AK</div>
        {!collapsed && (
          <div className="sidebar-user-info">
            <span className="sidebar-user-name">Alex Kim</span>
            <span className="sidebar-user-meta">CS Year 2</span>
          </div>
        )}
      </div>
    </aside>
  );
}

function NavItem({
  path,
  label,
  icon,
  pathname,
  collapsed,
  accentColor,
  onClick,
}: {
  path: string;
  label: string;
  icon: React.ReactNode;
  pathname: string;
  collapsed: boolean;
  accentColor?: string;
  onClick: () => void;
}) {
  const isActive = path === "/" ? pathname === "/" : pathname.startsWith(path);
  return (
    <button
      type="button"
      className={`sidebar-nav-item ${isActive ? "active" : ""}`}
      onClick={onClick}
      title={collapsed ? label : undefined}
      style={isActive && accentColor ? { borderLeftColor: accentColor } : undefined}
    >
      <span className="sidebar-nav-icon">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </button>
  );
}
