import { useMemo, useState } from "react";
import { startOfDay, subWeeks, isWithinInterval } from "date-fns";
import { MOCK_INTERACTION_LOG, type MockInteraction } from "../data/mockInteractionLog";

type TimeFilter = "today" | "week" | "all";

function formatMessageTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function BrainAvatar() {
  return (
    <div className="session-avatar session-avatar-ai" aria-hidden>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
        <path d="M12 13c-4 0-7 2-7 6v1h14v-1c0-4-3-6-7-6z" />
      </svg>
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="session-avatar session-avatar-user" aria-hidden>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
      </svg>
    </div>
  );
}

export function InteractionLog({
  interactions: propInteractions,
}: {
  interactions?: MockInteraction[] | null;
}) {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const interactions = propInteractions ?? MOCK_INTERACTION_LOG;

  const filtered = useMemo(() => {
    const now = new Date();
    const todayStart = startOfDay(now);
    const weekStart = startOfDay(subWeeks(now, 1));
    if (timeFilter === "today") {
      return interactions.filter((i) => new Date(i.timestamp) >= todayStart);
    }
    if (timeFilter === "week") {
      return interactions.filter((i) =>
        isWithinInterval(new Date(i.timestamp), { start: weekStart, end: now })
      );
    }
    return interactions;
  }, [interactions, timeFilter]);

  const ordered = useMemo(() => [...filtered], [filtered]);

  return (
    <section className="session-history-section">
      <h2 className="section-heading">SESSION HISTORY – RECENT INTERACTIONS</h2>
      <article className="card interaction-log-card">
        <header className="gaps-head">
          <div>
            <h3>Sentinel Interaction Log</h3>
            <p>Chronological Socratic Q&A.</p>
          </div>
          <div className="filter-group">
            <button
              type="button"
              className={timeFilter === "today" ? "filter active" : "filter"}
              onClick={() => setTimeFilter("today")}
            >
              Today
            </button>
            <button
              type="button"
              className={timeFilter === "week" ? "filter active" : "filter"}
              onClick={() => setTimeFilter("week")}
            >
              This Week
            </button>
            <button
              type="button"
              className={timeFilter === "all" ? "filter active" : "filter"}
              onClick={() => setTimeFilter("all")}
            >
              All Time
            </button>
          </div>
        </header>

        <div className="interaction-log-feed interaction-log-chat">
          {ordered.length === 0 ? (
            <p className="status-line">No interactions in this period.</p>
          ) : (
            ordered.map((item, i) => (
              <div key={`${item.timestamp}-${i}`} className={`interaction-log-item role-${item.role}`}>
                {item.role === "ai" ? <BrainAvatar /> : <UserAvatar />}
                <div className="interaction-log-body">
                  <span className="interaction-log-role">{item.role === "ai" ? "SENTINEL AI" : "YOU"}</span>
                  <p className="interaction-log-text">{item.text}</p>
                  <time dateTime={item.timestamp} className="interaction-log-time">
                    {formatMessageTime(item.timestamp)}
                  </time>
                </div>
              </div>
            ))
          )}
        </div>
      </article>
    </section>
  );
}
