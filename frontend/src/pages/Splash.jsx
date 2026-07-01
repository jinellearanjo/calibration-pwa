import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

/**
 * Splash component.
 * Opening screen displayed before the login page.
 * Fades in on load and navigates to login on click.
 */
function Splash() {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);

    useEffect(() => {
      // Fade in on mount.
      setTimeout(() => setVisible(true), 100);
      // Auto-redirect to login after 4 seconds.
      const timer = setTimeout(() => navigate("/login"), 4000);
      return () => clearTimeout(timer);
    }, []);

  return (
    <div
      onClick={() => navigate("/login")}
      style={{
        minHeight: "100vh",
        background: "#1B3A6B",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease",
        userSelect: "none",
      }}
    >
      {/* Logo */}
      <img
        src="/logo.png"
        alt="Instruworks"
        style={{
            height: 84,
            marginBottom: 50,
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(12px)",
            transition: "opacity 0.8s ease 0.8s, transform 0.8s ease 0.8s",
  }}
/>

      {/* Divider */}
      <div style={{
        width: 40,
        height: 2,
        background: "#2A7B6F",
        marginBottom: 32,
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease 0.4s",
      }} />

      {/* Title */}
      <h1 style={{
        fontFamily: "'Inter', sans-serif",
        fontSize: 28,
        fontWeight: 300,
        color: "#FFFFFF",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        marginBottom: 12,
        textAlign: "center",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: "opacity 0.8s ease 0.5s, transform 0.8s ease 0.5s",
      }}>
        Calibration Uncertainty
      </h1>
      <h1 style={{
        fontFamily: "'Inter', sans-serif",
        fontSize: 28,
        fontWeight: 700,
        color: "#FFFFFF",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        marginBottom: 48,
        textAlign: "center",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: "opacity 0.8s ease 0.6s, transform 0.8s ease 0.6s",
      }}>
        Calculator
      </h1>

      {/* Subtitle */}
      <p style={{
        fontFamily: "'Inter', sans-serif",
        fontSize: 12,
        fontWeight: 400,
        color: "rgba(255,255,255,0.45)",
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        marginBottom: 80,
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease 0.8s",
      }}>
        ISO/IEC 17025:2017 Compliant
      </p>

      {/* Click prompt */}
      <p style={{
        fontFamily: "'Inter', sans-serif",
        fontSize: 11,
        fontWeight: 400,
        color: "rgba(255,255,255,0.3)",
        letterSpacing: "0.15em",
        textTransform: "uppercase",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease 1.2s",
      }}>
        Click anywhere to continue
      </p>
    </div>
  );
}

export default Splash;