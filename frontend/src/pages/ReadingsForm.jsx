import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import SessionPicker from "../components/SessionPicker";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import { isValidDecimalInProgress } from "../utils/numericInput";
import { createReading, getReadings } from "../api";

/**
 * ReadingsForm component.
 * Displays a table for entering ascending and descending calibration readings.
 * Mean error and hysteresis are calculated live on every keystroke.
 * Submits all readings to the backend via createReading from api.js.
 *
 * Reachable two ways:
 *  - Directly from SessionForm with :sessionId already in the URL
 *    (/readings/:sessionId) - behaves exactly as before, no picker shown.
 *  - From the Dashboard card with no session in the URL (/readings) - a
 *    SessionPicker is shown above the form, and all fields/buttons stay
 *    disabled until a session is chosen from the dropdown. Works across
 *    refreshes and new tabs since it relies only on the URL param or the
 *    in-memory picker selection, never localStorage or navigation state.
 *
 * @param {Object} props
 * @param {string} props.uucIndicatorType - The UUC indicator type.
 * @param {string} props.calibrationSequence - The calibration sequence name.
 * @param {number} props.pointCount - Number of calibration points.
 */
function ReadingsForm({
  uucIndicatorType = "",
  calibrationSequence = "",
  pointCount = 5,
}) {
  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

  // pickedSessionId is only ever used when the URL has no :sessionId at
  // all (the Dashboard-card entry point). When urlSessionId is present,
  // effectiveSessionId is always just that - the picker never overrides
  // an explicit URL session.
  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [loadingExisting, setLoadingExisting] = useState(false);

  const initialRows = Array.from({ length: pointCount }, (_, i) => ({
    point_number: i + 1,
    nominal_value: "",
    measured_value_up: "",
    measured_value_down: "",
    mean_error: null,
    hysteresis: null,
  }));

  const [rows, setRows] = useState(initialRows);
  const [autoSelectSequence, setAutoSelectSequence] = useState(true);
  const [autoGeneratePoints, setAutoGeneratePoints] = useState(true);

  // Load any existing readings for the effective session so the form
  // actually reflects that session's data rather than always starting
  // blank - applies whether the session came from the URL or the picker.
  const loadExistingReadings = useCallback(() => {
    if (!effectiveSessionId) return;
    setLoadingExisting(true);
    getReadings(effectiveSessionId)
      .then(existing => {
        if (existing && existing.length > 0) {
          setRows(existing.map(r => ({
            point_number: r.point_number,
            nominal_value: String(r.nominal_value ?? ""),
            measured_value_up: String(r.measured_value_up ?? ""),
            measured_value_down: String(r.measured_value_down ?? ""),
            mean_error: r.mean_error !== null && r.mean_error !== undefined ? String(r.mean_error) : null,
            hysteresis: r.hysteresis !== null && r.hysteresis !== undefined ? String(r.hysteresis) : null,
          })));
        }
        setLoadingExisting(false);
      })
      .catch(() => {
        setLoadingExisting(false);
      });
  }, [effectiveSessionId]);

  useEffect(() => {
    loadExistingReadings();
  }, [loadExistingReadings]);

  function updateRow(index, field, value) {
    setIsDirty(true);
    setRows(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };

      const up = parseFloat(updated[index].measured_value_up);
      const down = parseFloat(updated[index].measured_value_down);
      const nominal = parseFloat(updated[index].nominal_value);

      if (!isNaN(up) && !isNaN(down) && !isNaN(nominal)) {
        updated[index].mean_error = ((up + down) / 2 - nominal).toFixed(4);
      } else {
        updated[index].mean_error = null;
      }

      if (!isNaN(up) && !isNaN(down)) {
        updated[index].hysteresis = Math.abs(up - down).toFixed(4);
      } else {
        updated[index].hysteresis = null;
      }

      return updated;
    });
  }

  function loadDemoData() {
    setRows(prev => prev.map((row, i) => {
      const nominal = (i + 1) * 10;
      const up = nominal + 0.02;
      const down = nominal - 0.01;
      return {
        ...row,
        nominal_value: nominal.toString(),
        measured_value_up: up.toString(),
        measured_value_down: down.toString(),
        mean_error: ((up + down) / 2 - nominal).toFixed(4),
        hysteresis: Math.abs(up - down).toFixed(4),
      };
    }));
  }

  async function handleRecalculate() {
    if (!effectiveSessionId) {
      setSubmitError("No session selected. Please select a session first.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      for (const row of rows) {
        if (!row.nominal_value || !row.measured_value_up || !row.measured_value_down) continue;
        await createReading({
          session_id: effectiveSessionId,
          point_number: row.point_number,
          nominal_value: parseFloat(row.nominal_value),
          measured_value_up: parseFloat(row.measured_value_up),
          measured_value_down: parseFloat(row.measured_value_down),
          reference_value: parseFloat(row.nominal_value),
          correction: 0,
          mean_error: parseFloat(row.mean_error) || 0,
          hysteresis: parseFloat(row.hysteresis) || 0,
        });
      }
      setIsDirty(false);
      navigate(`/calculation/${effectiveSessionId}`);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  const formDisabled = !effectiveSessionId;

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 04
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Calibration Readings
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Record ascending and descending measurements for each calibration point.
          </p>
        </div>

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} />
        )}

        <div style={{ opacity: formDisabled ? 0.5 : 1, transition: "opacity 0.15s" }}>

          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "20px 24px", boxShadow: "var(--shadow-sm)", marginBottom: 16 }}>
            <div style={{ display: "flex", gap: 32, marginBottom: 16 }}>
              <ReadOnlyField label="UUC Indicator Type" value={uucIndicatorType} />
              <ReadOnlyField label="Calibration Sequence" value={calibrationSequence} />
            </div>
            <div style={{ display: "flex", gap: 24 }}>
              <CheckboxField id="auto-sequence" label="Auto-select Sequence from UUC Accuracy" checked={autoSelectSequence} onChange={setAutoSelectSequence} disabled={formDisabled} />
              <CheckboxField id="auto-points" label="Auto-generate points from UUC range" checked={autoGeneratePoints} onChange={setAutoGeneratePoints} disabled={formDisabled} />
            </div>
          </div>

          <div style={{ background: "#F0F4FF", border: "1px solid #C7D7FF", borderRadius: "var(--radius)", padding: "10px 16px", marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
            <span style={{ color: "var(--color-primary)", fontWeight: 500 }}>
              {calibrationSequence || "No sequence selected"}
            </span>
            <button onClick={loadDemoData} disabled={formDisabled} style={{ background: "none", border: "none", color: "var(--color-accent)", cursor: formDisabled ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 500 }}>
              Load Demo Data
            </button>
          </div>

          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-sm)", overflow: "hidden", marginBottom: 20 }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "var(--color-primary)" }}>
                    <th style={thStyle}>Pt</th>
                    <th style={thStyle}>Nominal Std</th>
                    <th style={thStyle}>S1 Up</th>
                    <th style={thStyle}>S1 Down</th>
                    <th style={thStyle}>Mean Error</th>
                    <th style={thStyle}>Hysteresis</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={index} style={{ background: index % 2 === 0 ? "white" : "#F9FAFB", borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--color-accent)" }}>
                        {String(row.point_number).padStart(2, "0")}
                      </td>
                      <td style={tdStyle}><input type="text" inputMode="decimal" value={row.nominal_value} disabled={formDisabled} onChange={e => { if (isValidDecimalInProgress(e.target.value)) updateRow(index, "nominal_value", e.target.value); }} style={inputStyle} /></td>
                      <td style={tdStyle}><input type="text" inputMode="decimal" value={row.measured_value_up} disabled={formDisabled} onChange={e => { if (isValidDecimalInProgress(e.target.value)) updateRow(index, "measured_value_up", e.target.value); }} style={inputStyle} /></td>
                      <td style={tdStyle}><input type="text" inputMode="decimal" value={row.measured_value_down} disabled={formDisabled} onChange={e => { if (isValidDecimalInProgress(e.target.value)) updateRow(index, "measured_value_down", e.target.value); }} style={inputStyle} /></td>
                      <td style={{ ...tdStyle, textAlign: "center", fontFamily: "var(--font-mono)", color: row.mean_error !== null ? "var(--color-text)" : "var(--color-muted)" }}>
                        {row.mean_error !== null ? `±${row.mean_error}` : "—"}
                      </td>
                      <td style={{ ...tdStyle, textAlign: "center", fontFamily: "var(--font-mono)", color: row.hysteresis !== null ? "var(--color-text)" : "var(--color-muted)" }}>
                        {row.hysteresis !== null ? row.hysteresis : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {submitError && (
            <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 12 }}>
              {submitError}
            </p>
          )}

          <div style={{ display: "flex", gap: 12 }}>
            <button
              onClick={handleRecalculate}
              disabled={isSubmitting || formDisabled}
              style={{
                flex: 1, padding: "13px",
                background: (isSubmitting || formDisabled) ? "var(--color-border)" : "var(--color-primary)",
                color: "white", border: "none", borderRadius: "var(--radius)",
                fontSize: 14, fontWeight: 600,
                cursor: (isSubmitting || formDisabled) ? "not-allowed" : "pointer",
                letterSpacing: "0.02em",
              }}
              onMouseEnter={e => { if (!isSubmitting && !formDisabled) e.currentTarget.style.background = "var(--color-primary-hover)"; }}
              onMouseLeave={e => { if (!isSubmitting && !formDisabled) e.currentTarget.style.background = "var(--color-primary)"; }}
            >
              {isSubmitting ? "Saving Readings..." : loadingExisting ? "Loading..." : "Recalculate Metrology Uncertainty"}
            </button>
            <button
              onClick={() => safeNavigate("/dashboard")}
              style={{ padding: "13px 20px", background: "white", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", fontSize: 14, fontWeight: 500, cursor: "pointer" }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div style={{ flex: 1 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-muted)", marginBottom: 6 }}>{label}</label>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{value || "—"}</div>
    </div>
  );
}

function CheckboxField({ id, label, checked, onChange, disabled }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <input type="checkbox" id={id} checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} style={{ accentColor: "var(--color-primary)", width: 14, height: 14 }} />
      <label htmlFor={id} style={{ fontSize: 13, color: "var(--color-text)", cursor: disabled ? "not-allowed" : "pointer" }}>{label}</label>
    </div>
  );
}

const thStyle = {
  padding: "12px 16px", textAlign: "left", fontWeight: 600,
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "white",
};

const tdStyle = { padding: "8px 12px", color: "var(--color-text)" };

const inputStyle = {
  width: "100%", padding: "6px 10px", border: "1px solid var(--color-border)",
  borderRadius: "var(--radius)", fontSize: 13, fontFamily: "var(--font-mono)",
  background: "white", boxSizing: "border-box",
};

export default ReadingsForm;