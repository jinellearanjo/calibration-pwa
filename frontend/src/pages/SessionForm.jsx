import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import { decimalInputHandler } from "../utils/numericInput";
import { createSession, updateSession, createCalibrationReference, updateCalibrationReference, listMasterInstruments, getInstrument, getSession } from "../api";

/**
 * SessionForm component.
 * Creates a new calibration session, or edits an existing one (editMode).
 *
 * Edit mode: pre-fills from existing session record via getSession,
 * submits via PUT instead of POST, then routes to the appropriate
 * readings form for the instrument type.
 */
function SessionForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

  // instrumentId/instrumentType arrive via navigation state from
  // InstrumentForm.jsx. Both are optional — the form still works if
  // someone navigates here directly (e.g. a page refresh), it just won't
  // be pre-filled and the type will be looked up via getInstrument after
  // submission instead.
  const passedInstrumentId = location.state?.instrumentId;
  const passedInstrumentType = location.state?.instrumentType;
  const passedCalibrationReference = location.state?.calibrationReference;
  const editMode = location.state?.editMode || false;
  const editSessionId = location.state?.sessionId || null;

  const [formData, setFormData] = useState({
    instrument_id: passedInstrumentId || "",
    master_instrument_id: "",
    date: "",
    technician: "",
    temperature_c: "",
    humidity_pct: "",
    notes: "",
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [masterInstruments, setMasterInstruments] = useState([]);
  const [masterLoadError, setMasterLoadError] = useState("");

  // The instrument's category (Pressure/Temperature/Weighing/Electrical),
  // used to filter which master instruments show in the dropdown below -
  // without this, every master instrument for the user showed up
  // regardless of category, so a Temperature session could accidentally
  // have a Pressure master (e.g. "Dead Weight Tester") selected.
  // Prefer passedInstrumentType (set by InstrumentForm's navigation state)
  // since it avoids an extra request; fall back to looking it up if this
  // form was opened directly (e.g. a page refresh lost navigation state).
  const [resolvedInstrumentType, setResolvedInstrumentType] = useState(passedInstrumentType || null);

  useEffect(() => {
    if (resolvedInstrumentType || !formData.instrument_id) return;
    let cancelled = false;
    getInstrument(formData.instrument_id)
      .then(instrument => { if (!cancelled && instrument?.type) setResolvedInstrumentType(instrument.type); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [resolvedInstrumentType, formData.instrument_id]);

  // master_instrument_id is intentionally not in requiredFields: some
  // historical sessions predate this field, and not every calibration type
  // may have a master instrument recorded yet.
  const requiredFields = ["instrument_id", "date", "technician", "temperature_c", "humidity_pct"];

  // Pre-fill from existing session in edit mode
  useEffect(() => {
    if (!editMode || !editSessionId) return;
    getSession(editSessionId).then(session => {
      if (session) {
        setFormData({
          instrument_id: session.instrument_id || passedInstrumentId || "",
          master_instrument_id: session.master_instrument_id || "",
          date: session.date || "",
          technician: session.technician || "",
          temperature_c: String(session.temperature_c ?? ""),
          humidity_pct: String(session.humidity_pct ?? ""),
          notes: session.notes || "",
        });
      }
    }).catch(() => {});
  }, [editMode, editSessionId, passedInstrumentId]);

  useEffect(() => {
    let cancelled = false;
    listMasterInstruments()
      .then(data => { if (!cancelled) setMasterInstruments(data || []); })
      .catch(err => { if (!cancelled) setMasterLoadError(err.message); });
    return () => { cancelled = true; };
  }, []);

  function validate(field, value) {
    if (field === "instrument_id" && !value.trim()) return "Instrument ID is required.";
    if (field === "date" && !value) return "Date is required.";
    if (field === "technician" && !value.trim()) return "Technician name is required.";
    if (field === "temperature_c") {
      if (value === "") return "Temperature is required.";
      if (isNaN(Number(value))) return "Must be a number.";
    }
    if (field === "humidity_pct") {
      if (value === "") return "Humidity is required.";
      if (isNaN(Number(value))) return "Must be a number.";
      if (Number(value) < 0 || Number(value) > 100) return "Must be between 0 and 100.";
    }
    return "";
  }

  function updateField(field, value) {
    setFormData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
    setIsDirty(true);
  }

  const hasErrors = Object.values(errors).some(Boolean);
  const allFilled = requiredFields.every(f => formData[f] !== "");

  async function handleSubmit() {
    const freshErrors = {};
    requiredFields.forEach(f => { freshErrors[f] = validate(f, formData[f]); });
    setErrors(freshErrors);
    if (Object.values(freshErrors).some(Boolean)) return;

    setIsSubmitting(true);
    try {
      const payload = { ...formData };
      if (!payload.master_instrument_id) delete payload.master_instrument_id;

      let sessionId;

      if (editMode) {
        await updateSession(editSessionId, payload);
        sessionId = editSessionId;
        // Update calibration reference if carried through from InstrumentForm
        if (passedCalibrationReference) {
          try {
            await updateCalibrationReference(sessionId, { ...passedCalibrationReference, session_id: sessionId });
          } catch {
            await createCalibrationReference({ ...passedCalibrationReference, session_id: sessionId });
          }
        }
      } else {
        const created = await createSession(payload);
        sessionId = created?.[0]?.id;
        // Now that a session exists, submit the calibration reference data
        // (certificate number, customer details) carried forward from
        // InstrumentForm - this couldn't be submitted earlier since
        // calibration_reference.session_id didn't exist yet.
        if (passedCalibrationReference) {
          await createCalibrationReference({ ...passedCalibrationReference, session_id: sessionId });
        }
      }

      setIsDirty(false);

      // Resolve the instrument's type to decide which readings form to
      // send the user to. Prefer the type passed from InstrumentForm
      // (avoids an extra request); fall back to a lookup if this form was
      // opened directly (e.g. a page refresh lost the navigation state).
      let instrumentType = passedInstrumentType;
      if (!instrumentType) {
        const instrument = await getInstrument(payload.instrument_id);
        instrumentType = instrument?.type;
      }

      if (instrumentType === "Weighing") {
        navigate(`/readings/weighing/${sessionId}`);
      } else if (instrumentType === "Temperature") {
        navigate(`/readings/temperature/${sessionId}`);
      } else if (instrumentType === "Electrical") {
        navigate(`/readings/electrical/${sessionId}`);
      } else {
        navigate(`/readings/${sessionId}`);
      }
    } catch (err) {
      setErrors(prev => ({ ...prev, submit: err.message }));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 600, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            {editMode ? "Edit" : "Step 02"}
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            {editMode ? "Edit Calibration Session" : "Calibration Session"}
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            {editMode
              ? "Update the session date, technician, and environmental conditions."
              : "Set the session date, technician, and environmental conditions."}
          </p>
        </div>

        <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "32px", boxShadow: "var(--shadow-sm)" }}>
          <Field label="Instrument ID" id="instrument_id" value={formData.instrument_id} onChange={v => updateField("instrument_id", v)} error={errors.instrument_id} />

          <div style={{ marginBottom: 20 }}>
            <label htmlFor="master_instrument_id" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
              Master Instrument (optional)
            </label>
            <select
              id="master_instrument_id"
              value={formData.master_instrument_id}
              onChange={e => updateField("master_instrument_id", e.target.value)}
              style={{ width: "100%", padding: "10px", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", fontSize: 14, background: "white" }}
            >
              <option value="">— None selected —</option>
              {masterInstruments
                .filter(m =>
                  // Only show masters matching this instrument's category -
                  // without this, every master for the user showed up
                  // regardless of type (a Temperature session could end up
                  // with a Pressure master like "Dead Weight Tester"
                  // selected). Still show the currently-selected master
                  // even if it doesn't match, so editing a session that
                  // already has a mismatched master doesn't silently hide
                  // its current selection from the dropdown.
                  !resolvedInstrumentType ||
                  m.instrument_type === resolvedInstrumentType ||
                  m.id === formData.master_instrument_id
                )
                .map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.instrument_type}, S/N {m.serial_number})
                  </option>
                ))}
            </select>
            {masterLoadError && (
              <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>
                Could not load master instruments: {masterLoadError}
              </span>
            )}
          </div>

          <Field label="Date" id="date" type="date" value={formData.date} onChange={v => updateField("date", v)} error={errors.date} />
          <Field label="Technician" id="technician" value={formData.technician} onChange={v => updateField("technician", v)} error={errors.technician} />
          <Field label="Temperature (°C)" id="temperature_c" type="number" value={formData.temperature_c} onChange={v => updateField("temperature_c", v)} error={errors.temperature_c} />
          <Field label="Humidity (%)" id="humidity_pct" type="number" value={formData.humidity_pct} onChange={v => updateField("humidity_pct", v)} error={errors.humidity_pct} />
          <Field label="Notes (optional)" id="notes" value={formData.notes} onChange={v => updateField("notes", v)} error={errors.notes} />

          {errors.submit && (
            <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 8 }}>{errors.submit}</p>
          )}

          <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
            <button
              onClick={handleSubmit}
              disabled={hasErrors || !allFilled || isSubmitting}
              style={{
                flex: 1, padding: "11px",
                background: hasErrors || !allFilled || isSubmitting ? "var(--color-border)" : "var(--color-primary)",
                color: "white", border: "none", borderRadius: "var(--radius)",
                fontWeight: 600, fontSize: 14,
                cursor: hasErrors || !allFilled || isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              {isSubmitting ? "Saving..." : editMode ? "Save Changes" : "Create Session"}
            </button>
            <button
              onClick={() => safeNavigate(editMode ? "/edit-session" : "/dashboard")}
              style={{ padding: "11px 20px", background: "white", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", fontSize: 14, fontWeight: 500, cursor: "pointer" }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, id, value, onChange, error, type = "text" }) {
  const isNumeric = type === "number";
  return (
    <div style={{ marginBottom: 20 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
        {label}
      </label>
      <input
        id={id}
        type={isNumeric ? "text" : type}
        inputMode={isNumeric ? "decimal" : undefined}
        value={value}
        onChange={isNumeric ? decimalInputHandler(onChange) : (e => onChange(e.target.value))}
        style={{ borderColor: error ? "var(--color-error)" : undefined }}
      />
      {error && (
        <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>
          {error}
        </span>
      )}
    </div>
  );
}

export default SessionForm;