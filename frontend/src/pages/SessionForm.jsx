import { useState } from "react";
import Navbar from "../components/Navbar";

/**
 * SessionForm component.
 * Allows the user to create a new calibration session by entering
 * the date, technician name, and environmental conditions.
 * Submits data to the backend via a function imported from api.js.
 *
 * @param {Object} props
 * @param {Function} props.onSubmit - Called with form data on valid submission.
 */
function SessionForm({ onSubmit }) {
  const [formData, setFormData] = useState({
    instrument_id: "",
    date: "",
    technician: "",
    temperature_c: "",
    humidity_pct: "",
    notes: "",
  });

  const [errors, setErrors] = useState({});

  function validate(field, value) {
    // Each field returns an error string or empty string if valid.
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
  }

  const hasErrors = Object.values(errors).some(Boolean);
  const requiredFields = ["instrument_id", "date", "technician", "temperature_c", "humidity_pct"];
  const allFilled = requiredFields.every(f => formData[f] !== "");

  function handleSubmit() {
    // Run full validation on all fields before submitting.
    const freshErrors = {};
    requiredFields.forEach(f => {
      freshErrors[f] = validate(f, formData[f]);
    });
    setErrors(freshErrors);
    if (Object.values(freshErrors).some(Boolean)) return;
    onSubmit(formData);
  }

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 560, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 24 }}>Calibration Session</h2>

        <Field
          label="Instrument ID"
          id="instrument_id"
          value={formData.instrument_id}
          onChange={v => updateField("instrument_id", v)}
          error={errors.instrument_id}
        />
        <Field
          label="Date"
          id="date"
          type="date"
          value={formData.date}
          onChange={v => updateField("date", v)}
          error={errors.date}
        />
        <Field
          label="Technician"
          id="technician"
          value={formData.technician}
          onChange={v => updateField("technician", v)}
          error={errors.technician}
        />
        <Field
          label="Temperature (°C)"
          id="temperature_c"
          type="number"
          value={formData.temperature_c}
          onChange={v => updateField("temperature_c", v)}
          error={errors.temperature_c}
        />
        <Field
          label="Humidity (%)"
          id="humidity_pct"
          type="number"
          value={formData.humidity_pct}
          onChange={v => updateField("humidity_pct", v)}
          error={errors.humidity_pct}
        />
        <Field
          label="Notes (optional)"
          id="notes"
          value={formData.notes}
          onChange={v => updateField("notes", v)}
          error={errors.notes}
        />

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
          Create Session
        </button>
      </div>
    </div>
  );
}

/**
 * Field component.
 * A labelled input with inline error display.
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
      <label
        htmlFor={id}
        style={{ display: "block", fontWeight: "bold", marginBottom: 4, fontSize: 13 }}
      >
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

export default SessionForm;