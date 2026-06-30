import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";

/**
 * ReportPage component.
 * Displays the current session status and provides buttons to download
 * the session report as PDF or Excel. Download buttons are disabled
 * if the session status is REJECTED.
 *
 * @param {Object} props
 * @param {string} props.status - The current validation status of the session.
 */
function ReportPage({ status = "ACCEPTED" }) {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const isRejected = status === "REJECTED";

  const onDownloadPdf = () => {
    window.open(`http://127.0.0.1:8000/api/sessions/${sessionId}/report?format=pdf`, "_blank");
  };

  const onDownloadExcel = () => {
    window.open(`http://127.0.0.1:8000/api/sessions/${sessionId}/report?format=excel`, "_blank");
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 600, margin: "0 auto", padding: "48px 32px" }}>

        {/* Page header */}
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 07
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Generate Report
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Download the calibration certificate for this session.
          </p>
        </div>

        {/* Status card */}
        <div style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderLeft: "4px solid var(--color-primary)",
          borderRadius: "var(--radius)",
          padding: "20px 24px",
          marginBottom: 24,
          boxShadow: "var(--shadow-sm)",
        }}>
          <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-muted)", marginBottom: 6 }}>
            Session Status
          </p>
          <p style={{ fontSize: 16, fontWeight: 700, color: "var(--color-primary)" }}>
            {status}
          </p>
        </div>

        {/* Download buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
          <button
            onClick={onDownloadPdf}
            disabled={isRejected}
            style={{
              width: "100%",
              padding: "14px",
              background: isRejected ? "var(--color-border)" : "var(--color-primary)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 14,
              fontWeight: 600,
              cursor: isRejected ? "not-allowed" : "pointer",
              letterSpacing: "0.02em",
            }}
            onMouseEnter={e => { if (!isRejected) e.currentTarget.style.background = "var(--color-primary-hover)"; }}
            onMouseLeave={e => { if (!isRejected) e.currentTarget.style.background = "var(--color-primary)"; }}
          >
            Download PDF Certificate
          </button>
          <button
            onClick={onDownloadExcel}
            disabled={isRejected}
            style={{
              width: "100%",
              padding: "14px",
              background: "white",
              color: isRejected ? "var(--color-muted)" : "var(--color-primary)",
              border: `1px solid ${isRejected ? "var(--color-border)" : "var(--color-primary)"}`,
              borderRadius: "var(--radius)",
              fontSize: 14,
              fontWeight: 600,
              cursor: isRejected ? "not-allowed" : "pointer",
              letterSpacing: "0.02em",
            }}
          >
            Download Excel Report
          </button>
        </div>

        {/* Rejected message */}
        {isRejected && (
          <p style={{ fontSize: 13, color: "var(--color-error)", textAlign: "center", marginBottom: 24 }}>
            Session must be validated before a report can be generated.
          </p>
        )}

        {/* Back button */}
        <button
          onClick={() => navigate("/history")}
          style={{
            width: "100%",
            padding: "10px",
            background: "none",
            border: "none",
            color: "var(--color-muted)",
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          Back to History
        </button>
      </div>
    </div>
  );
}

export default ReportPage;