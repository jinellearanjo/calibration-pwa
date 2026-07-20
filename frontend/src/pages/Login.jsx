import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signIn, signUp } from "../auth";

// Groups the 9 stored job titles into 3 broader categories, purely so the
// sign-up form doesn't dump all 9 options into one dropdown at once. The
// value actually stored (and used for permissions + certificate display)
// is still the specific job title, not this grouping - see backend
// auth.py's TITLE_PERMISSION_TIER for where that mapping actually lives.
const ROLE_GROUPS = {
  "Management (Full Access)": ["QM", "TM", "MR", "MD"],
  "Technician (Certificate Creation)": ["Cal Tech", "Engineer", "Admin", "Lab Staff"],
  "Viewer (Read Only)": ["Viewer"],
};

/**
 * Login page component for user authentication.
 * Handles both sign in and sign up flows. Sign-up additionally collects
 * name, role/job title, employee ID, site location, and department,
 * passed through to Supabase Auth as sign-up metadata - a database
 * trigger (handle_new_user, see backend/migrations) reads this metadata
 * to create the corresponding profiles row automatically.
 * Redirects to dashboard on successful sign in.
 */
function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [roleGroup, setRoleGroup] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [siteLocation, setSiteLocation] = useState("");
  const [department, setDepartment] = useState("");
  const [signUpErrors, setSignUpErrors] = useState({});

  const jobTitleOptions = roleGroup ? ROLE_GROUPS[roleGroup] : [];

  const handleRoleGroupChange = (group) => {
    setRoleGroup(group);
    // Viewer is the only option in its group - auto-select it rather
    // than making the person pick a job title of one.
    const options = ROLE_GROUPS[group] || [];
    setJobTitle(options.length === 1 ? options[0] : "");
  };

  const validateSignUp = () => {
    const errors = {};
    if (!fullName.trim()) errors.fullName = "Required.";
    if (!roleGroup) errors.roleGroup = "Required.";
    if (!jobTitle) errors.jobTitle = "Required.";
    setSignUpErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (isSignUp) {
      if (!validateSignUp()) return;
      const { error } = await signUp(email, password, {
        full_name: fullName,
        title: jobTitle,
        employee_id: employeeId || null,
        site_location: siteLocation || null,
        department: department || null,
      });
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
      padding: "24px 0",
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
          <img src="/logo.png" alt="Instruworks" style={{ height: 84, marginBottom: 16 }} />
          <h2 style={{ fontSize: 22, fontWeight: 350, color: "var(--color-primary)", letterSpacing: "0.04em", marginBottom: 4 }}>
            {isSignUp ? "Join Instruworks." : "Welcome."}
          </h2>
          <p style={{ fontSize: 12, color: "var(--color-muted)" }}>
            {isSignUp ? "Create your account to continue." : "Sign in to continue."}
          </p>
        </div>

        {isSignUp && (
          <>
            <Field label="Full Name" id="signup_full_name" value={fullName} onChange={setFullName} error={signUpErrors.fullName} />
            <SelectField
              label="Role"
              id="signup_role_group"
              value={roleGroup}
              onChange={handleRoleGroupChange}
              error={signUpErrors.roleGroup}
              options={Object.keys(ROLE_GROUPS)}
            />
            {roleGroup && jobTitleOptions.length > 1 && (
              <SelectField
                label="Job Title"
                id="signup_job_title"
                value={jobTitle}
                onChange={setJobTitle}
                error={signUpErrors.jobTitle}
                options={jobTitleOptions}
              />
            )}
            <Field label="Employee ID / Payroll Number" id="signup_employee_id" value={employeeId} onChange={setEmployeeId} />
            <Field label="Site / Facility Location" id="signup_site_location" value={siteLocation} onChange={setSiteLocation} />
            <Field label="Assigned Lab / Department" id="signup_department" value={department} onChange={setDepartment} />
          </>
        )}

        <div style={{ marginBottom: 16 }}>
          <label htmlFor="email" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label htmlFor="password" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
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
          {isSignUp ? "Create Account" : "Let's Certify"}
        </button>

        {message && (
          <p style={{ fontSize: 13, color: "var(--color-muted)", textAlign: "center", marginBottom: 12 }}>
            {message}
          </p>
        )}

        <button
          onClick={() => { setIsSignUp(!isSignUp); setMessage(""); setSignUpErrors({}); }}
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

function Field({ label, id, value, onChange, error }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ borderColor: error ? "var(--color-error)" : undefined }}
      />
      {error && <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>{error}</span>}
    </div>
  );
}

function SelectField({ label, id, value, onChange, error, options }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)} style={{ borderColor: error ? "var(--color-error)" : undefined }}>
        <option value="">Select...</option>
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
      {error && <span style={{ color: "var(--color-error)", fontSize: 12, marginTop: 4, display: "block" }}>{error}</span>}
    </div>
  );
}

export default Login;