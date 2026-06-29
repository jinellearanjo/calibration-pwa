import { useNavigate } from "react-router-dom";
import { signOut } from "../auth";

/**
 * Navbar component.
 * Displays the application name and a sign out button on every protected page.
 * Redirects to the login page after successful sign out.
 */
function Navbar() {
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    // Redirect to login after signing out.
    navigate("/login");
  };

  return (
    <nav style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "12px 24px",
      borderBottom: "1px solid black",
      fontFamily: "sans-serif",
    }}>
      <span style={{ fontWeight: "bold", fontSize: 16 }}>
        Calibration Uncertainty Calculator
      </span>
      <button
        onClick={handleSignOut}
        style={{
          background: "none",
          border: "1px solid black",
          padding: "6px 14px",
          cursor: "pointer",
          fontSize: 14,
        }}
      >
        Sign Out
      </button>
    </nav>
  );
}

export default Navbar;