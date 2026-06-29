import { useState } from "react";
import { signIn, signUp } from "../auth";

/**
 * Login page component for user authentication.
 * Handles both sign in and sign up flows.
 */
function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [message, setMessage] = useState("");

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
        setMessage("Logged in successfully!");
      }
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "100px auto", fontFamily: "sans-serif" }}>
      <h2>{isSignUp ? "Sign Up" : "Sign In"}</h2>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        style={{ display: "block", width: "100%", marginBottom: 10, padding: 8 }}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        style={{ display: "block", width: "100%", marginBottom: 10, padding: 8 }}
      />
      <button onClick={handleSubmit} style={{ width: "100%", padding: 10 }}>
        {isSignUp ? "Sign Up" : "Sign In"}
      </button>
      <p style={{ marginTop: 10, color: "grey" }}>{message}</p>
      <button
        onClick={() => setIsSignUp(!isSignUp)}
        style={{ background: "none", border: "none", color: "blue", cursor: "pointer" }}
      >
        {isSignUp ? "Already have an account? Sign in" : "No account? Sign up"}
      </button>
    </div>
  );
}

export default Login;