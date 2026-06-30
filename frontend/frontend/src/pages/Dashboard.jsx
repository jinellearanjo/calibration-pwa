import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";

/**
 * Dashboard component.
 * Main landing page after login. Shows navigation options for the
 * core calibration workflow in the order they should be completed.
 */
function Dashboard() {
  const navigate = useNavigate();

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 600, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 8 }}>Dashboard</h2>
        <p style={{ color: "grey", marginBottom: 32 }}>
          Select a step to begin or continue a calibration session.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <DashboardButton
            label="1. Register Instrument"
            onClick={() => navigate("/instrument")}
          />
          <DashboardButton
            label="2. Master Instrument"
            onClick={() => navigate("/master")}
          />
          <DashboardButton
            label="3. Calibration Session"
            onClick={() => navigate("/session")}
          />
          <DashboardButton
            label="4. Enter Readings"
            onClick={() => navigate("/readings")}
          />
          <DashboardButton
            label="5. Calculate Uncertainty"
            onClick={() => navigate("/calculation")}
          />
          <DashboardButton
            label="6. Validation Results"
            onClick={() => navigate("/results")}
          />
          <DashboardButton
            label="7. Generate Report"
            onClick={() => navigate("/report")}
          />
          <DashboardButton
            label="Session History"
            onClick={() => navigate("/history")}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * DashboardButton component.
 * A full-width button used for workflow step navigation on the dashboard.
 *
 * @param {Object} props
 * @param {string} props.label - Button label text.
 * @param {Function} props.onClick - Click handler.
 */
function DashboardButton({ label, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        padding: "14px 20px",
        textAlign: "left",
        background: "white",
        border: "1px solid black",
        cursor: "pointer",
        fontSize: 14,
        fontFamily: "sans-serif",
      }}
    >
      {label}
    </button>
  );
}

export default Dashboard;