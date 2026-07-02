import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signIn, signUp } from "../auth";

/**
 * Login page component for user authentication.
 * Handles both sign in and sign up flows.
 * Redirects to dashboard on successful sign in.
 */
function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async () => {
    if (isSignUp) {
      const { error } = await signUp(email, password);
      if (error) {
        setMessage(error.message);
      } else {
        setMessage("Account created! Check your email to confirm.");
      }
    } else {
      const { error } = await signIn(email, password);
      if (error) {
        setMessage(error.message);
      } else {
        // Redirect to dashboard on successful login.
        navigate("/dashboard");
      }
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#1B3A6B",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}>
      <div style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow-md)",
        padding: "40px",
        width: "100%",
        maxWidth: 400,
      }}>
        <div style={{ marginBottom: 32, textAlign: "center" }}>
          <img src="/logo.png" alt="Instruworks" style={{ height: 36, marginBottom: 16 }} />
          <h2 style={{ fontSize: 20, fontWeight: 600, color: "var(--color-primary)", marginBottom: 4 }}>
            {isSignUp ? "Welcome." : " "}
          </h2>
          <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 0 }}>
            {isSignUp ? "Create your Instruworks account." : "Let's Certify."}
          </p>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
            Email
          </label>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
            Password
          </label>
          <input
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
          />
        </div>

        <button
          onClick={handleSubmit}
          style={{
            width: "100%",
            padding: "11px",
            background: "var(--color-primary)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius)",
            fontWeight: 600,
            fontSize: 14,
            marginBottom: 12,
          }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--color-primary-hover)"}
          onMouseLeave={e => e.currentTarget.style.background = "var(--color-primary)"}
        >
          {isSignUp ? "Create Account" : "Sign In"}
        </button>

        {message && (
          <p style={{ fontSize: 13, color: "var(--color-muted)", textAlign: "center", marginBottom: 12 }}>
            {message}
          </p>
        )}

        <button
          onClick={() => { setIsSignUp(!isSignUp); setMessage(""); }}
          style={{
            width: "100%",
            background: "none",
            border: "none",
            color: "var(--color-accent)",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {isSignUp ? "Already have an account? Sign in" : "No account? Sign up"}
        </button>
      </div>
    </div>
  );
}

export default Login;