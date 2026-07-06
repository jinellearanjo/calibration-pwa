import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Spinner from "../components/Spinner";
import SessionPicker from "../components/SessionPicker";
import { getResults, downloadReport } from "../api";

/**
 * ReportPage component.
 * Displays the current session status and provides buttons to download
 * the session report as PDF or Excel. Download buttons are disabled
 * if the session status is REJECTED.
 *
 * Status is fetched live via getResults(sessionId) rather than taken as
 * a hardcoded prop - a previous version defaulted to a fixed "ACCEPTED"
 * prop that was never actually wired to real data, so the reject-disable
 * logic never reflected a session's real status. Downloads now go
 * through api.js's downloadReport (attaches the JWT auth token, uses the
 * shared BASE_URL) instead of a raw window.open call to a hardcoded
 * http://127.0.0.1:8000 URL, which would have both failed auth on a
 * protected endpoint and broken entirely outside local development.
 *
 * Reachable two ways:
 *  - Directly from ResultsView with :sessionId already in the URL
 *    (/report/:sessionId) - behaves exactly as before, no picker shown.
 *  - From the Dashboard card with no session in the URL (/report) - a
 *    SessionPicker is shown above the content, and both download buttons
 *    stay disabled until a session is chosen. Works across refreshes and
 *    new tabs - relies only on the URL param or the in-memory picker
 *    selection, never localStorage or navigation state.
 */
function ReportPage() {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();

  const [pickedSessionId, setPickedSessionId] = useState(null);
  const effectiveSessionId = urlSessionId || pickedSessionId;
  const showPicker = !urlSessionId;

  const [status, setStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [statusError, setStatusError] = useState(null);
  const [downloadingFormat, setDownloadingFormat] = useState(null);
  const [downloadError, setDownloadError] = useState(null);

  const loadStatus = useCallback(() => {
    if (!effectiveSessionId) {
      setStatus(null);
      setStatusError(null);
      return;
    }
    setLoadingStatus(true);
    setStatusError(null);
    getResults(effectiveSessionId)
      .then(data => {
        setStatus(data.status);
        setLoadingStatus(false);
      })
      .catch(err => {
        setStatusError(err.message);
        setLoadingStatus(false);
      });
  }, [effectiveSessionId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const noSessionSelected = !effectiveSessionId;
  const isRejected = status === "REJECTED";
  const downloadsDisabled = noSessionSelected || isRejected || loadingStatus;

  async function handleDownload(format) {
    if (!effectiveSessionId) return;
    setDownloadingFormat(format);
    setDownloadError(null);
    try {
      await downloadReport(effectiveSessionId, format);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadingFormat(null);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 600, margin: "0 auto", padding: "48px 32px" }}>

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

        {showPicker && (
          <SessionPicker selectedSessionId={pickedSessionId} onSelect={setPickedSessionId} />
        )}

        <div style={{ opacity: noSessionSelected ? 0.5 : 1, transition: "opacity 0.15s" }}>

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
            {loadingStatus ? (
              <Spinner message="Loading status..." />
            ) : statusError ? (
              <p style={{ fontSize: 13, color: "var(--color-error)" }}>{statusError}</p>
            ) : (
              <p style={{ fontSize: 16, fontWeight: 700, color: "var(--color-primary)" }}>
                {status || "—"}
              </p>
            )}
          </div>

          {downloadError && (
            <p style={{ fontSize: 13, color: "var(--color-error)", marginBottom: 16 }}>
              {downloadError}
            </p>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            <button
              onClick={() => handleDownload("pdf")}
              disabled={downloadsDisabled || downloadingFormat !== null}
              style={{
                width: "100%",
                padding: "14px",
                background: downloadsDisabled ? "var(--color-border)" : "var(--color-primary)",
                color: "white",
                border: "none",
                borderRadius: "var(--radius)",
                fontSize: 14,
                fontWeight: 600,
                cursor: (downloadsDisabled || downloadingFormat !== null) ? "not-allowed" : "pointer",
                letterSpacing: "0.02em",
              }}
              onMouseEnter={e => { if (!downloadsDisabled) e.currentTarget.style.background = "var(--color-primary-hover)"; }}
              onMouseLeave={e => { if (!downloadsDisabled) e.currentTarget.style.background = "var(--color-primary)"; }}
            >
              {downloadingFormat === "pdf" ? "Generating PDF..." : "Download PDF Certificate"}
            </button>
            <button
              onClick={() => handleDownload("excel")}
              disabled={downloadsDisabled || downloadingFormat !== null}
              style={{
                width: "100%",
                padding: "14px",
                background: "white",
                color: downloadsDisabled ? "var(--color-muted)" : "var(--color-primary)",
                border: `1px solid ${downloadsDisabled ? "var(--color-border)" : "var(--color-primary)"}`,
                borderRadius: "var(--radius)",
                fontSize: 14,
                fontWeight: 600,
                cursor: (downloadsDisabled || downloadingFormat !== null) ? "not-allowed" : "pointer",
                letterSpacing: "0.02em",
              }}
            >
              {downloadingFormat === "excel" ? "Generating Excel..." : "Download Excel Report"}
            </button>
          </div>

          {isRejected && !noSessionSelected && (
            <p style={{ fontSize: 13, color: "var(--color-error)", textAlign: "center", marginBottom: 24 }}>
              Session must be validated before a report can be generated.
            </p>
          )}
        </div>

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