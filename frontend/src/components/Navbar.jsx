import { useNavigate, useLocation } from "react-router-dom";
import { signOut } from "../auth";

/**
 * Navbar component.
 * Displays the Instruworks logo, app name, and sign out button.
 * Highlights the active route with a left border accent.
 */
function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const handleSignOut = async () => {
    await signOut();
    navigate("/login");
  };

  const navLinks = [
    { label: "Dashboard", path: "/dashboard" },
    { label: "History", path: "/history" },
  ];

  return (
    <nav style={{
      background: "var(--color-surface)",
      borderBottom: "1px solid var(--color-border)",
      boxShadow: "var(--shadow-sm)",
      padding: "0 32px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      height: 60,
      position: "sticky",
      top: 0,
      zIndex: 100,
    }}>
      {/* Left: logo and nav links */}
      <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
        <div
          style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
          onClick={() => navigate("/dashboard")}
        >
          <img
            src="/logo.png"
            alt="Instruworks"
            style={{ height: 32, objectFit: "contain" }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {navLinks.map(link => {
            const isActive = location.pathname === link.path;
            return (
              <button
                key={link.path}
                onClick={() => navigate(link.path)}
                style={{
                  background: "none",
                  border: "none",
                  padding: "6px 14px",
                  color: isActive ? "var(--color-primary)" : "var(--color-muted)",
                  fontWeight: isActive ? 600 : 400,
                  borderBottom: isActive ? "2px solid var(--color-primary)" : "2px solid transparent",
                  borderRadius: 0,
                  fontSize: 14,
                  cursor: "pointer",
                  transition: "color 0.15s",
                }}
              >
                {link.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: sign out */}
      <button
        onClick={handleSignOut}
        style={{
          background: "none",
          border: "1px solid var(--color-border)",
          padding: "7px 16px",
          color: "var(--color-text)",
          borderRadius: "var(--radius)",
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        Sign Out
      </button>
    </nav>
  );
}

export default Navbar;