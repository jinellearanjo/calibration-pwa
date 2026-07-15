import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import SessionPicker from "../components/SessionPicker";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import { decimalInputHandler, isValidDecimalInProgress } from "../utils/numericInput";
import {
  createTemperatureRepeatabilityTest,
  getTemperatureRepeatabilityTests,
  getSession,
  getInstrument,
} from "../api";

/**
 * TemperatureReadingsForm component.
 * Data entry for Temperature calibration: one repeatability test per
 * setpoint (e.g. -15C, 110C, 300C, 650C), each with 3 repeated readings
 * plus the Type B component values (Ub1, Ub2, Ub3, Ub5, Ub6, Ub7, and
 * Ub8 for TCK sub-type only). Unlike Weighing's fixed 3 load points,
 * the number of setpoints tested varies per instrument/calibration
 * scope, so setpoints are added/removed dynamically rather than being
 * a fixed list.
 *
 * Each setpoint gets its own uncertainty_budgets row (via
 * uncertainty_budgets.temperature_test_id) - formula_manager.py's
 * _build_temperature_budgets (plural) loops over every setpoint's test
 * data and returns one budget per setpoint, so there's no limit on how
 * many setpoints a session can have.
 *
 * Reachable two ways, same pattern as ReadingsForm.jsx:
 *  - Directly with :sessionId already in the URL (/readings/temperature/:sessionId)
 *    from SessionForm's post-creation routing - no picker shown.
 *  - From a bare route with no session (/readings/temperature) - a
 *    SessionPicker is shown above the form and all fields/buttons stay
 *    disabled until a session is chosen. Relies only on the URL param
 *    or in-memory picker state, never localStorage or navigation state.
 *
 * The instrument's sub-type (TCK/RTD/DTI/DryBlock) is resolved via the
 * session's linked instrument, since only TCK needs the wire homogeneity
 * (Ub8) field - see calculation_engine.py and formulas/temperature.json.
 */
function TemperatureReadingsForm() {
  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [subtype, setSubtype] = useState(null);
  const [subtypeError, setSubtypeError] = useState("");
  const [loadingInstrument, setLoadingInstrument] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [setpoints, setSetpoints] = useState([newSetpoint(0)]);
  const [submitError, setSubmitError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Resolve the instrument's sub-type for the effective session - needed
  // to know whether to show the TCK-only wire homogeneity (Ub8) field.
  useEffect(() => {
    if (!effectiveSessionId) {
      setSubtype(null);
      return;
    }
    let cancelled = false;
    setLoadingInstrument(true);
    setSubtypeError("");
    getSession(effectiveSessionId)
      .then(session => getInstrument(session.instrument_id))
      .then(instrument => {
        if (cancelled) return;
        setSubtype(instrument?.instrument_subtype || null);
        if (!instrument?.instrument_subtype) {
          setSubtypeError("This instrument has no sensor sub-type set. Register it via Step 01 before entering readings.");
        }
      })
      .catch(err => {
        if (!cancelled) setSubtypeError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingInstrument(false);
      });
    return () => { cancelled = true; };
  }, [effectiveSessionId]);

  // Load any already-saved setpoints for this session so reopening the
  // form reflects existing data rather than always starting blank.
  const loadExisting = useCallback(() => {
    if (!effectiveSessionId) return;
    setLoadingExisting(true);
    getTemperatureRepeatabilityTests(effectiveSessionId)
      .then(existing => {
        if (existing && existing.length > 0) {
          setSetpoints(existing.map(hydrateSetpoint));
        }
        setLoadingExisting(false);
      })
      .catch(() => setLoadingExisting(false));
  }, [effectiveSessionId]);

  useEffect(() => {
    loadExisting();
  }, [loadExisting]);

  function updateSetpointField(index, field, value) {
    setIsDirty(true);
    setSetpoints(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  }

  function updateReading(spIndex, readingIndex, value) {
    setIsDirty(true);
    setSetpoints(prev => {
      const updated = [...prev];
      const readings = [...updated[spIndex].readings];
      readings[readingIndex] = { reading_value: value };
      updated[spIndex] = { ...updated[spIndex], readings };
      return updated;
    });
  }

  function addSetpoint() {
    setIsDirty(true);
    setSetpoints(prev => [...prev, newSetpoint(prev.length)]);
  }

  function removeSetpoint(index) {
    setIsDirty(true);
    setSetpoints(prev => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function setpointComplete(sp) {
    if (!sp.setpoint_label.trim() || sp.nominal_temperature === "") return false;
    return sp.readings.every(r => r.reading_value !== "");
  }

  const allComplete = setpoints.length > 0 && setpoints.every(setpointComplete);
  const formDisabled = !effectiveSessionId;
  const canSubmit = allComplete && !isSubmitting && !formDisabled;

  async function handleSubmit() {
    if (!effectiveSessionId) {
      setSubmitError("No session selected. Please select a session first.");
      return;
    }
    setSubmitError("");
    setIsSubmitting(true);
    try {
      for (const sp of setpoints) {
        const testPayload = {
          // session_id must be included here even though the backend also
          // sets it from the URL - FastAPI validates the request body
          // against TemperatureRepeatabilityTestCreate (which requires
          // session_id) before the endpoint's own override ever runs.
          // Verified empirically; see api.js's createTemperatureRepeatabilityTest.
          session_id: effectiveSessionId,
          setpoint_label: sp.setpoint_label.trim(),
          nominal_temperature: Number(sp.nominal_temperature),
          unit: sp.unit || "C",
          standard_uncertainty: sp.standard_uncertainty === "" ? null : Number(sp.standard_uncertainty),
          standard_accuracy: sp.standard_accuracy === "" ? null : Number(sp.standard_accuracy),
          drift_standard_uncertainty: sp.drift_standard_uncertainty === "" ? null : Number(sp.drift_standard_uncertainty),
          hysteresis_value: sp.hysteresis_value === "" ? null : Number(sp.hysteresis_value),
          bath_stability_value: sp.bath_stability_value === "" ? null : Number(sp.bath_stability_value),
          bath_uniformity_value: sp.bath_uniformity_value === "" ? null : Number(sp.bath_uniformity_value),
          wire_homogeneity_value:
            subtype === "TCK" && sp.wire_homogeneity_value !== ""
              ? Number(sp.wire_homogeneity_value)
              : null,
        };
        const readingsPayload = sp.readings.map((r, i) => ({
          reading_number: i + 1,
          reading_value: Number(r.reading_value),
        }));
        await createTemperatureRepeatabilityTest(effectiveSessionId, testPayload, readingsPayload);
      }
      setIsDirty(false);
      navigate(`/calculation/${effectiveSessionId}`);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 820, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 04 — Temperature
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Temperature Test Data
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Enter one repeatability test per setpoint tested. Each setpoint needs 3 repeated
            readings plus the standard, drift, and bath uncertainty values from the master
            instrument's certificate.
          </p>
        </div>

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} categoryFilter="Temperature" />
        )}

        <div style={{ opacity: formDisabled ? 0.5 : 1, transition: "opacity 0.15s" }}>

          <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "16px 24px", boxShadow: "var(--shadow-sm)", marginBottom: 20, display: "flex", alignItems: "center", gap: 32 }}>
            <ReadOnlyField
              label="Sensor Sub-Type"
              value={loadingInstrument ? "Loading..." : (subtype || "—")}
            />
            {subtype === "TCK" && (
              <p style={{ fontSize: 12, color: "var(--color-muted)", margin: 0 }}>
                TCK adds an extra Wire Homogeneity (Ub8) field to each setpoint below.
              </p>
            )}
          </div>

          {subtypeError && !loadingInstrument && (
            <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 16 }}>
              {subtypeError}
            </p>
          )}

          {loadingExisting && (
            <p style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 16 }}>
              Loading existing setpoints...
            </p>
          )}

          {setpoints.map((sp, index) => (
            <SetpointCard
              key={sp.key}
              index={index}
              setpoint={sp}
              subtype={subtype}
              canRemove={setpoints.length > 1}
              formDisabled={formDisabled}
              onFieldChange={(field, value) => updateSetpointField(index, field, value)}
              onReadingChange={(readingIndex, value) => updateReading(index, readingIndex, value)}
              onRemove={() => removeSetpoint(index)}
            />
          ))}

          <button
            onClick={addSetpoint}
            disabled={formDisabled}
            style={{
              padding: "10px 18px",
              background: "white",
              color: "var(--color-primary)",
              border: "1px dashed var(--color-primary)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              fontWeight: 600,
              cursor: formDisabled ? "not-allowed" : "pointer",
              marginBottom: 24,
            }}
          >
            + Add Setpoint
          </button>

          {setpoints.length > 1 && (
            <p style={{ color: "var(--color-accent)", fontSize: 13, marginBottom: 16, marginTop: -12 }}>
              Note: all setpoints will be saved and shown on the certificate, but the
              uncertainty calculation currently only supports one setpoint per session
              — calculating a budget will fail with multiple setpoints saved here.
              Keep to a single setpoint per session until multi-setpoint budgets are supported.
            </p>
          )}

          {submitError && (
            <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 12 }}>
              {submitError}
            </p>
          )}

          <div style={{ display: "flex", gap: 12 }}>
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              style={{
                flex: 1, padding: "13px",
                background: canSubmit ? "var(--color-primary)" : "var(--color-border)",
                color: "white", border: "none", borderRadius: "var(--radius)",
                fontSize: 14, fontWeight: 600,
                cursor: canSubmit ? "pointer" : "not-allowed",
                letterSpacing: "0.02em",
              }}
            >
              {isSubmitting ? "Saving..." : "Save Setpoints & Continue to Calculation"}
            </button>
            <button
              onClick={() => safeNavigate("/dashboard")}
              style={{ padding: "13px 20px", background: "white", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", fontSize: 14, fontWeight: 500, cursor: "pointer" }}
            >
              Save &amp; Exit
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SetpointCard({ index, setpoint, subtype, canRemove, formDisabled, onFieldChange, onReadingChange, onRemove }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        padding: "24px",
        marginBottom: 20,
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--color-primary)", margin: 0 }}>
          Setpoint {index + 1}
        </h3>
        {canRemove && (
          <button
            onClick={onRemove}
            disabled={formDisabled}
            style={{ background: "none", border: "none", color: "var(--color-error)", fontSize: 12, fontWeight: 500, cursor: formDisabled ? "not-allowed" : "pointer" }}
          >
            Remove
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        <SmallField
          id={`setpoint-${index}-setpoint_label`}
          label="Setpoint Label"
          value={setpoint.setpoint_label}
          onChange={v => onFieldChange("setpoint_label", v)}
          disabled={formDisabled}
          placeholder="e.g. minus_15c"
        />
        <SmallField
          id={`setpoint-${index}-nominal_temperature`}
          label="Nominal Temperature"
          value={setpoint.nominal_temperature}
          onChange={v => onFieldChange("nominal_temperature", v)}
          type="number"
          disabled={formDisabled}
        />
        <SmallField
          id={`setpoint-${index}-unit`}
          label="Unit"
          value={setpoint.unit}
          onChange={v => onFieldChange("unit", v)}
          disabled={formDisabled}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0 16px", marginBottom: 16 }}>
        <SmallField id={`setpoint-${index}-standard_uncertainty`} label="Uncertainty of Standard (Ub1)" value={setpoint.standard_uncertainty} onChange={v => onFieldChange("standard_uncertainty", v)} type="number" disabled={formDisabled} />
        <SmallField id={`setpoint-${index}-standard_accuracy`} label="Accuracy of Standard (Ub2)" value={setpoint.standard_accuracy} onChange={v => onFieldChange("standard_accuracy", v)} type="number" disabled={formDisabled} />
        <SmallField id={`setpoint-${index}-drift_standard_uncertainty`} label="Drift of Standard (Ub3)" value={setpoint.drift_standard_uncertainty} onChange={v => onFieldChange("drift_standard_uncertainty", v)} type="number" disabled={formDisabled} />
        <SmallField id={`setpoint-${index}-hysteresis_value`} label="Hysteresis (Ub5)" value={setpoint.hysteresis_value} onChange={v => onFieldChange("hysteresis_value", v)} type="number" disabled={formDisabled} />
        <SmallField id={`setpoint-${index}-bath_stability_value`} label="Bath Stability (Ub6)" value={setpoint.bath_stability_value} onChange={v => onFieldChange("bath_stability_value", v)} type="number" disabled={formDisabled} />
        <SmallField id={`setpoint-${index}-bath_uniformity_value`} label="Bath Uniformity (Ub7)" value={setpoint.bath_uniformity_value} onChange={v => onFieldChange("bath_uniformity_value", v)} type="number" disabled={formDisabled} />
        {subtype === "TCK" && (
          <SmallField id={`setpoint-${index}-wire_homogeneity_value`} label="Wire Homogeneity (Ub8)" value={setpoint.wire_homogeneity_value} onChange={v => onFieldChange("wire_homogeneity_value", v)} type="number" disabled={formDisabled} />
        )}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--color-muted)" }}>
            <th style={{ padding: "4px 8px" }}>Reading #</th>
            <th style={{ padding: "4px 8px" }}>Value ({setpoint.unit || "C"})</th>
          </tr>
        </thead>
        <tbody>
          {setpoint.readings.map((r, i) => (
            <tr key={i}>
              <td style={{ padding: "4px 8px", color: "var(--color-muted)" }}>{i + 1}</td>
              <td style={{ padding: "4px 8px" }}>
                <input
                  id={`setpoint-${index}-reading_value-${i}`}
                  name={`setpoint-${index}-reading_value-${i}`}
                  type="text"
                  inputMode="decimal"
                  value={r.reading_value}
                  disabled={formDisabled}
                  onChange={e => { if (isValidDecimalInProgress(e.target.value)) onReadingChange(i, e.target.value); }}
                  style={{ width: "100%" }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SmallField({ id, label, value, onChange, type = "text", disabled, placeholder }) {
  const isNumeric = type === "number";
  return (
    <div style={{ flex: 1, minWidth: 140, marginBottom: 12 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4, color: "var(--color-text)" }}>
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={isNumeric ? "text" : type}
        inputMode={isNumeric ? "decimal" : undefined}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={isNumeric ? decimalInputHandler(onChange) : (e => onChange(e.target.value))}
        style={{ width: "100%" }}
      />
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-muted)", marginBottom: 6 }}>{label}</label>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{value || "—"}</div>
    </div>
  );
}

function newSetpoint(index) {
  return {
    key: `new_${index}_${Date.now()}`,
    setpoint_label: "",
    nominal_temperature: "",
    unit: "C",
    standard_uncertainty: "",
    standard_accuracy: "",
    drift_standard_uncertainty: "",
    hysteresis_value: "",
    bath_stability_value: "",
    bath_uniformity_value: "",
    wire_homogeneity_value: "",
    readings: [{ reading_value: "" }, { reading_value: "" }, { reading_value: "" }],
  };
}

/** Converts a saved backend record (with nested readings) back into this form's local state shape. */
function hydrateSetpoint(t) {
  const sortedReadings = (t.readings || [])
    .slice()
    .sort((a, b) => a.reading_number - b.reading_number)
    .map(r => ({ reading_value: r.reading_value !== null && r.reading_value !== undefined ? String(r.reading_value) : "" }));
  while (sortedReadings.length < 3) sortedReadings.push({ reading_value: "" });

  return {
    key: t.id,
    setpoint_label: t.setpoint_label || "",
    nominal_temperature: t.nominal_temperature !== null && t.nominal_temperature !== undefined ? String(t.nominal_temperature) : "",
    unit: t.unit || "C",
    standard_uncertainty: t.standard_uncertainty !== null && t.standard_uncertainty !== undefined ? String(t.standard_uncertainty) : "",
    standard_accuracy: t.standard_accuracy !== null && t.standard_accuracy !== undefined ? String(t.standard_accuracy) : "",
    drift_standard_uncertainty: t.drift_standard_uncertainty !== null && t.drift_standard_uncertainty !== undefined ? String(t.drift_standard_uncertainty) : "",
    hysteresis_value: t.hysteresis_value !== null && t.hysteresis_value !== undefined ? String(t.hysteresis_value) : "",
    bath_stability_value: t.bath_stability_value !== null && t.bath_stability_value !== undefined ? String(t.bath_stability_value) : "",
    bath_uniformity_value: t.bath_uniformity_value !== null && t.bath_uniformity_value !== undefined ? String(t.bath_uniformity_value) : "",
    wire_homogeneity_value: t.wire_homogeneity_value !== null && t.wire_homogeneity_value !== undefined ? String(t.wire_homogeneity_value) : "",
    readings: sortedReadings,
  };
}

export default TemperatureReadingsForm;