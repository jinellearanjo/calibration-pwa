import { useParams } from "react-router-dom";
import { downloadReport } from "../api";

/**
 * ReportPage component.
 * Displays the current session status and provides buttons to download
 * the session report as PDF or Excel. Download buttons are disabled
 * if the session status is REJECTED.
 *
 * @param {Object} props
 * @param {string} props.status - The current validation status of the session.
 */ 
export function ReportPage({ status }) {
  const { sessionId } = useParams();

  // Reports can only be generated for validated sessions.
  // Disabled state prevents requesting a file that doesn't exist.
  const isRejected = status === "REJECTED";

  const onDownloadPdf = () => {
    downloadReport(sessionId, "pdf");
  };

  const onDownloadExcel = () => {
    downloadReport(sessionId, "excel");
  };

  return (
    <main style={{ maxWidth: 480, margin: "0 auto", padding: "48px 24px", fontFamily: "sans-serif", color: "black" }}>
      <p style={{ fontSize: 18, fontWeight: "bold" }}>
        Session status: {status}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
        <button
          type="button"
          onClick={onDownloadPdf}
          disabled={isRejected}
          style={{ width: "100%", borderRadius: 999, border: "1px solid black", padding: "12px 0", fontWeight: 500, opacity: isRejected ? 0.4 : 1, cursor: isRejected ? "not-allowed" : "pointer", background: "white" }}
        >
          Download PDF
        </button>
        <button
          type="button"
          onClick={onDownloadExcel}
          disabled={isRejected}
          style={{ width: "100%", borderRadius: 999, border: "1px solid black", padding: "12px 0", fontWeight: 500, opacity: isRejected ? 0.4 : 1, cursor: isRejected ? "not-allowed" : "pointer", background: "white" }}
        >
          Download Excel
        </button>
      </div>
      {isRejected && (
        <p style={{ fontSize: 14, marginTop: 16 }}>
          Session must be validated before a report can be generated.
        </p>
      )}
    </main>
  );
}

export default ReportPage;