import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Spinner from "../components/Spinner";
import SessionPicker from "../components/SessionPicker";
import {
  getUncertaintyBudgets,
  calculateUncertainty,
  getTemperatureRepeatabilityTests,
  getElectricalTests,
} from "../api";

// Every possible uncertainty budget field, across all categories, with a
// human-readable label. Each category populates a different subset (see
// calculation_engine.py's build_* functions) - only fields actually
// present (not null/undefined) in a given budget are rendered.
const COMPONENT_FIELDS = [
  { key: "type_a_value", label: "Type A Uncertainty", group: "type_a" },
  { key: "u_std", label: "Standard's Uncertainty (u_std)", group: "type_b" },
  { key: "u_std_accuracy", label: "Standard's Accuracy Uncertainty (u_std_accuracy)", group: "type_b" },
  { key: "u_res", label: "Resolution Uncertainty (u_res)", group: "type_b" },
  { key: "u_hys", label: "Hysteresis Uncertainty (u_hys)", group: "type_b" },
  { key: "u_zero", label: "Zero Error Uncertainty (u_zero)", group: "type_b" },
  { key: "u_head", label: "Medium Head Correction (u_head)", group: "type_b" },
  { key: "u_temp", label: "Temperature Influence (u_temp)", group: "type_b" },
  { key: "u_repeatability", label: "Repeatability Uncertainty (u_repeatability)", group: "type_b" },
  { key: "u_std_weights", label: "Standard Weights Uncertainty (u_std_weights)", group: "type_b" },
  { key: "u_eccentric", label: "Eccentric Loading Uncertainty (u_eccentric)", group: "type_b" },
  { key: "u_drift", label: "Drift of Standard Uncertainty (u_drift)", group: "type_b" },
  { key: "u_bath_stability", label: "Bath Stability Uncertainty (u_bath_stability)", group: "type_b" },
  { key: "u_bath_uniformity", label: "Bath Uniformity Uncertainty (u_bath_uniformity)", group: "type_b" },
  { key: "u_wire_homogeneity", label: "Wire Homogeneity Uncertainty (u_wire_homogeneity)", group: "type_b" },
  { key: "u_b1", label: "Type B Component 1 (u_b1)", group: "type_b" },
  { key: "u_b2", label: "Type B Component 2 (u_b2)", group: "type_b" },
  { key: "u_b3", label: "Type B Component 3 (u_b3)", group: "type_b" },
  { key: "u_b4", label: "Type B Component 4 (u_b4)", group: "type_b" },
];

const SUMMARY_FIELDS = [
  { key: "combined_uncertainty", label: "Combined Uncertainty (Uc)" },
  { key: "k_value", label: "Coverage Factor (k)" },
  { key: "expanded_uncertainty", label: "Expanded Uncertainty (U)" },
  { key: "cmc", label: "Claimed Measurement Capability (CMC)" },
  { key: "final_applied_uncertainty", label: "Final Applied Uncertainty" },
];

/**
 * CalculationView component.
 * Fetches all existing uncertainty budgets for a session if any exist, or
 * offers to calculate them via POST /api/sessions/{id}/calculate. Always
 * a list now - Pressure/Weighing sessions get exactly one (rendered
 * exactly as before, no visual change for the common case); Temperature
 * (one per setpoint) and Electrical (one per function-type/range) can
 * have several, each rendered as its own card with a friendly label
 * (setpoint name, or function type + range) fetched separately from
 * whichever test-data endpoint applies.
 *
 * An empty list means "not calculated yet" - this used to be detected by
 * catching a 404 with a specific message; the backend now just returns
 * an empty array for this case, so no error handling is needed for it.
 *
 * Reachable two ways:
 *  - Directly from ReadingsForm with :sessionId already in the URL
 *    (/calculation/:sessionId) - behaves exactly as before, no picker shown.
 *  - From the Dashboard card with no session in the URL (/calculation) -
 *    a SessionPicker is shown above the content, and the Calculate/
 *    Recalculate/Continue buttons stay disabled until a session is
 *    chosen. Works across refreshes and new tabs - relies only on the
 *    URL param or the in-memory picker selection.
 */
function CalculationView() {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();

  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [budgets, setBudgets] = useState([]);
  const [labelMap, setLabelMap] = useState({});
  const [loading, setLoading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);

  const loadExistingBudgets = useCallback(() => {
    if (!effectiveSessionId) {
      setBudgets([]);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    getUncertaintyBudgets(effectiveSessionId)
      .then(data => {
        setBudgets(data || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [effectiveSessionId]);

  useEffect(() => {
    loadExistingBudgets();
  }, [loadExistingBudgets]);

  // Fetch friendly per-budget labels (setpoint name, or function type +
  // range) when there's more than one budget - not needed for the common
  // Pressure/Weighing/single-item case, and cheap to skip otherwise.
  useEffect(() => {
    if (budgets.length <= 1 || !effectiveSessionId) {
      setLabelMap({});
      return;
    }
    const first = budgets[0];
    if (first.temperature_test_id) {
      getTemperatureRepeatabilityTests(effectiveSessionId).then(tests => {
        const map = {};
        (tests || []).forEach(t => { map[t.id] = `Setpoint: ${t.setpoint_label}`; });
        setLabelMap(map);
      }).catch(() => setLabelMap({}));
    } else if (first.electrical_test_id) {
      getElectricalTests(effectiveSessionId).then(tests => {
        const map = {};
        (tests || []).forEach(t => { map[t.id] = `${t.function_type} — ${t.range_label}`; });
        setLabelMap(map);
      }).catch(() => setLabelMap({}));
    } else {
      setLabelMap({});
    }
  }, [budgets, effectiveSessionId]);

  function handleCalculate() {
    if (!effectiveSessionId) return;
    setCalculating(true);
    setError(null);
    calculateUncertainty(effectiveSessionId)
      .then(data => {
        setBudgets(data || []);
        setCalculating(false);
      })
      .catch(err => {
        setError(err.message);
        setCalculating(false);
      });
  }

  function labelFor(budget) {
    const testId = budget.temperature_test_id || budget.electrical_test_id;
    return labelMap[testId] || null;
  }

  const noSessionSelected = !effectiveSessionId;
  const notYetCalculated = !loading && budgets.length === 0;

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

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} />
        )}

        <div style={{ opacity: noSessionSelected ? 0.5 : 1, transition: "opacity 0.15s" }}>

          {loading && <Spinner message="Checking for an existing calculation..." />}

          {error && (
            <div style={{
              padding: "14px 16px", background: "#FEF2F2", border: "1px solid #FECACA",
              borderRadius: "var(--radius)", color: "var(--color-error)", fontSize: 13,
              marginBottom: 24, lineHeight: 1.5,
            }}>
              {error}
            </div>
          )}

          {!loading && (notYetCalculated || noSessionSelected) && (
            <div style={{
              background: "var(--color-surface)", border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)", padding: "32px", textAlign: "center",
              boxShadow: "var(--shadow-sm)",
            }}>
              <p style={{ color: "var(--color-muted)", fontSize: 14, marginBottom: 20 }}>
                {noSessionSelected
                  ? "Select a session above to check for or run its uncertainty calculation."
                  : "No uncertainty budget has been calculated for this session yet."}
              </p>
              <CalculateButton onClick={handleCalculate} calculating={calculating} disabled={noSessionSelected} label="Calculate Uncertainty Budget" />
            </div>
          )}

          {!loading && budgets.length > 0 && (
            <>
              {budgets.map((budget, index) => {
                const label = labelFor(budget);
                const presentComponentFields = COMPONENT_FIELDS.filter(
                  f => budget[f.key] !== null && budget[f.key] !== undefined
                );
                return (
                  <div key={budget.temperature_test_id || budget.electrical_test_id || index} style={{ marginBottom: 20 }}>
                    {budgets.length > 1 && (
                      <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--color-primary)", marginBottom: 12 }}>
                        {label || `Budget ${index + 1} of ${budgets.length}`}
                      </h2>
                    )}
                    <div style={{
                      background: "var(--color-surface)", border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius)", padding: "24px", marginBottom: 20,
                      boxShadow: "var(--shadow-sm)",
                    }}>
                      <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-primary)", marginBottom: 16 }}>
                        Uncertainty Components
                      </h3>
                      <ComponentTable fields={presentComponentFields} budget={budget} />
                    </div>

                    <div style={{
                      background: "var(--color-surface)", border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius)", padding: "24px",
                      boxShadow: "var(--shadow-sm)",
                    }}>
                      <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-primary)", marginBottom: 16 }}>
                        Summary
                      </h3>
                      <ComponentTable fields={SUMMARY_FIELDS} budget={budget} highlightKey="final_applied_uncertainty" />
                    </div>
                  </div>
                );
              })}

              <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                <CalculateButton onClick={handleCalculate} calculating={calculating} disabled={noSessionSelected} label="Recalculate" secondary />
                <button
                  onClick={() => navigate(`/results/${effectiveSessionId}`)}
                  disabled={noSessionSelected}
                  style={{
                    padding: "11px 24px",
                    background: noSessionSelected ? "var(--color-border)" : "var(--color-primary)",
                    color: "white", border: "none", borderRadius: "var(--radius)",
                    fontWeight: 600, fontSize: 14,
                    cursor: noSessionSelected ? "not-allowed" : "pointer",
                  }}
                >
                  Continue to Results
                </button>
              </div>
            </>
          )}
        </div>
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
                padding: "10px 4px", textAlign: "right", fontFamily: "var(--font-mono)",
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
  return value.toPrecision(6).replace(/\.?0+$/, "").replace(/\.$/, "");
}

function CalculateButton({ onClick, calculating, disabled, label, secondary = false }) {
  const isDisabled = calculating || disabled;
  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      style={{
        padding: "11px 24px",
        background: isDisabled ? "var(--color-border)" : (secondary ? "white" : "var(--color-primary)"),
        color: isDisabled ? "var(--color-muted)" : (secondary ? "var(--color-text)" : "white"),
        border: secondary ? "1px solid var(--color-border)" : "none",
        borderRadius: "var(--radius)", fontWeight: 600, fontSize: 14,
        cursor: isDisabled ? "not-allowed" : "pointer",
        opacity: calculating ? 0.6 : 1,
      }}
    >
      {calculating ? "Calculating..." : label}
    </button>
  );
}

export default CalculationView;