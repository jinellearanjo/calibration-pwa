import { useState } from "react";
import Navbar from "../components/Navbar";

/**
 * ReadingsForm component.
 * Displays a table for entering ascending and descending calibration readings.
 * Mean error and hysteresis are calculated live on every keystroke.
 * Submits data via onRecalculate prop — no fetch calls inside this component.
 *
 * @param {Object} props
 * @param {string} props.uucIndicatorType - The UUC indicator type displayed above the table.
 * @param {string} props.calibrationSequence - The calibration sequence name displayed above the table.
 * @param {number} props.pointCount - Number of calibration points to display.
 * @param {Function} props.onRecalculate - Called with readings data when button is clicked.
 */
function ReadingsForm({ uucIndicatorType = "", calibrationSequence = "", pointCount = 5, onRecalculate }) {
  const initialRows = Array.from({ length: pointCount }, (_, i) => ({
    point_number: i + 1,
    nominal_value: "",
    measured_value_up: "",
    measured_value_down: "",
    // Mean error and hysteresis are derived — never entered manually.
    mean_error: null,
    hysteresis: null,
  }));

  const [rows, setRows] = useState(initialRows);
  const [autoSelectSequence, setAutoSelectSequence] = useState(true);
  const [autoGeneratePoints, setAutoGeneratePoints] = useState(true);

  function updateRow(index, field, value) {
    setRows(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };

      const up = parseFloat(updated[index].measured_value_up);
      const down = parseFloat(updated[index].measured_value_down);
      const nominal = parseFloat(updated[index].nominal_value);

      // Recalculate mean error and hysteresis on every keystroke per spec.
      // Mean error: average of ascending and descending minus nominal value.
      if (!isNaN(up) && !isNaN(down) && !isNaN(nominal)) {
        updated[index].mean_error = ((up + down) / 2 - nominal).toFixed(4);
      } else {
        updated[index].mean_error = null;
      }

      // Hysteresis: absolute difference between ascending and descending.
      if (!isNaN(up) && !isNaN(down)) {
        updated[index].hysteresis = Math.abs(up - down).toFixed(4);
      } else {
        updated[index].hysteresis = null;
      }

      return updated;
    });
  }

  function handleRecalculate() {
    onRecalculate(rows);
  }

  function loadDemoData() {
    // Populate with example values so the team can test without real data.
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

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 24 }}>Calibration Readings</h2>

        {/* Read-only info fields */}
        <div style={{ display: "flex", gap: 24, marginBottom: 16 }}>
          <ReadOnlyField label="UUC Indicator Type" value={uucIndicatorType} />
          <ReadOnlyField label="Calibration Sequence" value={calibrationSequence} />
        </div>

        {/* Checkboxes */}
        <div style={{ marginBottom: 12 }}>
          <CheckboxField
            id="auto-sequence"
            label="Auto-select Sequence from UUC Accuracy"
            checked={autoSelectSequence}
            onChange={setAutoSelectSequence}
          />
          <CheckboxField
            id="auto-points"
            label="Auto-generate points from UUC range"
            checked={autoGeneratePoints}
            onChange={setAutoGeneratePoints}
          />
        </div>

        {/* Info bar */}
        <div style={{
          background: "#f3f4f6",
          padding: "8px 12px",
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
        }}>
          <span>{calibrationSequence || "No sequence selected"}</span>
          <button
            type="button"
            onClick={loadDemoData}
            style={{ background: "none", border: "none", color: "blue", cursor: "pointer", fontSize: 13 }}
          >
            Load Demo Data
          </button>
        </div>

        {/* Readings table */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "black", color: "white" }}>
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
                <tr key={row.point_number} style={{ background: index % 2 === 0 ? "white" : "#f9fafb" }}>
                  <td style={tdStyle}>{row.point_number}</td>
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={row.nominal_value}
                      onChange={e => updateRow(index, "nominal_value", e.target.value)}
                      style={inputStyle}
                    />
                  </td>
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={row.measured_value_up}
                      onChange={e => updateRow(index, "measured_value_up", e.target.value)}
                      style={inputStyle}
                    />
                  </td>
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={row.measured_value_down}
                      onChange={e => updateRow(index, "measured_value_down", e.target.value)}
                      style={inputStyle}
                    />
                  </td>
                  {/* Read-only calculated fields */}
                  <td style={{ ...tdStyle, textAlign: "center" }}>
                    {row.mean_error !== null ? `±${row.mean_error}` : "—"}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "center" }}>
                    {row.hysteresis !== null ? row.hysteresis : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recalculate button */}
        <button
          onClick={handleRecalculate}
          style={{
            width: "100%",
            padding: "14px",
            marginTop: 20,
            background: "blue",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 14,
            fontWeight: "bold",
          }}
        >
          Recalculate Metrology Uncertainty
        </button>
      </div>
    </div>
  );
}

/**
 * ReadOnlyField component.
 * Displays a labelled read-only text value.
 */
function ReadOnlyField({ label, value }) {
  return (
    <div style={{ flex: 1 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: "bold", marginBottom: 4 }}>
        {label}
      </label>
      <div style={{ padding: "8px 10px", border: "1px solid #ccc", fontSize: 13, background: "#f9fafb" }}>
        {value || "—"}
      </div>
    </div>
  );
}

/**
 * CheckboxField component.
 * A labelled checkbox input.
 */
function CheckboxField({ id, label, checked, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={e => onChange(e.target.checked)}
      />
      <label htmlFor={id} style={{ fontSize: 13 }}>{label}</label>
    </div>
  );
}

// Table cell styles defined outside the component to avoid recreation on every render.
const thStyle = {
  padding: "10px 12px",
  textAlign: "left",
  fontWeight: "bold",
  border: "1px solid black",
};

const tdStyle = {
  padding: "6px 8px",
  border: "1px solid #d1d5db",
};

const inputStyle = {
  width: "100%",
  padding: "4px 6px",
  border: "1px solid #d1d5db",
  fontSize: 13,
  boxSizing: "border-box",
};

export default ReadingsForm;