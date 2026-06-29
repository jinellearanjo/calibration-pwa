/**
 * StatusBadge component.
 * Displays a calibration session status string in bold black text.
 * No colours, no background, no border, no icons — plain bold text only.
 *
 * @param {Object} props
 * @param {string} props.status - One of ACCEPTED, REVIEW REQUIRED, or REJECTED.
 */
function StatusBadge({ status }) {
  return (
    <span style={{ fontWeight: "bold", fontFamily: "sans-serif" }}>
      {status}
    </span>
  );
}

export default StatusBadge;