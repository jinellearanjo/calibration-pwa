import { useState, useEffect } from "react";
import { listSessions } from "../api";

/**
 * SessionPicker component.
 * Dropdown for selecting an existing calibration session, shown above
 * form content on pages 04-07 whenever the page is reached without a
 * :sessionId already present in the URL (e.g. via a Dashboard card
 * rather than the SessionForm -> ReadingsForm navigation chain).
 * Fetches the list via listSessions() from api.js - the single source
 * of truth for API calls, per project convention.
 *
 * @param {Object} props
 * @param {string|null} props.selectedSessionId - Currently selected session id, or null.
 * @param {Function} props.onSelect - Called with the selected session's id (string), or null if cleared.
 * @param {string} [props.categoryFilter] - If provided, only sessions whose
 *   instrument.type matches are shown - used by the four category-specific
 *   readings pages (ReadingsForm=Pressure, WeighingReadingsForm,
 *   TemperatureReadingsForm, ElectricalReadingsForm) so a Temperature
 *   session can no longer be picked while entering Weighing data (the
 *   backend also guards against this via _require_instrument_type, but
 *   filtering it out of the dropdown means the wrong option is never
 *   offered in the first place). CalculationView/ResultsView/ReportPage
 *   are category-agnostic and intentionally don't pass this - any
 *   session's calculation/results/report can be viewed regardless of
 *   its instrument category.
 */
function SessionPicker({ selectedSessionId, onSelect, categoryFilter }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listSessions()
      .then(data => {
        if (!cancelled) {
          setSessions(data || []);
          setLoading(false);
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const visibleSessions = categoryFilter
    ? sessions.filter(s => s.instruments?.type === categoryFilter)
    : sessions;

  return (
    <div style={{
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderLeft: "4px solid var(--color-accent)",
      borderRadius: "var(--radius)",
      padding: "20px 24px",
      marginBottom: 24,
      boxShadow: "var(--shadow-sm)",
    }}>
      <label htmlFor="session-picker" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--color-text)" }}>
        Select a Calibration Session
      </label>
      <p style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 12 }}>
        Choose an existing session to continue working on. The form below stays disabled until you select one.
      </p>

      {loading && <p style={{ fontSize: 13, color: "var(--color-muted)" }}>Loading sessions...</p>}
      {error && <p style={{ fontSize: 13, color: "var(--color-error)" }}>{error}</p>}

      {!loading && !error && (
        <select
          id="session-picker"
          value={selectedSessionId || ""}
          onChange={e => onSelect(e.target.value || null)}
          style={{
            width: "100%",
            padding: "10px 12px",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)",
            fontSize: 14,
            background: "white",
          }}
        >
          <option value="">— Select a session —</option>
          {visibleSessions.map(s => (
            <option key={s.id} value={s.id}>
              {(s.instruments && s.instruments.name) || s.instrument_id} — {s.date} — {s.technician}
            </option>
          ))}
        </select>
      )}

      {!loading && !error && visibleSessions.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginTop: 8 }}>
          {categoryFilter && sessions.length > 0
            ? `No ${categoryFilter} calibration sessions found. Other-category sessions exist but aren't shown here.`
            : "No calibration sessions found. Create one from the Dashboard first."}
        </p>
      )}
    </div>
  );
}

export default SessionPicker;