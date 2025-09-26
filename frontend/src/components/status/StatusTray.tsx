import { useMemo } from "react";

import { useStatusFeed } from "@hooks/useStatusFeed";

import "@styles/status-tray.css";

export function StatusTray(): JSX.Element | null {
  const { entries, clearFinished } = useStatusFeed();

  const activeEntries = useMemo(
    () => entries.filter((entry) => entry.state === "pending" || entry.state === "running"),
    [entries]
  );

  const completedEntries = useMemo(
    () => entries.filter((entry) => entry.state === "success" || entry.state === "error"),
    [entries]
  );

  const hasEntries = activeEntries.length > 0 || completedEntries.length > 0;

  if (!hasEntries) {
    return null;
  }

  return (
    <div className="status-tray" aria-live="polite">
      <div className="status-tray__section" aria-label="Active operations">
        <h2 className="status-tray__heading">Activity</h2>
        {activeEntries.length === 0 ? (
          <p className="status-tray__empty">No active operations</p>
        ) : (
          <ul className="status-tray__list">
            {activeEntries.map((entry) => (
              <li key={entry.id} className="status-tray__item status-tray__item--active">
                <div>
                  <span className="status-tray__label">{entry.label}</span>
                  <span className="status-tray__state">{formatState(entry.state)}</span>
                </div>
                {typeof entry.progress === "number" ? (
                  <progress value={entry.progress} max={100}>
                    {entry.progress}%
                  </progress>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
      {completedEntries.length > 0 ? (
        <div className="status-tray__section" aria-label="Completed operations">
          <div className="status-tray__section-header">
            <h3 className="status-tray__heading">Recently completed</h3>
            <button
              type="button"
              className="status-tray__clear-button"
              onClick={clearFinished}
            >
              Clear
            </button>
          </div>
          <ul className="status-tray__list">
            {completedEntries.map((entry) => (
              <li key={entry.id} className={`status-tray__item status-tray__item--${entry.state}`}>
                <span className="status-tray__label">{entry.label}</span>
                <span className="status-tray__state">{formatState(entry.state)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function formatState(state: string): string {
  switch (state) {
    case "pending":
      return "Queued";
    case "running":
      return "Running";
    case "success":
      return "Completed";
    case "error":
      return "Failed";
    default:
      return state;
  }
}
