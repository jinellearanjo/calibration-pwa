import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getMyProfile, updateMyProfile, deactivateMyAccount, submitRoleChangeRequest } from "../api";
import { signOut } from "../auth";

// Requestable titles, grouped the same way as the sign-up form - a
// person can request a different job title within either group (most
// commonly a Viewer requesting Cal Tech/Engineer/etc.), but not Viewer
// itself, since that's the default rather than something to request.
const REQUESTABLE_TITLE_GROUPS = {
  "Management (Full Access)": ["QM", "TM", "MR", "MD"],
  "Technician (Certificate Creation)": ["Cal Tech", "Engineer", "Admin", "Lab Staff"],
};

/**
 * Account page.
 * Shows the current user's own profile (name, job title, employee ID,
 * site location, department), lets them edit the display-only fields,
 * submit a request for a different job title, and deactivate their own
 * account ("delete account" - see deactivateMyAccount's docstring in
 * api.js for why this deactivates rather than truly deletes).
 */
function Account() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const [fullName, setFullName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [siteLocation, setSiteLocation] = useState("");
  const [department, setDepartment] = useState("");

  const [requestGroup, setRequestGroup] = useState("");
  const [requestTitle, setRequestTitle] = useState("");
  const [requestReason, setRequestReason] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [submittingRequest, setSubmittingRequest] = useState(false);

  const [showDeactivateConfirm, setShowDeactivateConfirm] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [deactivateError, setDeactivateError] = useState("");

  const loadProfile = useCallback(() => {
    setLoading(true);
    getMyProfile()
      .then(p => {
        setProfile(p);
        setFullName(p.full_name || "");
        setEmployeeId(p.employee_id || "");
        setSiteLocation(p.site_location || "");
        setDepartment(p.department || "");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveMessage("");
    try {
      await updateMyProfile({
        full_name: fullName,
        employee_id: employeeId,
        site_location: siteLocation,
        department: department,
      });
      setSaveMessage("Saved.");
    } catch (err) {
      setSaveMessage(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitRoleRequest = async () => {
    if (!requestTitle) return;
    setSubmittingRequest(true);
    setRequestMessage("");
    try {
      await submitRoleChangeRequest(requestTitle, requestReason || undefined);
      setRequestMessage("Request submitted. A QM/TM/MR/MD will review it.");
      setRequestGroup("");
      setRequestTitle("");
      setRequestReason("");
    } catch (err) {
      setRequestMessage(err.message);
    } finally {
      setSubmittingRequest(false);
    }
  };

  const handleDeactivate = async () => {
    setDeactivating(true);
    setDeactivateError("");
    try {
      await deactivateMyAccount();
      await signOut();
      navigate("/login");
    } catch (err) {
      setDeactivateError(err.message);
      setDeactivating(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 32 }}>Loading account...</div>;
  }

  const requestTitleOptions = requestGroup ? REQUESTABLE_TITLE_GROUPS[requestGroup] : [];

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "32px 24px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 600, color: "var(--color-primary)", marginBottom: 4 }}>Account</h1>
      <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 32 }}>
        Job title: <strong>{profile?.title || "Viewer"}</strong> - to change it, submit a request below.
      </p>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Profile</h2>

        <Field label="Full Name" id="account_full_name" value={fullName} onChange={setFullName} />
        <Field label="Employee ID / Payroll Number" id="account_employee_id" value={employeeId} onChange={setEmployeeId} />
        <Field label="Site / Facility Location" id="account_site_location" value={siteLocation} onChange={setSiteLocation} />
        <Field label="Assigned Lab / Department" id="account_department" value={department} onChange={setDepartment} />

        <button onClick={handleSaveProfile} disabled={saving} style={buttonStyle}>
          {saving ? "Saving..." : "Save Changes"}
        </button>
        {saveMessage && <p style={{ fontSize: 13, color: "var(--color-muted)", marginTop: 8 }}>{saveMessage}</p>}
      </section>

      <section style={{ marginBottom: 40, borderTop: "1px solid var(--color-border)", paddingTop: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Request a Different Job Title</h2>
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 16 }}>
          Reviewed by a QM/TM/MR/MD. If denied, you can submit a new request afterward.
        </p>

        <SelectField
          label="Role"
          id="account_request_group"
          value={requestGroup}
          onChange={g => { setRequestGroup(g); setRequestTitle(""); }}
          options={Object.keys(REQUESTABLE_TITLE_GROUPS)}
        />
        {requestGroup && (
          <SelectField
            label="Job Title"
            id="account_request_title"
            value={requestTitle}
            onChange={setRequestTitle}
            options={requestTitleOptions}
          />
        )}
        <Field label="Reason (optional)" id="account_request_reason" value={requestReason} onChange={setRequestReason} />

        <button onClick={handleSubmitRoleRequest} disabled={!requestTitle || submittingRequest} style={buttonStyle}>
          {submittingRequest ? "Submitting..." : "Submit Request"}
        </button>
        {requestMessage && <p style={{ fontSize: 13, color: "var(--color-muted)", marginTop: 8 }}>{requestMessage}</p>}
      </section>

      <section style={{ borderTop: "1px solid var(--color-border)", paddingTop: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-error)", marginBottom: 4 }}>Delete Account</h2>
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 16 }}>
          This deactivates your account rather than permanently deleting it - any instruments, sessions, or
          certificates you've created stay exactly as they are. You'll be signed out immediately and won't be
          able to log back in unless a QM/TM/MR/MD reactivates your account.
        </p>

        {!showDeactivateConfirm ? (
          <button onClick={() => setShowDeactivateConfirm(true)} style={dangerButtonStyle}>
            Delete Account
          </button>
        ) : (
          <div style={{ background: "#fdf0f0", border: "1px solid var(--color-error)", borderRadius: "var(--radius)", padding: 16 }}>
            <p style={{ fontSize: 13, marginBottom: 12 }}>
              Are you sure? This will sign you out immediately.
            </p>
            <button onClick={handleDeactivate} disabled={deactivating} style={dangerButtonStyle}>
              {deactivating ? "Deactivating..." : "Yes, deactivate my account"}
            </button>
            <button
              onClick={() => setShowDeactivateConfirm(false)}
              style={{ ...buttonStyle, background: "none", color: "var(--color-text)", marginLeft: 8 }}
            >
              Cancel
            </button>
            {deactivateError && <p style={{ fontSize: 13, color: "var(--color-error)", marginTop: 8 }}>{deactivateError}</p>}
          </div>
        )}
      </section>
    </div>
  );
}

const buttonStyle = {
  padding: "9px 18px",
  background: "var(--color-primary)",
  color: "white",
  border: "none",
  borderRadius: "var(--radius)",
  fontWeight: 600,
  fontSize: 13,
  cursor: "pointer",
};

const dangerButtonStyle = {
  ...buttonStyle,
  background: "var(--color-error)",
};

function Field({ label, id, value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <input id={id} type="text" value={value} onChange={e => onChange(e.target.value)} />
    </div>
  );
}

function SelectField({ label, id, value, onChange, options }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={id} style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6, color: "var(--color-text)" }}>{label}</label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)}>
        <option value="">Select...</option>
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    </div>
  );
}

export default Account;
