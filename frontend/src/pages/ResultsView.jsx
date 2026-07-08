import { getResults } from "../api";
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";
import Spinner from "../components/Spinner";
import SessionPicker from "../components/SessionPicker";

/**
 * ResultsView component.
 * Displays the validation result for a calibration session: overall
 * compliance status, acceptance limit, and a per-budget breakdown.
 *
 * Pressure/Weighing sessions have exactly one budget, shown as a single
 * summary table (same layout as before this component supported multiple
 * budgets). Temperature (one per setpoint) and Electrical (one per
 * function-type/range) can have several - each gets its own row, with
 * whichever specific setpoint/range caused a REJECTED or REVIEW REQUIRED
 * result visually highlighted, not just named in a flag buried in a list.
 * The overall session status is "worst case wins" across every budget
 * (see validation.py) - a single failing setpoint/range is enough to
 * make the whole session non-ACCEPTED, so surfacing exactly which one
 * failed is the most useful thing this screen can show.
 *
 * Reachable two ways:
 *  - Directly from CalculationView with :sessionId already in the URL
 *    (/results/:sessionId) - behaves exactly as before, no picker shown.
 *  - From the Dashboard card with no session in the URL (/results) - a
 *    SessionPicker is shown above the content, and Generate Report stays
 *    disabled until a session is chosen. Works across refreshes and new
 *    tabs - relies only on the URL param or the in-memory picker
 *    selection, never localStorage or navigation state.
 */
function ResultsView() {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();

  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadResults = useCallback(() => {
    if (!effectiveSessionId) {
      setResult(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    getResults(effectiveSessionId)
      .then(data => {
        setResult(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [effectiveSessionId]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const noSessionSelected = !effectiveSessionId;

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 32px" }}>

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

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} />
        )}

        {loading && <Spinner message="Loading results..." />}

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

        {!loading && noSessionSelected && !result && (
          <div style={{
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)", padding: "32px", textAlign: "center",
            boxShadow: "var(--shadow-sm)",
          }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
              Select a session above to view its validation results.
            </p>
          </div>
        )}

        <div style={{ opacity: noSessionSelected ? 0.5 : 1, transition: "opacity 0.15s" }}>
          {result && (
            <>
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
                      {result.budgets && result.budgets.length > 1 && (
                        <th style={thStyle}>Setpoint / Range</th>
                      )}
                      <th style={thStyle}>Status</th>
                      <th style={{ ...thStyle, textAlign: "right" }}>Final Applied Uncertainty</th>
                      <th style={{ ...thStyle, textAlign: "right" }}>CMC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result.budgets || []).map((budget, index) => {
                      const isFailing = budget.status !== "ACCEPTED";
                      return (
                        <tr
                          key={index}
                          style={{
                            background: isFailing ? "#FEF2F2" : (index % 2 === 1 ? "#F9FAFB" : "white"),
                            borderLeft: isFailing ? "3px solid var(--color-error)" : "3px solid transparent",
                          }}
                        >
                          {result.budgets.length > 1 && (
                            <td style={{ padding: "12px 16px", fontWeight: 500, color: "var(--color-text)" }}>
                              {budget.identifier || `Item ${index + 1}`}
                            </td>
                          )}
                          <td style={{ padding: "12px 16px" }}>
                            <StatusBadge status={budget.status} />
                          </td>
                          <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                            {budget.final_applied_uncertainty !== null && budget.final_applied_uncertainty !== undefined
                              ? `± ${budget.final_applied_uncertainty}`
                              : "—"}
                          </td>
                          <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                            {budget.cmc !== null && budget.cmc !== undefined ? budget.cmc : "—"}
                          </td>
                        </tr>
                      );
                    })}
                    <ResultRow
                      label="Acceptance Limit"
                      value={result.acceptance_limit !== null ? result.acceptance_limit : "—"}
                      alt
                    />
                  </tbody>
                </table>
              </div>

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

              <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
                <button
                  onClick={() => navigate(`/report/${effectiveSessionId}`)}
                  disabled={noSessionSelected}
                  style={{
                    padding: "10px 24px",
                    background: noSessionSelected ? "var(--color-border)" : "var(--color-primary)",
                    color: "white",
                    border: "none",
                    borderRadius: "var(--radius)",
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: noSessionSelected ? "not-allowed" : "pointer",
                  }}
                  onMouseEnter={e => { if (!noSessionSelected) e.currentTarget.style.background = "var(--color-primary-hover)"; }}
                  onMouseLeave={e => { if (!noSessionSelected) e.currentTarget.style.background = "var(--color-primary)"; }}
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