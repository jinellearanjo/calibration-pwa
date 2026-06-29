import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import StatusBadge from "../components/StatusBadge";

/**
 * ResultsView component.
 * Displays the validation result for a calibration session including
 * status, uncertainty values, acceptance limit, CMC, and any flags.
 * All data is fetched from the backend using the session ID from the URL.
 */
function ResultsView() {
  const { sessionId } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch validation results when the component mounts.
    fetch(`http://127.0.0.1:8000/api/sessions/${sessionId}/validate`)
      .then(r => r.json())
      .then(data => {
        setResult(data);
        setLoading(false);
      })
      .catch(err => {
        setError("Failed to load validation results.");
        setLoading(false);
      });
  }, [sessionId]);

  if (loading) return <div style={{ fontFamily: "sans-serif", padding: 24 }}>Loading...</div>;
  if (error) return <div style={{ fontFamily: "sans-serif", padding: 24 }}>{error}</div>;

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <Navbar />
      <div style={{ maxWidth: 600, margin: "40px auto", padding: "0 24px" }}>
        <h2 style={{ marginBottom: 24 }}>Validation Results</h2>

        {/* Compliance status */}
        <div style={{ marginBottom: 16 }}>
          <span style={{ fontWeight: "bold", marginRight: 8 }}>
            Compliance Report:
          </span>
          <StatusBadge status={result.status} />
        </div>

        {/* Uncertainty values */}
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
          <tbody>
            <ResultRow
              label="Final Applied Uncertainty"
              value={result.final_applied_uncertainty !== null
                ? `± ${result.final_applied_uncertainty}`
                : "—"}
            />
            <ResultRow
              label="Acceptance Limit"
              value={result.acceptance_limit !== null
                ? result.acceptance_limit
                : "—"}
            />
            <ResultRow
              label="CMC"
              value={result.cmc !== null ? result.cmc : "—"}
            />
          </tbody>
        </table>

        {/* Flags — only shown when present */}
        {result.flags && result.flags.length > 0 && (
          <div>
            <p style={{ fontWeight: "bold", marginBottom: 8 }}>Flags:</p>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {result.flags.map((flag, index) => (
                <li key={index} style={{ marginBottom: 4 }}>
                  {flag}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ResultRow component.
 * A single labelled row in the results table.
 *
 * @param {Object} props
 * @param {string} props.label - Row label.
 * @param {string|number} props.value - Row value.
 */
function ResultRow({ label, value }) {
  return (
    <tr>
      <td style={{
        padding: "10px 12px",
        fontWeight: "bold",
        border: "1px solid black",
        width: "60%",
      }}>
        {label}
      </td>
      <td style={{
        padding: "10px 12px",
        border: "1px solid black",
      }}>
        {value}
      </td>
    </tr>
  );
}

export default ResultsView;