import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";

/**
 * Dashboard component.
 * Main landing page after login. Shows navigation cards for the
 * core calibration workflow in the order they should be completed.
 */
function Dashboard() {
  const navigate = useNavigate();

  const steps = [
    { number: "01", label: "Register Instrument", description: "Add calibration reference details and instrument under calibration.", path: "/instrument" },
    { number: "02", label: "Master Instrument", description: "Search, select, or register the reference standard used.", path: "/master" },
    { number: "03", label: "Calibration Session", description: "Set the session date, technician, and environmental conditions.", path: "/session" },
    { number: "04", label: "Enter Readings", description: "Record ascending and descending measurements for each calibration point.", path: "/readings" },
    { number: "05", label: "Calculate Uncertainty", description: "Run the GUM-compliant uncertainty calculation for this session.", path: "/calculation" },
    { number: "06", label: "Validation Results", description: "Review the compliance status and uncertainty budget.", path: "/results" },
    { number: "07", label: "Generate Report", description: "Download the calibration certificate as PDF or Excel.", path: "/report" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 32px" }}>

        {/* Page header */}
        <div style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Calibration Workflow
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Dashboard
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Complete each step in order to produce a GUM-compliant calibration certificate.
          </p>
        </div>

        {/* Step cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {steps.map(step => (
            <StepCard key={step.number} step={step} onClick={() => navigate(step.path)} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * StepCard component.
 * A clickable workflow step card with a step number, label, and description.
 *
 * @param {Object} props
 * @param {Object} props.step - Step data object.
 * @param {Function} props.onClick - Click handler.
 */
function StepCard({ step, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderLeft: "3px solid var(--color-primary)",
        borderRadius: "var(--radius)",
        padding: "20px 20px 20px 18px",
        textAlign: "left",
        cursor: "pointer",
        boxShadow: "var(--shadow-sm)",
        transition: "box-shadow 0.15s, transform 0.15s",
        width: "100%",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = "var(--shadow-md)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = "var(--shadow-sm)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      <span style={{
        display: "inline-block",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.06em",
        color: "var(--color-accent)",
        marginBottom: 8,
        fontFamily: "var(--font-mono)",
      }}>
        {step.number}
      </span>
      <p style={{ fontWeight: 600, fontSize: 14, color: "var(--color-primary)", marginBottom: 6 }}>
        {step.label}
      </p>
      <p style={{ fontSize: 13, color: "var(--color-muted)", lineHeight: 1.5 }}>
        {step.description}
      </p>
    </button>
  );
}

export default Dashboard;