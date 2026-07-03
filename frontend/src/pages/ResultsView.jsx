import { getResults } from "../api";
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";
import Spinner from "../components/Spinner";

/**
 * ResultsView component.
 * Displays the validation result for a calibration session including
 * status, uncertainty values, acceptance limit, CMC, and any flags.
 */
function ResultsView() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
      getResults(sessionId)
        .then(data => {
          setResult(data);
          setLoading(false);
        })
        .catch(err => {
          setError(err.message);
          setLoading(false);
        });
    }, [sessionId]);

  if (loading) return <Spinner message="Loading results..." />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 32px" }}>

        {/* Page header */}
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 06
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Validation Results
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Compliance status and uncertainty summary for this session.
          </p>
        </div>

        {error && (
          <div style={{
            padding: "14px 16px",
            background: "#FEF2F2",
            border: "1px solid #FECACA",
            borderRadius: "var(--radius)",
            color: "var(--color-error)",
            fontSize: 13,
            marginBottom: 24,
          }}>
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Status card */}
            <div style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderLeft: "4px solid var(--color-primary)",
              borderRadius: "var(--radius)",
              padding: "20px 24px",
              marginBottom: 16,
              boxShadow: "var(--shadow-sm)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-muted)", marginBottom: 6 }}>
                  Compliance Report
                </p>
                <StatusBadge status={result.status} />
              </div>
            </div>

            {/* Uncertainty values */}
            <div style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              boxShadow: "var(--shadow-sm)",
              overflow: "hidden",
              marginBottom: 16,
            }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "var(--color-primary)" }}>
                    <th style={thStyle}>Parameter</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  <ResultRow
                    label="Final Applied Uncertainty"
                    value={result.final_applied_uncertainty !== null ? `± ${result.final_applied_uncertainty}` : "—"}
                  />
                  <ResultRow
                    label="Acceptance Limit"
                    value={result.acceptance_limit !== null ? result.acceptance_limit : "—"}
                    alt
                  />
                  <ResultRow
                    label="CMC"
                    value={result.cmc !== null ? result.cmc : "—"}
                  />
                </tbody>
              </table>
            </div>

            {/* Flags */}
            {result.flags && result.flags.length > 0 && (
              <div style={{
                background: "#FFFBEB",
                border: "1px solid #FDE68A",
                borderRadius: "var(--radius)",
                padding: "16px 20px",
                marginBottom: 16,
              }}>
                <p style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "#92400E", marginBottom: 10 }}>
                  Flags
                </p>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {result.flags.map((flag, index) => (
                    <li key={index} style={{ fontSize: 13, color: "#78350F", marginBottom: 4 }}>
                      {flag}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
              <button
                onClick={() => navigate(`/report/${sessionId}`)}
                style={{
                  padding: "10px 24px",
                  background: "var(--color-primary)",
                  color: "white",
                  border: "none",
                  borderRadius: "var(--radius)",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--color-primary-hover)"}
                onMouseLeave={e => e.currentTarget.style.background = "var(--color-primary)"}
              >
                Generate Report
              </button>
              <button
                onClick={() => navigate("/history")}
                style={{
                  padding: "10px 24px",
                  background: "white",
                  color: "var(--color-text)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius)",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Back to History
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * ResultRow component.
 * A single labelled row in the results table.
 */
function ResultRow({ label, value, alt }) {
  return (
    <tr style={{ background: alt ? "#F9FAFB" : "white" }}>
      <td style={{ padding: "12px 16px", color: "var(--color-text)", fontWeight: 500 }}>
        {label}
      </td>
      <td style={{ padding: "12px 16px", color: "var(--color-text)", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13 }}>
        {value}
      </td>
    </tr>
  );
}

const thStyle = {
  padding: "12px 16px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "white",
};

export default ResultsView;