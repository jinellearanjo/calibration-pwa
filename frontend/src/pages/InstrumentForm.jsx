import { useState } from "react";
import Navbar from "../components/Navbar";

/**
 * InstrumentForm component.
 * Two-section form for registering a new instrument under calibration.
 * Section 1: Calibration Reference Details.
 * Section 2: Unit Under Calibration (UUC) fields.
 * Submits data via onSubmit prop — no fetch calls inside this component.
 *
 * @param {Object} props
 * @param {Function} props.onSubmit - Called with combined form data on valid submission.
 */
function InstrumentForm({ onSubmit }) {
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

  // Required fields — optional fields are excluded from validation.
  const requiredRef = [
    "certificate_number", "date_of_calibration", "cal_due_date",
    "item_received_date", "date_of_issue", "customer_name", "customer_address",
  ];
  const requiredUuc = [
    "name", "type", "make", "model", "serial_number",
    "accuracy_class", "resolution", "unit", "range_min", "range_max",
  ];

  function validate(field, value) {
    const numericFields = ["accuracy_class", "resolution", "range_min", "range_max"];
    if (requiredRef.includes(field) || requiredUuc.includes(field)) {
      if (!value || !value.toString().trim()) return `${field.replace(/_/g, " ")} is required.`;
    }
    if (numericFields.includes(field) && value !== "" && isNaN(Number(value))) {
      return "Must be a number.";
    }
    return "";
  }

  function updateRef(field, value) {
    setRefData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
  }

  function updateUuc(field, value) {
    setUucData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: validate(field, value) }));
  }

  const hasErrors = Object.values(errors).some(Boolean);
  const allFilled = [...requiredRef, ...requiredUuc].every(
    f => (refData[f] || uucData[f] || "").toString().trim() !== ""
  );

  function handleSubmit() {
    // Validate all required fields before submitting.
    const freshErrors = {};
    requiredRef.forEach(f => { freshErrors[f] = validate(f, refData[f]); });
    requiredUuc.forEach(f => { freshErrors[f] = validate(f, uucData[f]); });
    setErrors(freshErrors);
    if (Object.values(freshErrors).some(Boolean)) return;
    onSubmit({ ...refData, ...uucData });
  }

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 640, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 24 }}>Register Instrument</h2>

        {/* Section 1 */}
        <SectionHeading title="Calibration Reference Details" />
        <Field label="Certificate Number" id="certificate_number" value={refData.certificate_number} onChange={v => updateRef("certificate_number", v)} error={errors.certificate_number} />
        <Field label="Date of Calibration" id="date_of_calibration" type="date" value={refData.date_of_calibration} onChange={v => updateRef("date_of_calibration", v)} error={errors.date_of_calibration} />
        <Field label="Calibration Due Date" id="cal_due_date" type="date" value={refData.cal_due_date} onChange={v => updateRef("cal_due_date", v)} error={errors.cal_due_date} />
        <Field label="Item Received Date" id="item_received_date" type="date" value={refData.item_received_date} onChange={v => updateRef("item_received_date", v)} error={errors.item_received_date} />
        <Field label="Date of Issue" id="date_of_issue" type="date" value={refData.date_of_issue} onChange={v => updateRef("date_of_issue", v)} error={errors.date_of_issue} />
        <Field label="Customer Name" id="customer_name" value={refData.customer_name} onChange={v => updateRef("customer_name", v)} error={errors.customer_name} />
        <Field label="Customer Address" id="customer_address" value={refData.customer_address} onChange={v => updateRef("customer_address", v)} error={errors.customer_address} />

        {/* Section 2 */}
        <SectionHeading title="Unit Under Calibration (UUC)" />
        <Field label="Instrument Name" id="name" value={uucData.name} onChange={v => updateUuc("name", v)} error={errors.name} />
        <SelectField
          label="Type"
          id="type"
          value={uucData.type}
          onChange={v => updateUuc("type", v)}
          error={errors.type}
          options={["Pressure", "Temperature", "Electrical", "Weighing"]}
        />
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
          options={["bar", "psi", "kPa", "MPa", "mbar"]}
        />
        <Field label="Range Min" id="range_min" type="number" value={uucData.range_min} onChange={v => updateUuc("range_min", v)} error={errors.range_min} />
        <Field label="Range Max" id="range_max" type="number" value={uucData.range_max} onChange={v => updateUuc("range_max", v)} error={errors.range_max} />
        <Field label="Tag Number (optional)" id="tag_number" value={uucData.tag_number} onChange={v => updateUuc("tag_number", v)} error={errors.tag_number} />
        <Field label="Calibration Carried At (optional)" id="calibration_carried_at" value={uucData.calibration_carried_at} onChange={v => updateUuc("calibration_carried_at", v)} error={errors.calibration_carried_at} />
        <Field label="Dial Size (optional)" id="dial_size" value={uucData.dial_size} onChange={v => updateUuc("dial_size", v)} error={errors.dial_size} />
        <Field label="Mounting Orientation (optional)" id="mounting_orientation" value={uucData.mounting_orientation} onChange={v => updateUuc("mounting_orientation", v)} error={errors.mounting_orientation} />
        <Field label="Instrument Location (optional)" id="instrument_location" value={uucData.instrument_location} onChange={v => updateUuc("instrument_location", v)} error={errors.instrument_location} />
        <Field label="Medium Used (optional)" id="medium_used" value={uucData.medium_used} onChange={v => updateUuc("medium_used", v)} error={errors.medium_used} />

        <button
          onClick={handleSubmit}
          disabled={hasErrors || !allFilled}
          style={{
            width: "100%",
            padding: "12px",
            marginTop: 8,
            background: hasErrors || !allFilled ? "#ccc" : "black",
            color: "white",
            border: "none",
            cursor: hasErrors || !allFilled ? "not-allowed" : "pointer",
            fontSize: 14,
          }}
        >
          Register Instrument
        </button>
      </div>
    </div>
  );
}

/**
 * SectionHeading component.
 * Blue section heading for form groups.
 *
 * @param {Object} props
 * @param {string} props.title - Heading text.
 */
function SectionHeading({ title }) {
  return (
    <h3 style={{
      color: "blue",
      fontSize: 14,
      fontWeight: "bold",
      margin: "24px 0 12px",
      borderBottom: "1px solid blue",
      paddingBottom: 4,
    }}>
      {title}
    </h3>
  );
}

/**
 * Field component.
 * Labelled input with inline error display.
 *
 * @param {Object} props
 * @param {string} props.label - Field label.
 * @param {string} props.id - Input id.
 * @param {string} props.value - Current value.
 * @param {Function} props.onChange - Change handler.
 * @param {string} props.error - Error message if invalid.
 * @param {string} props.type - Input type.
 */
function Field({ label, id, value, onChange, error, type = "text" }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontWeight: "bold", marginBottom: 4, fontSize: 13 }}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%",
          padding: "8px 10px",
          border: `1px solid ${error ? "red" : "black"}`,
          fontSize: 14,
          boxSizing: "border-box",
        }}
      />
      {error && (
        <span style={{ color: "red", fontSize: 12, marginTop: 2, display: "block" }}>
          {error}
        </span>
      )}
    </div>
  );
}

/**
 * SelectField component.
 * Labelled dropdown with inline error display.
 *
 * @param {Object} props
 * @param {string} props.label - Field label.
 * @param {string} props.id - Select id.
 * @param {string} props.value - Current value.
 * @param {Function} props.onChange - Change handler.
 * @param {string} props.error - Error message if invalid.
 * @param {string[]} props.options - Dropdown options.
 */
function SelectField({ label, id, value, onChange, error, options }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontWeight: "bold", marginBottom: 4, fontSize: 13 }}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%",
          padding: "8px 10px",
          border: `1px solid ${error ? "red" : "black"}`,
          fontSize: 14,
          boxSizing: "border-box",
          background: "white",
        }}
      >
        <option value="">Select...</option>
        {options.map(opt => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
      {error && (
        <span style={{ color: "red", fontSize: 12, marginTop: 2, display: "block" }}>
          {error}
        </span>
      )}
    </div>
  );
}

export default InstrumentForm;