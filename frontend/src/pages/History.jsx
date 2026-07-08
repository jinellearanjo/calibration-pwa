import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";
import Spinner from "../components/Spinner";
import { listSessions } from "../api";

/**
 * History component.
 * Displays a table of all calibration sessions for the current user, with
 * category/status filtering and CSV export.
 */

/**
 * Escapes a single CSV field: wraps in double quotes and doubles any
 * internal quotes if the value contains a comma, quote, or newline.
 * @param {*} value - Raw cell value (stringified via String()).
 * @returns {string} A CSV-safe field.
 */
function csvEscape(value) {
  const str = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Builds a CSV string (with header row) from a list of sessions.
 * Columns: Session ID, Instrument Name, Category, Status, Date.
 * @param {Array<Object>} sessions - Session records to export.
 * @returns {string} CSV text, CRLF line endings per RFC 4180.
 */
function sessionsToCsv(sessions) {
  const header = ["Session ID", "Instrument Name", "Category", "Status", "Date"];
  const rows = sessions.map(session => [
    session.id || "",
    session.instruments?.name || "",
    session.instruments?.type || "",
    session.status || "PENDING",
    session.date || "",
  ]);
  return [header, ...rows].map(row => row.map(csvEscape).join(",")).join("\r\n");
}

/**
 * Triggers a browser download of the given text as a named file.
 * @param {string} filename - Name for the downloaded file.
 * @param {string} text - File contents.
 * @param {string} mimeType - MIME type for the Blob.
 */
function downloadTextFile(filename, text, mimeType) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

const CATEGORY_OPTIONS = ["All", "Pressure", "Weighing", "Temperature", "Electrical"];
const STATUS_OPTIONS = ["All", "ACCEPTED", "REVIEW REQUIRED", "REJECTED", "PENDING"];

function History() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const navigate = useNavigate();

  useEffect(() => {
    listSessions()
      .then(data => {
        setSessions(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <Spinner message="Loading sessions..." />;

  // Client-side filtering only - no new backend endpoint, sessions is already
  // fetched in full by listSessions() above.
  // NOTE: the category filter compares against session.instruments?.type,
  // which requires GET /api/sessions to select the instrument's type
  // alongside its name (backend/main.py's list_sessions endpoint) - fixed
  // alongside this file, since the filter is useless without it.
  const filteredSessions = sessions.filter(session => {
    const categoryMatches = categoryFilter === "All" || session.instruments?.type === categoryFilter;
    const statusMatches = statusFilter === "All" || (session.status || "PENDING") === statusFilter;
    return categoryMatches && statusMatches;
  });

  const handleDownloadCsv = () => {
    const csv = sessionsToCsv(filteredSessions);
    const stamp = new Date().toISOString().slice(0, 10);
    downloadTextFile(`calibration-sessions-${stamp}.csv`, csv, "text/csv;charset=utf-8;");
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 32px" }}>
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>Records</p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>Session History</h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>All calibration sessions associated with your account.</p>
        </div>

        {error && (
          <div style={{ padding: "14px 16px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: "var(--radius)", color: "var(--color-error)", fontSize: 13, marginBottom: 24 }}>
            {error}
          </div>
        )}

        {sessions.length > 0 && (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
            <FilterSelect
              label="Category"
              value={categoryFilter}
              onChange={setCategoryFilter}
              options={CATEGORY_OPTIONS}
            />
            <FilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={STATUS_OPTIONS}
            />
            <button
              onClick={handleDownloadCsv}
              disabled={filteredSessions.length === 0}
              style={{ padding: "9px 16px", background: "white", color: "var(--color-primary)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", fontSize: 13, fontWeight: 500, cursor: filteredSessions.length === 0 ? "not-allowed" : "pointer" }}
              onMouseEnter={e => { if (filteredSessions.length > 0) e.currentTarget.style.borderColor = "var(--color-primary)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--color-border)"; }}
            >
              Download as CSV
            </button>
          </div>
        )}

        {sessions.length === 0 && !error ? (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", padding: "48px 24px", textAlign: "center" }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14 }}>No calibration sessions found. Start by registering an instrument.</p>
            <button onClick={() => navigate("/instrument")} style={{ marginTop: 16, padding: "9px 20px", background: "var(--color-primary)", color: "white", border: "none", borderRadius: "var(--radius)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>
              Register Instrument
            </button>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", padding: "48px 24px", textAlign: "center" }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14 }}>No sessions match the selected filters.</p>
          </div>
        ) : (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--color-primary)" }}>
                  <th style={thStyle}>Date</th>
                  <th style={thStyle}>Instrument</th>
                  <th style={thStyle}>Technician</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map((session, index) => (
                  <tr key={session.id} style={{ background: index % 2 === 0 ? "white" : "#F9FAFB", borderBottom: "1px solid var(--color-border)" }}>
                    <td style={tdStyle}>{session.date || "—"}</td>
                    <td style={tdStyle}>{session.instruments?.name || "—"}</td>
                    <td style={tdStyle}>{session.technician || "—"}</td>
                    {/* Was session.status || "—": showed a bare dash for a
                        session with no status, while the filter dropdown
                        and CSV export both treat that same missing status
                        as "PENDING" - meaning a session could be invisible
                        under the "PENDING" filter while displaying "—" in
                        this table. Matched to "PENDING" for consistency. */}
                    <td style={tdStyle}><StatusBadge status={session.status || "PENDING"} /></td>
                    <td style={tdStyle}>
                      <div style={{ display: "flex", gap: 8 }}>
                        <ActionButton label="Results" onClick={() => navigate(`/results/${session.id}`)} />
                        <ActionButton label="Report" onClick={() => navigate(`/report/${session.id}`)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--color-muted)", fontWeight: 500 }}>
      {label}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ padding: "7px 10px", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", fontSize: 13, color: "var(--color-text)", background: "white", cursor: "pointer", minWidth: 160 }}
      >
        {options.map(option => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </label>
  );
}

function ActionButton({ label, onClick }) {
  return (
    <button onClick={onClick} style={{ padding: "4px 12px", border: "1px solid var(--color-border)", background: "white", borderRadius: "var(--radius)", fontSize: 12, fontWeight: 500, cursor: "pointer", color: "var(--color-primary)", transition: "border-color 0.15s" }}
      onMouseEnter={e => e.currentTarget.style.borderColor = "var(--color-primary)"}
      onMouseLeave={e => e.currentTarget.style.borderColor = "var(--color-border)"}
    >
      {label}
    </button>
  );
}

const thStyle = { padding: "12px 16px", textAlign: "left", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "white" };
const tdStyle = { padding: "12px 16px", color: "var(--color-text)" };

export default History;