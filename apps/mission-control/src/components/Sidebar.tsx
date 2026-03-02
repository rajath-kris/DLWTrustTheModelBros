import { useNavigate, useLocation } from "react-router-dom";

const ID_TO_PATH: Record<string, string> = {
  "mission-control": "/",
  "readiness-radar": "/",
  "knowledge-gap-tracker": "/gaps",
  "document-hub": "/documents",
  "session-history": "/history",
  schedule: "/schedule",
  preferences: "/preferences",
};

function getPathForId(id: string): string {
  return ID_TO_PATH[id] ?? "/";
}

function isActive(pathname: string, id: string): boolean {
  const path = getPathForId(id);
  if (path === "/") return pathname === "/";
  return pathname.startsWith(path);
}

const BRAIN_ICON = (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <path
      d="M12 4a4 4 0 0 1 4 4v1a3 3 0 0 1 2 5.58v1.06a2 2 0 0 1-1.11 1.79l-1.39.6a2 2 0 0 0-1.11 1.79V18a2 2 0 0 1-4 0v-.18a2 2 0 0 0-1.11-1.79l-1.39-.6A2 2 0 0 1 6 14.64v-1.06a3 3 0 0 1 2-5.58V8a4 4 0 0 1 4-4z"
      fill="#8b5cf6"
      stroke="#7c3aed"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
    <path
      d="M9 10h.01M15 10h.01M9.5 14a3.5 3.5 0 0 0 5 0"
      stroke="#7c3aed"
      strokeWidth="1.2"
      strokeLinecap="round"
    />
  </svg>
);

const ICONS = {
  chart: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  ),
  radar: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
    </svg>
  ),
  thought: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 18h6M9 14h6M9 10h.01M12 4a4 4 0 0 1 4 4c0 2-1.5 3.5-3 5l-1 1H9l-1-1c-1.5-1.5-3-3-3-5a4 4 0 0 1 4-4z" />
    </svg>
  ),
  folder: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  ),
  chat: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  calendar: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  gear: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

const CORE_ITEMS = [
  { id: "mission-control", label: "Mission Control", icon: ICONS.chart },
  { id: "readiness-radar", label: "Readiness Radar", icon: ICONS.radar },
  { id: "knowledge-gap-tracker", label: "Knowledge Gaps", icon: ICONS.thought },
];

const RESOURCE_ITEMS = [
  { id: "document-hub", label: "Document Hub", icon: ICONS.folder },
  { id: "session-history", label: "Session History", icon: ICONS.chat },
  { id: "schedule", label: "Schedule", icon: ICONS.calendar },
];

const SETTINGS_ITEMS = [{ id: "preferences", label: "Preferences", icon: ICONS.gear }];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;

  const handleNav = (id: string) => {
    navigate(getPathForId(id));
  };

  return (
    <aside className="app-sidebar" role="navigation" aria-label="Main navigation">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon" aria-hidden>
          {BRAIN_ICON}
        </div>
        <span className="sidebar-logo-title">The Brain</span>
        <span className="sidebar-logo-subtitle">SENTINEL AI</span>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-nav-group">
          <span className="sidebar-nav-group-label">CORE</span>
          <ul className="sidebar-nav-list">
            {CORE_ITEMS.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`sidebar-nav-item ${isActive(pathname, item.id) ? "active" : ""}`}
                  onClick={() => handleNav(item.id)}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="sidebar-nav-group">
          <span className="sidebar-nav-group-label">RESOURCES</span>
          <ul className="sidebar-nav-list">
            {RESOURCE_ITEMS.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`sidebar-nav-item ${isActive(pathname, item.id) ? "active" : ""}`}
                  onClick={() => handleNav(item.id)}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="sidebar-nav-group">
          <span className="sidebar-nav-group-label">SETTINGS</span>
          <ul className="sidebar-nav-list">
            {SETTINGS_ITEMS.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`sidebar-nav-item ${isActive(pathname, item.id) ? "active" : ""}`}
                  onClick={() => handleNav(item.id)}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <div className="sidebar-user">
        <div className="sidebar-user-avatar" aria-hidden>
          AK
        </div>
        <div className="sidebar-user-info">
          <span className="sidebar-user-name">Alex Kim</span>
          <span className="sidebar-user-meta">CS Year 2</span>
        </div>
      </div>
    </aside>
  );
}
