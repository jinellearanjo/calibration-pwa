import { useNavigate } from "react-router-dom";

/**
 * NotFound component.
 * Displayed when a user navigates to an unknown route.
 */
function NotFound() {
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--color-bg)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "var(--font-body)",
    }}>
      <div style={{ textAlign: "center" }}>
        <p style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--color-accent)",
          marginBottom: 16,
        }}>
          404
        </p>
        <h1 style={{
          fontSize: 28,
          fontWeight: 700,
          color: "var(--color-primary)",
          marginBottom: 12,
        }}>
          Page not found
        </h1>
        <p style={{
          fontSize: 14,
          color: "var(--color-muted)",
          marginBottom: 32,
        }}>
          The page you are looking for does not exist or has been moved.
        </p>
        <button
          onClick={() => navigate("/dashboard")}
          style={{
            padding: "10px 24px",
            background: "var(--color-primary)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 14,
            fontWeight: 500,
            cursor: "pointer",
          }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--color-primary-hover)"}
          onMouseLeave={e => e.currentTarget.style.background = "var(--color-primary)"}
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}

export default NotFound;