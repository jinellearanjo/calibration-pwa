import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Spinner from "../components/Spinner";
import { getUncertaintyBudget, calculateUncertainty } from "../api";

// Every possible uncertainty budget field, across all categories, with a
// human-readable label. Pressure and Weighing populate different subsets
// of these (see calculation_engine.py's build_pressure_uncertainty_budget
// vs build_weighing_uncertainty_budget) - only fields actually present
// (not null/undefined) in the returned budget are rendered, so this list
// doubles as documentation for what a full budget could ever contain.
const COMPONENT_FIELDS = [
  { key: "type_a_value", label: "Type A Uncertainty", group: "type_a" },
  { key: "u_std", label: "Standard's Uncertainty (u_std)", group: "type_b" },
  { key: "u_res", label: "Resolution Uncertainty (u_res)", group: "type_b" },
  { key: "u_hys", label: "Hysteresis Uncertainty (u_hys)", group: "type_b" },
  { key: "u_zero", label: "Zero Error Uncertainty (u_zero)", group: "type_b" },
  { key: "u_head", label: "Medium Head Correction (u_head)", group: "type_b" },
  { key: "u_temp", label: "Temperature Influence (u_temp)", group: "type_b" },
  { key: "u_std_weights", label: "Standard Weights Uncertainty (u_std_weights)", group: "type_b" },
  { key: "u_eccentric", label: "Eccentric Loading Uncertainty (u_eccentric)", group: "type_b" },
];

const SUMMARY_FIELDS = [
  { key: "combined_uncertainty", label: "Combined Uncertainty (Uc)" },
  { key: "k_value", label: "Coverage Factor (k)" },
  { key: "expanded_uncertainty", label: "Expanded Uncertainty (U)" },
  { key: "cmc", label: "Claimed Measurement Capability (CMC)" },
  { key: "final_applied_uncertainty", label: "Final Applied Uncertainty" },
];

// The exact message main.py's GET /budget endpoint returns when no budget
// exists yet for a session. Matched against here to distinguish "not
// calculated yet, that's fine" from a real error - api.js's request()
// helper doesn't currently preserve HTTP status codes on thrown errors,
// only the detail message, so string matching is the pragmatic option
// without a broader api.js refactor.
const NOT_YET_CALCULATED_MESSAGE = "Uncertainty budget not found.";

/**
 * CalculationView component.
 * Fetches an existing uncertainty budget for a session if one exists, or
 * offers to calculate one via POST /api/sessions/{id}/calculate. Displays
 * the full component breakdown once available, with fields shown only if
 * present - Pressure and Weighing populate different subsets of
 * COMPONENT_FIELDS, and Temperature/Electrical currently return a 501 from
 * the backend, surfaced here as a clear "not yet available" message rather
 * than a generic error.
 */
function CalculationView() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [budget, setBudget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);
  const [notYetCalculated, setNotYetCalculated] = useState(false);

  const loadExistingBudget = useCallback(() => {
    setLoading(true);
    setError(null);
    getUncertaintyBudget(sessionId)
      .then(data => {
        setBudget(data);
        setNotYetCalculated(false);
        setLoading(false);
      })
      .catch(err => {
        if (err.message === NOT_YET_CALCULATED_MESSAGE) {
          setNotYetCalculated(true);
        } else {
          setError(err.message);
        }
        setLoading(false);
      });
  }, [sessionId]);

  useEffect(() => {
    loadExistingBudget();
  }, [loadExistingBudget]);

  function handleCalculate() {
    setCalculating(true);
    setError(null);
    calculateUncertainty(sessionId)
      .then(data => {
        setBudget(data);
        setNotYetCalculated(false);
        setCalculating(false);
      })
      .catch(err => {
        setError(err.message);
        setCalculating(false);
      });
  }

  if (loading) return <Spinner message="Checking for an existing calculation..." />;

  const presentComponentFields = budget
    ? COMPONENT_FIELDS.filter(f => budget[f.key] !== null && budget[f.key] !== undefined)
    : [];

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 05
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Uncertainty Calculation
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            GUM-compliant uncertainty budget for this calibration session.
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
            lineHeight: 1.5,
          }}>
            {error}
          </div>
        )}

        {notYetCalculated && !budget && (
          <div style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)",
            padding: "32px",
            textAlign: "center",
            boxShadow: "var(--shadow-sm)",
          }}>
            <p style={{ color: "var(--color-muted)", fontSize: 14, marginBottom: 20 }}>
              No uncertainty budget has been calculated for this session yet.
            </p>
            <CalculateButton onClick={handleCalculate} calculating={calculating} label="Calculate Uncertainty Budget" />
          </div>
        )}

        {budget && (
          <>
            <div style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              padding: "24px",
              marginBottom: 20,
              boxShadow: "var(--shadow-sm)",
            }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-primary)", marginBottom: 16 }}>
                Uncertainty Components
              </h3>
              <ComponentTable fields={presentComponentFields} budget={budget} />
            </div>

            <div style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              padding: "24px",
              marginBottom: 24,
              boxShadow: "var(--shadow-sm)",
            }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-primary)", marginBottom: 16 }}>
                Summary
              </h3>
              <ComponentTable fields={SUMMARY_FIELDS} budget={budget} highlightKey="final_applied_uncertainty" />
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              <CalculateButton onClick={handleCalculate} calculating={calculating} label="Recalculate" secondary />
              <button
                onClick={() => navigate(`/results/${sessionId}`)}
                style={{
                  padding: "11px 24px",
                  background: "var(--color-primary)",
                  color: "white",
                  border: "none",
                  borderRadius: "var(--radius)",
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: "pointer",
                }}
              >
                Continue to Results
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ComponentTable({ fields, budget, highlightKey }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <tbody>
        {fields.map(f => {
          const value = budget[f.key];
          const isHighlighted = f.key === highlightKey;
          return (
            <tr key={f.key} style={{ borderTop: "1px solid var(--color-border)" }}>
              <td style={{
                padding: "10px 4px",
                color: isHighlighted ? "var(--color-primary)" : "var(--color-text)",
                fontWeight: isHighlighted ? 600 : 400,
              }}>
                {f.label}
              </td>
              <td style={{
                padding: "10px 4px",
                textAlign: "right",
                fontFamily: "var(--font-mono)",
                color: isHighlighted ? "var(--color-primary)" : "var(--color-text)",
                fontWeight: isHighlighted ? 700 : 400,
              }}>
                {formatValue(value)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function formatValue(value) {
  if (typeof value !== "number") return String(value);
  // 6 significant figures is generous enough for uncertainty values that
  // range from sub-milligram (weighing) to multi-bar (pressure) without
  // truncating small values to 0.00.
  return value.toPrecision(6).replace(/\.?0+$/, "").replace(/\.$/, "");
}

function CalculateButton({ onClick, calculating, label, secondary = false }) {
  return (
    <button
      onClick={onClick}
      disabled={calculating}
      style={{
        padding: "11px 24px",
        background: secondary ? "white" : "var(--color-primary)",
        color: secondary ? "var(--color-text)" : "white",
        border: secondary ? "1px solid var(--color-border)" : "none",
        borderRadius: "var(--radius)",
        fontWeight: 600,
        fontSize: 14,
        cursor: calculating ? "not-allowed" : "pointer",
        opacity: calculating ? 0.6 : 1,
      }}
    >
      {calculating ? "Calculating..." : label}
    </button>
  );
}

export default CalculationView;