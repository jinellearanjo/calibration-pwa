import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import Spinner from "../components/Spinner";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import { decimalInputHandler } from "../utils/numericInput";
import {
  createInstrument,
  updateInstrument,
  getInstrument,
  updateCalibrationReference,
  createCalibrationReference,
  getCalibrationReferenceBySession,
} from "../api";

/**
 * InstrumentForm component.
 * Two-section form for registering a new instrument under calibration,
 * or editing an existing one (editMode via location.state).
 *
 * Edit mode: pre-fills both sections from existing DB records, submits
 * via PUT instead of POST, then navigates to SessionForm in edit mode
 * carrying sessionId through.
 *
 * Section 1: Calibration Reference Details.
 * Section 2: Unit Under Calibration (UUC) fields.
 */
function InstrumentForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingEdit, setLoadingEdit] = useState(false);

  // Edit mode fields from navigation state
  const editMode = location.state?.editMode || false;
  const editSessionId = location.state?.sessionId || null;
  const editInstrumentId = location.state?.instrumentId || null;

  const [refData, setRefData] = useState({
    certificate_number: "",
    date_of_calibration: "",
    cal_due_date: "",
    item_received_date: "",
    date_of_issue: "",
    customer_name: "",
    customer_address: "",
  });

  const [uucData, setUucData] = useState({
    name: "",
    type: "",
    instrument_subtype: "",
    make: "",
    model: "",
    serial_number: "",
    accuracy_class: "",
    resolution: "",
    unit: "",
    range_min: "",
    range_max: "",
    tag_number: "",
    calibration_carried_at: "",
    dial_size: "",
    mounting_orientation: "",
    instrument_location: "",
    medium_used: "",
  });

  const [errors, setErrors] = useState({});

  // Pre-fill from existing records when in edit mode
  useEffect(() => {
    if (!editMode || !editInstrumentId) return;
    setLoadingEdit(true);

    async function loadEditData() {
      try {
        const instrument = await getInstrument(editInstrumentId);
        if (instrument) {
          setUucData({
            name: instrument.name || "",
            type: instrument.type || "",
            instrument_subtype: instrument.instrument_subtype || "",
            make: instrument.make || "",
            model: instrument.model || "",
            serial_number: instrument.serial_number || "",
            accuracy_class: String(instrument.accuracy_class ?? ""),
            resolution: String(instrument.resolution ?? ""),
            unit: instrument.unit || "",
            range_min: String(instrument.range_min ?? ""),
            range_max: String(instrument.range_max ?? ""),
            tag_number: instrument.tag_number || "",
            calibration_carried_at: instrument.calibration_carried_at || "",
            dial_size: instrument.dial_size || "",
            mounting_orientation: instrument.mounting_orientation || "",
            instrument_location: instrument.instrument_location || "",
            medium_used: instrument.medium_used || "",
          });
        }

        // Fetch calibration reference for this session, if one exists yet
        // (routed through api.js's request() helper, same auth-token
        // handling as every other call in this app - no need to hand-roll
        // a fetch + Supabase session lookup here).
        if (editSessionId) {
          try {
            const ref = await getCalibrationReferenceBySession(editSessionId);
            if (ref) {
              setRefData({
                certificate_number: ref.certificate_number || "",
                date_of_calibration: ref.date_of_calibration || "",
                cal_due_date: ref.cal_due_date || "",
                item_received_date: ref.item_received_date || "",
                date_of_issue: ref.date_of_issue || "",
                customer_name: ref.customer_name || "",
                customer_address: ref.customer_address || "",
              });
            }
          } catch {
            // No calibration reference exists yet for this session (404) -
            // non-fatal, the form just stays empty for Section 1 and the
            // user fills it in fresh.
          }
        }
      } catch (e) {
        // Non-fatal: form stays empty and user can fill manually
      } finally {
        setLoadingEdit(false);
      }
    }

    loadEditData();
  }, [editMode, editInstrumentId, editSessionId]);

  const requiredRef = ["certificate_number", "date_of_calibration", "cal_due_date", "item_received_date", "date_of_issue", "customer_name", "customer_address"];
  const requiredUuc = ["name", "type", "make", "model", "serial_number", "accuracy_class", "resolution", "unit", "range_min", "range_max"];

  function validate(field, value) {
    const numericFields = ["accuracy_class", "resolution", "range_min", "range_max"];
    if (requiredRef.includes(field) || requiredUuc.includes(field)) {
      if (!value || !value.toString().trim()) return "This field is required.";
    }
    // instrument_subtype is only required when type is Temperature - it isn't
    // in requiredUuc because it's conditionally rendered, so it needs its own check.
    if (field === "instrument_subtype" && uucData.type === "Temperature") {
      if (!value || !value.toString().trim()) return "Required for Temperature instruments.";
    }
    if (numericFields.includes(field) && value !== "" && isNaN(Number(value))) {
      return "Must be a number.";
    }
    return "";
  }

  function updateRef(field, value) {
    setRefData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
    setIsDirty(true);
  }

  function updateUuc(field, value) {
    setUucData(prev => {
      const nextData = { ...prev, [field]: value };
      // If the instrument category type changes, reset the chosen unit
      if (field === "type") {
        nextData.unit = "";
      }
      return nextData;
    });

    setErrors(prev => {
      const nextErrors = { ...prev, [field]: validate(field, value) };
      // If type changed, clear out any old validation errors for the unit field
      if (field === "type") {
        nextErrors.unit = "";
      }
      return nextErrors;
    });

    setIsDirty(true);
  }

  const hasErrors = Object.values(errors).some(Boolean);
  const allFilled = [...requiredRef, ...requiredUuc].every(f =>
    (refData[f] || uucData[f] || "").toString().trim() !== ""
  ) && (uucData.type !== "Temperature" || (uucData.instrument_subtype || "").toString().trim() !== "");

  async function handleSubmit() {
    const freshErrors = {};
    requiredRef.forEach(f => { freshErrors[f] = validate(f, refData[f]); });
    requiredUuc.forEach(f => { freshErrors[f] = validate(f, uucData[f]); });
    freshErrors.instrument_subtype = validate("instrument_subtype", uucData.instrument_subtype);
    setErrors(freshErrors);
    if (Object.values(freshErrors).some(Boolean)) return;

    setIsSubmitting(true);
    try {
      let instrumentId;

      if (editMode) {
        // Update existing instrument
        await updateInstrument(editInstrumentId, uucData);
        instrumentId = editInstrumentId;
        // Update or create calibration reference
        try {
          await updateCalibrationReference(editSessionId, { ...refData, session_id: editSessionId });
        } catch {
          await createCalibrationReference({ ...refData, session_id: editSessionId });
        }
      } else {
        // Create the instrument now. refData (certificate number, customer
        // details, etc.) can't be submitted yet - calibration_reference
        // requires a session_id, and no session exists until SessionForm's
        // own submit. Carry refData forward via navigation state; SessionForm
        // submits it once the new session's id is available.
        const created = await createInstrument(uucData);
        instrumentId = created?.[0]?.id;
      }

      setIsDirty(false);
      navigate("/session", {
        state: {
          instrumentId,
          instrumentType: uucData.type,
          calibrationReference: refData,
          ...(editMode ? { editMode: true, sessionId: editSessionId } : {}),
        },
      });
    } catch (err) {
      setErrors(prev => ({ ...prev, submit: err.message }));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loadingEdit) return <Spinner message="Loading session data..." />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            {editMode ? "Edit" : "Step 01"}
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            {editMode ? "Edit Instrument Details" : "Register Instrument"}
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            {editMode
              ? "Update calibration reference details and instrument under calibration fields."
              : "Enter calibration reference details and instrument under calibration fields."}
          </p>
        </div>

        <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "28px 32px", boxShadow: "var(--shadow-sm)", marginBottom: 16 }}>
          <SectionHeading step="01" title="Calibration Reference Details" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            <Field label="Certificate Number" id="certificate_number" value={refData.certificate_number} onChange={v => updateRef("certificate_number", v)} error={errors.certificate_number} />
            <Field label="Date of Calibration" id="date_of_calibration" type="date" value={refData.date_of_calibration} onChange={v => updateRef("date_of_calibration", v)} error={errors.date_of_calibration} />
            <Field label="Calibration Due Date" id="cal_due_date" type="date" value={refData.cal_due_date} onChange={v => updateRef("cal_due_date", v)} error={errors.cal_due_date} />
            <Field label="Item Received Date" id="item_received_date" type="date" value={refData.item_received_date} onChange={v => updateRef("item_received_date", v)} error={errors.item_received_date} />
            <Field label="Date of Issue" id="date_of_issue" type="date" value={refData.date_of_issue} onChange={v => updateRef("date_of_issue", v)} error={errors.date_of_issue} />
            <Field label="Customer Name" id="customer_name" value={refData.customer_name} onChange={v => updateRef("customer_name", v)} error={errors.customer_name} />
            <div style={{ gridColumn: "1 / -1" }}>
              <Field label="Customer Address" id="customer_address" value={refData.customer_address} onChange={v => updateRef("customer_address", v)} error={errors.customer_address} />
            </div>
          </div>
        </div>

        <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius)", padding: "28px 32px", boxShadow: "var(--shadow-sm)", marginBottom: 24 }}>
          <SectionHeading step="02" title="Unit Under Calibration (UUC)" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            <Field label="Instrument Name" id="name" value={uucData.name} onChange={v => updateUuc("name", v)} error={errors.name} />
            <SelectField label="Type" id="type" value={uucData.type} onChange={v => updateUuc("type", v)} error={errors.type} options={["Pressure", "Temperature", "Electrical", "Weighing"]} />
            {uucData.type === "Temperature" && (
              <SelectField
                label="Sensor Sub-Type"
                id="instrument_subtype"
                value={uucData.instrument_subtype || ""}
                onChange={v => updateUuc("instrument_subtype", v)}
                error={errors.instrument_subtype}
                options={["TCK", "RTD", "DTI", "DryBlock"]}
              />
            )}
            <Field label="Make" id="make" value={uucData.make} onChange={v => updateUuc("make", v)} error={errors.make} />
            <Field label="Model" id="model" value={uucData.model} onChange={v => updateUuc("model", v)} error={errors.model} />
            <Field label="Serial Number" id="serial_number" value={uucData.serial_number} onChange={v => updateUuc("serial_number", v)} error={errors.serial_number} />
            <Field label="Accuracy Class" id="accuracy_class" type="number" value={uucData.accuracy_class} onChange={v => updateUuc("accuracy_class", v)} error={errors.accuracy_class} />
            <Field label="Resolution" id="resolution" type="number" value={uucData.resolution} onChange={v => updateUuc("resolution", v)} error={errors.resolution} />
            <SelectField
              label="Unit"
              id="unit"
              value={uucData.unit}
              onChange={v => updateUuc("unit", v)}
              error={errors.unit}
              options={
                uucData.type === "Pressure" ? ["bar", "psi", "kPa", "MPa", "mbar"] :
                uucData.type === "Temperature" ? ["°C"] :
                uucData.type === "Weighing" ? ["g", "kg", "mg"] :
                uucData.type === "Electrical" ? ["V", "mV", "A", "mA", "\u00B5A", "\u2126", "k\u2126", "M\u2126", "G\u2126", "Hz", "kHz", "MHz"] :
                []
              }
            />
            <Field label="Range Min" id="range_min" type="number" value={uucData.range_min} onChange={v => updateUuc("range_min", v)} error={errors.range_min} />
            <Field label="Range Max" id="range_max" type="number" value={uucData.range_max} onChange={v => updateUuc("range_max", v)} error={errors.range_max} />
            <Field label="Tag Number (optional)" id="tag_number" value={uucData.tag_number} onChange={v => updateUuc("tag_number", v)} error={errors.tag_number} />
            <Field label="Calibration Carried At (optional)" id="calibration_carried_at" value={uucData.calibration_carried_at} onChange={v => updateUuc("calibration_carried_at", v)} error={errors.calibration_carried_at} />
            <Field label="Dial Size (optional)" id="dial_size" value={uucData.dial_size} onChange={v => updateUuc("dial_size", v)} error={errors.dial_size} />
            <Field label="Mounting Orientation (optional)" id="mounting_orientation" value={uucData.mounting_orientation} onChange={v => updateUuc("mounting_orientation", v)} error={errors.mounting_orientation} />
            <Field label="Instrument Location (optional)" id="instrument_location" value={uucData.instrument_location} onChange={v => updateUuc("instrument_location", v)} error={errors.instrument_location} />
            <Field label="Medium Used (optional)" id="medium_used" value={uucData.medium_used} onChange={v => updateUuc("medium_used", v)} error={errors.medium_used} />
          </div>
        </div>

        {errors.submit && (
          <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 12 }}>
            {errors.submit}
          </p>
        )}

        <div style={{ display: "flex", gap: 12 }}>
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
            {isSubmitting ? "Saving..." : editMode ? "Save Changes" : "Register Instrument"}
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
  );
}

function SectionHeading({ step, title }) {
  return (
    <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: "1px solid var(--color-border)" }}>
      <span style={{ fontSize: 11, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-accent)", marginRight: 10 }}>{step}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-primary)" }}>{title}</span>
    </div>
  );
}

function Field({ label, id, value, onChange, error, type = "text" }) {
  const isNumeric = type === "number";
  return (
    <div style={{ marginBottom: 20 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <input
        id={id}
        type={isNumeric ? "text" : type}
        inputMode={isNumeric ? "decimal" : undefined}
        value={value}
        onChange={isNumeric ? decimalInputHandler(onChange) : (e => onChange(e.target.value))}
        style={{ borderColor: error ? "var(--color-error)" : undefined }}
      />
      {error && <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>{error}</span>}
    </div>
  );
}

function SelectField({ label, id, value, onChange, error, options }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)} style={{ borderColor: error ? "var(--color-error)" : undefined }}>
        <option value="">Select...</option>
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
      {error && <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>{error}</span>}
    </div>
  );
}

export default InstrumentForm;