import { useState } from "react";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import Navbar from "../components/Navbar";

/**
 * InstrumentForm component.
 * Two-section form for registering a new instrument under calibration.
 * Section 1: Calibration Reference Details.
 * Section 2: Unit Under Calibration (UUC) fields.
 *
 * @param {Object} props
 * @param {Function} props.onSubmit - Called with combined form data on valid submission.
 */
function InstrumentForm({ onSubmit }) {
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

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

  const requiredRef = ["certificate_number", "date_of_calibration", "cal_due_date", "item_received_date", "date_of_issue", "customer_name", "customer_address"];
  const requiredUuc = ["name", "type", "make", "model", "serial_number", "accuracy_class", "resolution", "unit", "range_min", "range_max"];

  function validate(field, value) {
    const numericFields = ["accuracy_class", "resolution", "range_min", "range_max"];
    if (requiredRef.includes(field) || requiredUuc.includes(field)) {
      if (!value || !value.toString().trim()) return `This field is required.`;
    }
    if (numericFields.includes(field) && value !== "" && isNaN(Number(value))) {
      return "Must be a number.";
    }
    return "";
  }

  function updateRef(field, value) {
    setRefData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
    // Mark form as dirty when any field changes.
    setIsDirty(true);
  }

  function updateUuc(field, value) {
    setUucData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
    // Mark form as dirty when any field changes.
    setIsDirty(true);
  }

  const hasErrors = Object.values(errors).some(Boolean);
  const allFilled = [...requiredRef, ...requiredUuc].every(f =>
    (refData[f] || uucData[f] || "").toString().trim() !== ""
  );

  function handleSubmit() {
    const freshErrors = {};
    requiredRef.forEach(f => { freshErrors[f] = validate(f, refData[f]); });
    requiredUuc.forEach(f => { freshErrors[f] = validate(f, uucData[f]); });
    setErrors(freshErrors);
    if (Object.values(freshErrors).some(Boolean)) return;
    onSubmit({ ...refData, ...uucData });
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 32px" }}>

        {/* Page header */}
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 01
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Register Instrument
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Enter calibration reference details and instrument under calibration fields.
          </p>
        </div>

        {/* Section 1 */}
        <div style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius)",
          padding: "28px 32px",
          boxShadow: "var(--shadow-sm)",
          marginBottom: 16,
        }}>
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

        {/* Section 2 */}
        <div style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius)",
          padding: "28px 32px",
          boxShadow: "var(--shadow-sm)",
          marginBottom: 24,
        }}>
          <SectionHeading step="02" title="Unit Under Calibration (UUC)" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            <Field label="Instrument Name" id="name" value={uucData.name} onChange={v => updateUuc("name", v)} error={errors.name} />
            <SelectField label="Type" id="type" value={uucData.type} onChange={v => updateUuc("type", v)} error={errors.type} options={["Pressure", "Temperature", "Electrical", "Weighing"]} />
            <Field label="Make" id="make" value={uucData.make} onChange={v => updateUuc("make", v)} error={errors.make} />
            <Field label="Model" id="model" value={uucData.model} onChange={v => updateUuc("model", v)} error={errors.model} />
            <Field label="Serial Number" id="serial_number" value={uucData.serial_number} onChange={v => updateUuc("serial_number", v)} error={errors.serial_number} />
            <Field label="Accuracy Class" id="accuracy_class" type="number" value={uucData.accuracy_class} onChange={v => updateUuc("accuracy_class", v)} error={errors.accuracy_class} />
            <Field label="Resolution" id="resolution" type="number" value={uucData.resolution} onChange={v => updateUuc("resolution", v)} error={errors.resolution} />
            <SelectField label="Unit" id="unit" value={uucData.unit} onChange={v => updateUuc("unit", v)} error={errors.unit} options={["bar", "psi", "kPa", "MPa", "mbar"]} />
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

        {/* Actions */}
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={handleSubmit}
            disabled={hasErrors || !allFilled}
            style={{
              flex: 1,
              padding: "11px",
              background: hasErrors || !allFilled ? "var(--color-border)" : "var(--color-primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius)",
              fontWeight: 600,
              fontSize: 14,
              cursor: hasErrors || !allFilled ? "not-allowed" : "pointer",
            }}
          >
            Register Instrument
          </button>
          <button
            onClick={() => safeNavigate("/dashboard")}
            style={{
              padding: "11px 20px",
              background: "white",
              color: "var(--color-text)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * SectionHeading component.
 * Styled section heading with step number accent.
 */
function SectionHeading({ step, title }) {
  return (
    <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: "1px solid var(--color-border)" }}>
      <span style={{ fontSize: 11, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-accent)", marginRight: 10 }}>
        {step}
      </span>
      <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-primary)" }}>
        {title}
      </span>
    </div>
  );
}

/**
 * Field component.
 * Labelled input with inline error display.
 */
function Field({ label, id, value, onChange, error, type = "text" }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
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

/**
 * SelectField component.
 * Labelled dropdown with inline error display.
 */
function SelectField({ label, id, value, onChange, error, options }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ borderColor: error ? "var(--color-error)" : undefined }}
      >
        <option value="">Select...</option>
        {options.map(opt => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
      {error && (
        <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>
          {error}
        </span>
      )}
    </div>
  );
}

export default InstrumentForm;