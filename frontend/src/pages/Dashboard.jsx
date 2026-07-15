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
    { number: "04", label: "Enter Readings", description: "Pick an existing session below - it'll take you straight to the right category's readings form.", path: "/history" },
    { number: "05", label: "Calculate Uncertainty", description: "Run the uncertainty calculation for this session.", path: "/calculation" },
    { number: "06", label: "Validate Results", description: "Review the compliance status and uncertainty budget.", path: "/results" },
    { number: "07", label: "Generate Certificate", description: "Generate the calibration certificate as PDF or Excel.", path: "/report" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Calibration Workflow
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Dashboard
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Complete each step in order to produce a calibration certificate.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {steps.map(step => (
            <StepCard key={step.number} step={step} onClick={step.path ? () => navigate(step.path) : null} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * StepCard component.
 * A clickable workflow step card with a step number, label, and description.
 * Cards with no path are displayed as non-interactive, informational steps.
 *
 * @param {Object} props
 * @param {Object} props.step - Step data object.
 * @param {Function|null} props.onClick - Click handler, or null if the step is not directly navigable.
 */
function StepCard({ step, onClick }) {
  const isDisabled = !onClick;

  return (
    <button
      onClick={onClick || undefined}
      disabled={isDisabled}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderLeft: `3px solid ${isDisabled ? "var(--color-border)" : "var(--color-primary)"}`,
        borderRadius: "var(--radius)",
        padding: "20px 20px 20px 18px",
        textAlign: "left",
        cursor: isDisabled ? "default" : "pointer",
        boxShadow: "var(--shadow-sm)",
        transition: "box-shadow 0.15s, transform 0.15s",
        width: "100%",
        opacity: isDisabled ? 0.5 : 1,
      }}
      onMouseEnter={e => {
        if (!isDisabled) {
          e.currentTarget.style.boxShadow = "var(--shadow-md)";
          e.currentTarget.style.transform = "translateY(-1px)";
        }
      }}
      onMouseLeave={e => {
        if (!isDisabled) {
          e.currentTarget.style.boxShadow = "var(--shadow-sm)";
          e.currentTarget.style.transform = "translateY(0)";
        }
      }}
    >
      <span style={{
        display: "inline-block",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.06em",
        color: isDisabled ? "var(--color-muted)" : "var(--color-accent)",
        marginBottom: 8,
        fontFamily: "var(--font-mono)",
      }}>
        {step.number}
      </span>
      <p style={{ fontWeight: 600, fontSize: 14, color: isDisabled ? "var(--color-muted)" : "var(--color-primary)", marginBottom: 6 }}>
        {step.label}
      </p>
      <p style={{ fontSize: 13, color: "var(--color-muted)", lineHeight: 1.5 }}>
        {step.description}
      </p>
    </button>
  );
}

export default Dashboard;