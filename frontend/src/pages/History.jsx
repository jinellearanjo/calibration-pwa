import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";
import Spinner from "../components/Spinner";
import { listSessions } from "../api";

/**
 * History component.
 * Displays a table of all calibration sessions for the current user.
 */
function History() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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

        {sessions.length === 0 && !error ? (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "48px 24px", textAlign: "center" }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14 }}>No calibration sessions found. Start by registering an instrument.</p>
            <button onClick={() => navigate("/instrument")} style={{ marginTop: 16, padding: "9px 20px", background: "var(--color-primary)", color: "white", border: "none", borderRadius: "var(--radius)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>
              Register Instrument
            </button>
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
                {sessions.map((session, index) => (
                  <tr key={session.id} style={{ background: index % 2 === 0 ? "white" : "#F9FAFB", borderBottom: "1px solid var(--color-border)" }}>
                    <td style={tdStyle}>{session.date || "—"}</td>
                    <td style={tdStyle}>{session.instruments?.name || "—"}</td>
                    <td style={tdStyle}>{session.technician || "—"}</td>
                    <td style={tdStyle}><StatusBadge status={session.status || "—"} /></td>
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