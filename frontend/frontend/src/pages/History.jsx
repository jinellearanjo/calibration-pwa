import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";

/**
 * History component.
 * Displays a list of all calibration sessions for the current user.
 * Each row shows the session date, instrument name, technician, and status.
 * Clicking a row navigates to the results page for that session.
 */
function History() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch all sessions for the current user on mount.
    fetch("http://127.0.0.1:8000/api/sessions")
      .then(r => r.json())
      .then(data => {
        setSessions(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load session history.");
        setLoading(false);
      });
  }, []);

  if (loading) return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ padding: 40 }}>Loading...</div>
    </div>
  );

  if (error) return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ padding: 40 }}>{error}</div>
    </div>
  );

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 24 }}>Session History</h2>

        {sessions.length === 0 ? (
          <p style={{ color: "grey" }}>No calibration sessions found.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "black", color: "white" }}>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Instrument</th>
                <th style={thStyle}>Technician</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session, index) => (
                <tr
                  key={session.id}
                  style={{
                    background: index % 2 === 0 ? "white" : "#f9fafb",
                    cursor: "pointer",
                  }}
                >
                  <td style={tdStyle}>{session.date || "—"}</td>
                  <td style={tdStyle}>{session.instrument_name || "—"}</td>
                  <td style={tdStyle}>{session.technician || "—"}</td>
                  <td style={tdStyle}>
                    <StatusBadge status={session.status || "—"} />
                  </td>
                  <td style={tdStyle}>
                    <button
                      onClick={() => navigate(`/results/${session.id}`)}
                      style={{
                        marginRight: 8,
                        padding: "4px 10px",
                        border: "1px solid black",
                        background: "white",
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      Results
                    </button>
                    <button
                      onClick={() => navigate(`/report/${session.id}`)}
                      style={{
                        padding: "4px 10px",
                        border: "1px solid black",
                        background: "white",
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      Report
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const thStyle = {
  padding: "10px 12px",
  textAlign: "left",
  fontWeight: "bold",
  border: "1px solid black",
};

const tdStyle = {
  padding: "10px 12px",
  border: "1px solid #d1d5db",
};

export default History;