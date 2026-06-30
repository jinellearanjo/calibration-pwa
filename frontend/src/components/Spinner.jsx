/**
 * Spinner component.
 * Displays a centered loading indicator while data is being fetched.
 *
 * @param {Object} props
 * @param {string} props.message - Optional loading message to display.
 */
function Spinner({ message = "Loading..." }) {
  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--color-bg)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "var(--font-body)",
      gap: 16,
    }}>
      <div style={{
        width: 36,
        height: 36,
        border: "3px solid var(--color-border)",
        borderTop: "3px solid var(--color-primary)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <p style={{
        fontSize: 13,
        color: "var(--color-muted)",
        letterSpacing: "0.04em",
      }}>
        {message}
      </p>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default Spinner;