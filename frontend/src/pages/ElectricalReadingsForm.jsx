import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import SessionPicker from "../components/SessionPicker";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import {
  createElectricalTest,
  getElectricalTests,
} from "../api";

// Must match formulas/electrical.json's function_types keys exactly.
const FUNCTION_TYPES = [
  "DCV", "ACV", "DCA", "ACA", "Resistance", "Frequency",
  "Insulation Resistance", "Temperature (R,S,B)", "Temperature (K,J,N,E,T)",
  "DCA (Coil)", "ACA (Coil)",
];
const COIL_TYPES = new Set(["DCA (Coil)", "ACA (Coil)"]);

/**
 * ElectricalReadingsForm component.
 * Data entry for Electrical calibration: one test per function-type/range
 * tested (e.g. a single DMM session might test DCV at 6 different ranges,
 * ACV at another 6, and so on). Each test needs its repeated readings plus
 * the Type B input values (Ub1/Ub2/Ub3, and Ub4 for DCV's thermo-electric
 * limit or the two Coil types' extra resolution component). Mirrors
 * TemperatureReadingsForm.jsx's dynamic-list structure, built with the
 * session-picker pattern from the start.
 *
 * IMPORTANT: unlike Temperature's Type A (stdev/sqrt(n)), Electrical's
 * Type A divisor is a flat 2 - confirmed against real source files, not
 * a bug in the form or the backend. See calculate_type_a_electrical's
 * docstring for the full explanation. DCV also has a known possible
 * double-counting quirk (thermo-electric voltage folded into Type A AND
 * appearing as its own Ub4) - reproduced faithfully, not silently fixed.
 *
 * Reachable two ways, same pattern as TemperatureReadingsForm.jsx:
 *  - Directly with :sessionId already in the URL (/readings/electrical/:sessionId).
 *  - From a bare route with no session (/readings/electrical) - a
 *    SessionPicker is shown, fields stay disabled until a session is chosen.
 */
function ElectricalReadingsForm() {
  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [loadingExisting, setLoadingExisting] = useState(false);
  const [tests, setTests] = useState([newTest(0)]);
  const [submitError, setSubmitError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadExisting = useCallback(() => {
    if (!effectiveSessionId) return;
    setLoadingExisting(true);
    getElectricalTests(effectiveSessionId)
      .then(existing => {
        if (existing && existing.length > 0) {
          setTests(existing.map(hydrateTest));
        }
        setLoadingExisting(false);
      })
      .catch(() => setLoadingExisting(false));
  }, [effectiveSessionId]);

  useEffect(() => {
    loadExisting();
  }, [loadExisting]);

  function updateTestField(index, field, value) {
    setIsDirty(true);
    setTests(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  }

  function updateReading(testIndex, readingIndex, value) {
    setIsDirty(true);
    setTests(prev => {
      const updated = [...prev];
      const readings = [...updated[testIndex].readings];
      readings[readingIndex] = { reading_value: value };
      updated[testIndex] = { ...updated[testIndex], readings };
      return updated;
    });
  }

  function addReading(testIndex) {
    setIsDirty(true);
    setTests(prev => {
      const updated = [...prev];
      updated[testIndex] = {
        ...updated[testIndex],
        readings: [...updated[testIndex].readings, { reading_value: "" }],
      };
      return updated;
    });
  }

  function removeReading(testIndex, readingIndex) {
    setIsDirty(true);
    setTests(prev => {
      const updated = [...prev];
      const readings = updated[testIndex].readings;
      if (readings.length === 1) return prev;
      updated[testIndex] = { ...updated[testIndex], readings: readings.filter((_, i) => i !== readingIndex) };
      return updated;
    });
  }

  function addTest() {
    setIsDirty(true);
    setTests(prev => [...prev, newTest(prev.length)]);
  }

  function removeTest(index) {
    setIsDirty(true);
    setTests(prev => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function testComplete(t) {
    if (!t.function_type || !t.range_label.trim() || !t.unit.trim()) return false;
    if (t.cert_uncertainty_limit === "" || t.calibrator_accuracy_limit === "" || t.resolution === "") return false;
    if (t.function_type === "DCV" && t.thermo_electric_limit === "") return false;
    if (COIL_TYPES.has(t.function_type) && t.coil_accuracy_limit === "") return false;
    return t.readings.every(r => r.reading_value !== "");
  }

  const allComplete = tests.length > 0 && tests.every(testComplete);
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
      for (const t of tests) {
        const testPayload = {
          session_id: effectiveSessionId,
          function_type: t.function_type,
          range_label: t.range_label.trim(),
          nominal_value: t.nominal_value === "" ? null : Number(t.nominal_value),
          unit: t.unit.trim(),
          cert_uncertainty_limit: Number(t.cert_uncertainty_limit),
          calibrator_accuracy_limit: Number(t.calibrator_accuracy_limit),
          resolution: Number(t.resolution),
          thermo_electric_limit: t.function_type === "DCV" ? Number(t.thermo_electric_limit) : null,
          coil_accuracy_limit: COIL_TYPES.has(t.function_type) ? Number(t.coil_accuracy_limit) : null,
        };
        const readingsPayload = t.readings.map((r, i) => ({
          reading_number: i + 1,
          reading_value: Number(r.reading_value),
        }));
        await createElectricalTest(effectiveSessionId, testPayload, readingsPayload);
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
      <div style={{ maxWidth: 860, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 04 — Electrical
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Electrical Test Data
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Enter one test per function type and range (e.g. DCV at 200mV, DCV at 2V, ACV at 200mV...).
            Each test needs its repeated readings plus the standard and accuracy limits from the
            calibrator's certificate.
          </p>
        </div>

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} />
        )}

        <div style={{ opacity: formDisabled ? 0.5 : 1, transition: "opacity 0.15s" }}>

          {loadingExisting && (
            <p style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 16 }}>
              Loading existing tests...
            </p>
          )}

          {tests.map((t, index) => (
            <TestCard
              key={t.key}
              index={index}
              test={t}
              canRemove={tests.length > 1}
              formDisabled={formDisabled}
              onFieldChange={(field, value) => updateTestField(index, field, value)}
              onReadingChange={(readingIndex, value) => updateReading(index, readingIndex, value)}
              onAddReading={() => addReading(index)}
              onRemoveReading={readingIndex => removeReading(index, readingIndex)}
              onRemove={() => removeTest(index)}
            />
          ))}

          <button
            onClick={addTest}
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
            + Add Test
          </button>

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
              {isSubmitting ? "Saving..." : "Save Tests & Continue to Calculation"}
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

function TestCard({ index, test, canRemove, formDisabled, onFieldChange, onReadingChange, onAddReading, onRemoveReading, onRemove }) {
  const isCoil = COIL_TYPES.has(test.function_type);
  const isDCV = test.function_type === "DCV";

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
          Test {index + 1}
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
        <div style={{ flex: 1, minWidth: 160, marginBottom: 12 }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>Function Type</label>
          <select
            value={test.function_type}
            disabled={formDisabled}
            onChange={e => onFieldChange("function_type", e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="">Select...</option>
            {FUNCTION_TYPES.map(ft => <option key={ft} value={ft}>{ft}</option>)}
          </select>
        </div>
        <SmallField label="Range Label" value={test.range_label} onChange={v => onFieldChange("range_label", v)} disabled={formDisabled} placeholder="e.g. 200mV" />
        <SmallField label="Nominal Value" value={test.nominal_value} onChange={v => onFieldChange("nominal_value", v)} type="number" disabled={formDisabled} />
        <SmallField label="Unit" value={test.unit} onChange={v => onFieldChange("unit", v)} disabled={formDisabled} placeholder="e.g. mV" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0 16px", marginBottom: 16 }}>
        <SmallField label="Uncertainty of Standard Calibrator (Ub1)" value={test.cert_uncertainty_limit} onChange={v => onFieldChange("cert_uncertainty_limit", v)} type="number" disabled={formDisabled} />
        <SmallField label="Accuracy of Standard Calibrator (Ub2)" value={test.calibrator_accuracy_limit} onChange={v => onFieldChange("calibrator_accuracy_limit", v)} type="number" disabled={formDisabled} />
        <SmallField label={isCoil ? "Resolution of UUC (Ub4)" : "Resolution of UUC (Ub3)"} value={test.resolution} onChange={v => onFieldChange("resolution", v)} type="number" disabled={formDisabled} />
        {isDCV && (
          <SmallField label="Thermo-Electric Voltage Limit (Ub4)" value={test.thermo_electric_limit} onChange={v => onFieldChange("thermo_electric_limit", v)} type="number" disabled={formDisabled} />
        )}
        {isCoil && (
          <SmallField label="Accuracy of Current Coil (Ub3)" value={test.coil_accuracy_limit} onChange={v => onFieldChange("coil_accuracy_limit", v)} type="number" disabled={formDisabled} />
        )}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 8 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--color-muted)" }}>
            <th style={{ padding: "4px 8px" }}>Reading #</th>
            <th style={{ padding: "4px 8px" }}>Value ({test.unit || "—"})</th>
            <th style={{ padding: "4px 8px" }}></th>
          </tr>
        </thead>
        <tbody>
          {test.readings.map((r, i) => (
            <tr key={i}>
              <td style={{ padding: "4px 8px", color: "var(--color-muted)" }}>{i + 1}</td>
              <td style={{ padding: "4px 8px" }}>
                <input
                  type="number"
                  value={r.reading_value}
                  disabled={formDisabled}
                  onChange={e => onReadingChange(i, e.target.value)}
                  style={{ width: "100%" }}
                />
              </td>
              <td style={{ padding: "4px 8px" }}>
                {test.readings.length > 1 && (
                  <button
                    onClick={() => onRemoveReading(i)}
                    disabled={formDisabled}
                    style={{ background: "none", border: "none", color: "var(--color-error)", fontSize: 12, cursor: formDisabled ? "not-allowed" : "pointer" }}
                  >
                    ×
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        onClick={onAddReading}
        disabled={formDisabled}
        style={{ background: "none", border: "none", color: "var(--color-primary)", fontSize: 12, fontWeight: 600, cursor: formDisabled ? "not-allowed" : "pointer", padding: 0 }}
      >
        + Add Reading
      </button>
    </div>
  );
}

function SmallField({ label, value, onChange, type = "text", disabled, placeholder }) {
  return (
    <div style={{ flex: 1, minWidth: 140, marginBottom: 12 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4, color: "var(--color-text)" }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
        style={{ width: "100%" }}
      />
    </div>
  );
}

function newTest(index) {
  return {
    key: `new_${index}_${Date.now()}`,
    function_type: "",
    range_label: "",
    nominal_value: "",
    unit: "",
    cert_uncertainty_limit: "",
    calibrator_accuracy_limit: "",
    resolution: "",
    thermo_electric_limit: "",
    coil_accuracy_limit: "",
    readings: [{ reading_value: "" }, { reading_value: "" }, { reading_value: "" }],
  };
}

/** Converts a saved backend record (with nested readings) back into this form's local state shape. */
function hydrateTest(t) {
  const sortedReadings = (t.electrical_readings || [])
    .slice()
    .sort((a, b) => a.reading_number - b.reading_number)
    .map(r => ({ reading_value: r.reading_value !== null && r.reading_value !== undefined ? String(r.reading_value) : "" }));
  if (sortedReadings.length === 0) sortedReadings.push({ reading_value: "" });

  return {
    key: t.id,
    function_type: t.function_type || "",
    range_label: t.range_label || "",
    nominal_value: t.nominal_value !== null && t.nominal_value !== undefined ? String(t.nominal_value) : "",
    unit: t.unit || "",
    cert_uncertainty_limit: t.cert_uncertainty_limit !== null && t.cert_uncertainty_limit !== undefined ? String(t.cert_uncertainty_limit) : "",
    calibrator_accuracy_limit: t.calibrator_accuracy_limit !== null && t.calibrator_accuracy_limit !== undefined ? String(t.calibrator_accuracy_limit) : "",
    resolution: t.resolution !== null && t.resolution !== undefined ? String(t.resolution) : "",
    thermo_electric_limit: t.thermo_electric_limit !== null && t.thermo_electric_limit !== undefined ? String(t.thermo_electric_limit) : "",
    coil_accuracy_limit: t.coil_accuracy_limit !== null && t.coil_accuracy_limit !== undefined ? String(t.coil_accuracy_limit) : "",
    readings: sortedReadings,
  };
}

export default ElectricalReadingsForm;
