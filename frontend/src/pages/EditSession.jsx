import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { listSessions } from "../api";

/**
 * EditSession page.
 * Lists all sessions and lets the user pick one to edit.
 * Navigates to InstrumentForm in edit mode with the session's existing data.
 */
function EditSession() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    listSessions()
      .then(data => {
        setSessions(data || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  function handleEdit(session) {
    navigate("/instrument", {
      state: {
        editMode: true,
        sessionId: session.id,
        instrumentId: session.instrument_id,
      },
    });
  }

  if (loading) return <Spinner message="Loading sessions..." />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 32px" }}>
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Edit
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Edit Existing Session
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Select a session to edit its instrument details, session metadata, or calibration reference.
          </p>
        </div>

        {error && (
          <div style={{ padding: "14px 16px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: "var(--radius)", color: "var(--color-error)", fontSize: 13, marginBottom: 24 }}>
            {error}
          </div>
        )}

        {sessions.length === 0 && !error ? (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", padding: "48px 24px", textAlign: "center" }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14 }}>No sessions found.</p>
          </div>
        ) : (
          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--color-primary)" }}>
                  <th style={thStyle}>Date</th>
                  <th style={thStyle}>Instrument</th>
                  <th style={thStyle}>Category</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session, index) => (
                  <tr
                    key={session.id}
                    style={{ background: index % 2 === 0 ? "white" : "#F9FAFB", borderBottom: "1px solid var(--color-border)" }}
                  >
                    <td style={tdStyle}>{session.date || "—"}</td>
                    <td style={tdStyle}>{session.instruments?.name || "—"}</td>
                    <td style={tdStyle}>{session.instruments?.type || "—"}</td>
                    <td style={tdStyle}><StatusBadge status={session.status || "PENDING"} /></td>
                    <td style={tdStyle}>
                      <button
                        onClick={() => handleEdit(session)}
                        style={{
                          padding: "4px 14px",
                          background: "white",
                          color: "var(--color-primary)",
                          border: "1px solid var(--color-border)",
                          borderRadius: "var(--radius)",
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: "pointer",
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--color-primary)"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--color-border)"; }}
                      >
                        Edit
                      </button>
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

const thStyle = { padding: "12px 16px", textAlign: "left", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "white" };
const tdStyle = { padding: "12px 16px", color: "var(--color-text)" };

export default EditSession;
