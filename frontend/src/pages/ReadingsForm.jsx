import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import { useState } from "react";
import Navbar from "../components/Navbar";

/**
 * ReadingsForm component.
 * Displays a table for entering ascending and descending calibration readings.
 * Mean error and hysteresis are calculated live on every keystroke.
 *
 * @param {Object} props
 * @param {string} props.uucIndicatorType - The UUC indicator type.
 * @param {string} props.calibrationSequence - The calibration sequence name.
 * @param {number} props.pointCount - Number of calibration points.
 * @param {Function} props.onRecalculate - Called with readings data when button is clicked.
 */
function ReadingsForm({
  uucIndicatorType = "",
  calibrationSequence = "",
  pointCount = 5,
  onRecalculate,
}) {
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

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

  function updateRow(index, field, value) {
    setIsDirty(true); // Mark form as dirty when any reading changes.
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

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 32px" }}>

        {/* Page header */}
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

        {/* Info card */}
        <div style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius)",
          padding: "20px 24px",
          boxShadow: "var(--shadow-sm)",
          marginBottom: 16,
        }}>
          <div style={{ display: "flex", gap: 32, marginBottom: 16 }}>
            <ReadOnlyField label="UUC Indicator Type" value={uucIndicatorType} />
            <ReadOnlyField label="Calibration Sequence" value={calibrationSequence} />
          </div>
          <div style={{ display: "flex", gap: 24 }}>
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
        </div>

        {/* Info bar */}
        <div style={{
          background: "#F0F4FF",
          border: "1px solid #C7D7FF",
          borderRadius: "var(--radius)",
          padding: "10px 16px",
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
        }}>
          <span style={{ color: "var(--color-primary)", fontWeight: 500 }}>
            {calibrationSequence || "No sequence selected"}
          </span>
          <button
            onClick={loadDemoData}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-accent)",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            Load Demo Data
          </button>
        </div>

        {/* Readings table */}
        <div style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius)",
          boxShadow: "var(--shadow-sm)",
          overflow: "hidden",
          marginBottom: 20,
        }}>
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
                  <tr
                    key={row.point_number}
                    style={{
                      background: index % 2 === 0 ? "white" : "#F9FAFB",
                      borderBottom: "1px solid var(--color-border)",
                    }}
                  >
                    <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--color-accent)" }}>
                      {String(row.point_number).padStart(2, "0")}
                    </td>
                    <td style={tdStyle}>
                      <input type="number" value={row.nominal_value} onChange={e => updateRow(index, "nominal_value", e.target.value)} style={inputStyle} />
                    </td>
                    <td style={tdStyle}>
                      <input type="number" value={row.measured_value_up} onChange={e => updateRow(index, "measured_value_up", e.target.value)} style={inputStyle} />
                    </td>
                    <td style={tdStyle}>
                      <input type="number" value={row.measured_value_down} onChange={e => updateRow(index, "measured_value_down", e.target.value)} style={inputStyle} />
                    </td>
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

        {/* Actions */}
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={() => onRecalculate && onRecalculate(rows)}
            style={{
              flex: 1,
              padding: "13px",
              background: "var(--color-primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              letterSpacing: "0.02em",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--color-primary-hover)"}
            onMouseLeave={e => e.currentTarget.style.background = "var(--color-primary)"}
          >
            Recalculate Metrology Uncertainty
          </button>
          <button
            onClick={() => safeNavigate("/dashboard")}
            style={{
              padding: "13px 20px",
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

function ReadOnlyField({ label, value }) {
  return (
    <div style={{ flex: 1 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-muted)", marginBottom: 6 }}>
        {label}
      </label>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>
        {value || "—"}
      </div>
    </div>
  );
}

function CheckboxField({ id, label, checked, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ accentColor: "var(--color-primary)", width: 14, height: 14 }}
      />
      <label htmlFor={id} style={{ fontSize: 13, color: "var(--color-text)", cursor: "pointer" }}>
        {label}
      </label>
    </div>
  );
}

const thStyle = {
  padding: "12px 16px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "white",
};

const tdStyle = {
  padding: "8px 12px",
  color: "var(--color-text)",
};

const inputStyle = {
  width: "100%",
  padding: "6px 10px",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius)",
  fontSize: 13,
  fontFamily: "var(--font-mono)",
  background: "white",
  boxSizing: "border-box",
};

export default ReadingsForm;