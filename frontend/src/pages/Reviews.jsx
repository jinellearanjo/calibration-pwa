import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import {
  getMyProfile,
  getAllProfiles,
  listRoleChangeRequests,
  approveRoleChangeRequest,
  denyRoleChangeRequest,
  getFlaggedSessions,
  approveSessionReview,
  rejectSessionReview,
  deactivateUserAccount,
  reactivateUserAccount,
} from "../api";

const FULL_EDIT_TITLES = ["QM", "TM", "MR", "MD"];

/**
 * Reviews page - full_edit tier only (QM/TM/MR/MD).
 * Three sections: pending job-title change requests, sessions flagged
 * for review by check_master_instrument_validity, and an all-users
 * activity view. The backend enforces all of this independently (every
 * action here 403s for a non-full_edit caller regardless of what this
 * page shows) - this page's own access check is just so a Viewer/
 * Technician sees a clear message instead of a page full of failed
 * requests.
 */
function Reviews() {
  const [myTitle, setMyTitle] = useState(null);
  const [checkingAccess, setCheckingAccess] = useState(true);

  const [requests, setRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [requestNotes, setRequestNotes] = useState({});
  const [requestActionError, setRequestActionError] = useState("");

  const [flaggedSessions, setFlaggedSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [sessionNotes, setSessionNotes] = useState({});
  const [sessionActionError, setSessionActionError] = useState("");

  const [profiles, setProfiles] = useState([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [profileActionError, setProfileActionError] = useState("");

  useEffect(() => {
    getMyProfile()
      .then(p => setMyTitle(p.title))
      .finally(() => setCheckingAccess(false));
  }, []);

  const hasAccess = FULL_EDIT_TITLES.includes(myTitle);

  const loadRequests = useCallback(() => {
    setLoadingRequests(true);
    listRoleChangeRequests("pending")
      .then(setRequests)
      .finally(() => setLoadingRequests(false));
  }, []);

  const loadFlaggedSessions = useCallback(() => {
    setLoadingSessions(true);
    getFlaggedSessions()
      .then(setFlaggedSessions)
      .finally(() => setLoadingSessions(false));
  }, []);

  const loadProfiles = useCallback(() => {
    setLoadingProfiles(true);
    getAllProfiles()
      .then(setProfiles)
      .finally(() => setLoadingProfiles(false));
  }, []);

  useEffect(() => {
    if (hasAccess) {
      loadRequests();
      loadFlaggedSessions();
      loadProfiles();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAccess]);

  const handleApproveRequest = async (id) => {
    setRequestActionError("");
    try {
      await approveRoleChangeRequest(id, requestNotes[id]);
      loadRequests();
      loadProfiles();
    } catch (err) {
      setRequestActionError(err.message);
    }
  };

  const handleDenyRequest = async (id) => {
    setRequestActionError("");
    try {
      await denyRoleChangeRequest(id, requestNotes[id]);
      loadRequests();
    } catch (err) {
      setRequestActionError(err.message);
    }
  };

  const handleApproveSession = async (id) => {
    setSessionActionError("");
    try {
      await approveSessionReview(id, sessionNotes[id]);
      loadFlaggedSessions();
    } catch (err) {
      setSessionActionError(err.message);
    }
  };

  const handleRejectSession = async (id) => {
    setSessionActionError("");
    try {
      await rejectSessionReview(id, sessionNotes[id]);
      loadFlaggedSessions();
    } catch (err) {
      setSessionActionError(err.message);
    }
  };

  const handleToggleActive = async (userId, currentlyActive) => {
    setProfileActionError("");
    try {
      if (currentlyActive) {
        await deactivateUserAccount(userId);
      } else {
        await reactivateUserAccount(userId);
      }
      loadProfiles();
    } catch (err) {
      setProfileActionError(err.message);
    }
  };

  if (checkingAccess) {
    return (
      <>
        <Navbar />
        <div style={{ padding: 32 }}>Loading...</div>
      </>
    );
  }

  if (!hasAccess) {
    return (
      <>
        <Navbar />
        <div style={{ maxWidth: 480, margin: "80px auto", padding: 24, textAlign: "center" }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Access Restricted</h2>
          <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 16 }}>
            This page is only available to QM, TM, MR, and MD. Your current title is{" "}
            <strong>{myTitle || "Viewer"}</strong>. Request a different job title from your{" "}
            <Link to="/account">Account</Link> page if you believe this is wrong.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 600, color: "var(--color-primary)", marginBottom: 4 }}>Reviews</h1>
      <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 32 }}>
        Pending job-title requests, flagged sessions, and account activity.
      </p>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          Pending Job-Title Requests {requests.length > 0 && `(${requests.length})`}
        </h2>
        {loadingRequests ? (
          <p style={{ fontSize: 13, color: "var(--color-muted)" }}>Loading...</p>
        ) : requests.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--color-muted)" }}>No pending requests.</p>
        ) : (
          requests.map(r => (
            <div key={r.id} style={cardStyle}>
              <p style={{ fontSize: 13, marginBottom: 4 }}>
                Requesting <strong>{r.requested_title}</strong>
              </p>
              {r.reason && <p style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 8 }}>"{r.reason}"</p>}
              <input
                type="text"
                placeholder="Note (optional)"
                value={requestNotes[r.id] || ""}
                onChange={e => setRequestNotes({ ...requestNotes, [r.id]: e.target.value })}
                style={{ marginBottom: 8, width: "100%" }}
              />
              <button onClick={() => handleApproveRequest(r.id)} style={approveButtonStyle}>Approve</button>
              <button onClick={() => handleDenyRequest(r.id)} style={{ ...denyButtonStyle, marginLeft: 8 }}>Deny</button>
            </div>
          ))
        )}
        {requestActionError && <p style={{ fontSize: 13, color: "var(--color-error)", marginTop: 8 }}>{requestActionError}</p>}
      </section>

      <section style={{ marginBottom: 40, borderTop: "1px solid var(--color-border)", paddingTop: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          Flagged Sessions {flaggedSessions.length > 0 && `(${flaggedSessions.length})`}
        </h2>
        {loadingSessions ? (
          <p style={{ fontSize: 13, color: "var(--color-muted)" }}>Loading...</p>
        ) : flaggedSessions.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--color-muted)" }}>No sessions awaiting review.</p>
        ) : (
          flaggedSessions.map(s => (
            <div key={s.id} style={cardStyle}>
              <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                {s.instruments?.name || "Unknown instrument"} ({s.instruments?.type})
              </p>
              <p style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 8 }}>{s.review_note}</p>
              <input
                type="text"
                placeholder="Note (optional, overrides the flag reason above)"
                value={sessionNotes[s.id] || ""}
                onChange={e => setSessionNotes({ ...sessionNotes, [s.id]: e.target.value })}
                style={{ marginBottom: 8, width: "100%" }}
              />
              <button onClick={() => handleApproveSession(s.id)} style={approveButtonStyle}>Approve</button>
              <button onClick={() => handleRejectSession(s.id)} style={{ ...denyButtonStyle, marginLeft: 8 }}>Reject</button>
            </div>
          ))
        )}
        {sessionActionError && <p style={{ fontSize: 13, color: "var(--color-error)", marginTop: 8 }}>{sessionActionError}</p>}
      </section>

      <section style={{ borderTop: "1px solid var(--color-border)", paddingTop: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>All Users</h2>
        {loadingProfiles ? (
          <p style={{ fontSize: 13, color: "var(--color-muted)" }}>Loading...</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--color-border)" }}>
                <th style={{ padding: "6px 8px" }}>Name</th>
                <th style={{ padding: "6px 8px" }}>Title</th>
                <th style={{ padding: "6px 8px" }}>Department</th>
                <th style={{ padding: "6px 8px" }}>Status</th>
                <th style={{ padding: "6px 8px" }}></th>
              </tr>
            </thead>
            <tbody>
              {profiles.map(p => (
                <tr key={p.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td style={{ padding: "6px 8px" }}>{p.full_name || "-"}</td>
                  <td style={{ padding: "6px 8px" }}>{p.title}</td>
                  <td style={{ padding: "6px 8px" }}>{p.department || "-"}</td>
                  <td style={{ padding: "6px 8px" }}>
                    {p.is_active === false ? (
                      <span style={{ color: "var(--color-error)" }}>Deactivated</span>
                    ) : (
                      <span>Active</span>
                    )}
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <button
                      onClick={() => handleToggleActive(p.id, p.is_active !== false)}
                      style={p.is_active === false ? approveButtonStyle : denyButtonStyle}
                    >
                      {p.is_active === false ? "Reactivate" : "Deactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {profileActionError && <p style={{ fontSize: 13, color: "var(--color-error)", marginTop: 8 }}>{profileActionError}</p>}
      </section>
      </div>
    </>
  );
}

const cardStyle = {
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius)",
  padding: 16,
  marginBottom: 12,
};

const approveButtonStyle = {
  padding: "6px 14px",
  background: "var(--color-primary)",
  color: "white",
  border: "none",
  borderRadius: "var(--radius)",
  fontWeight: 600,
  fontSize: 12,
  cursor: "pointer",
};

const denyButtonStyle = {
  ...approveButtonStyle,
  background: "var(--color-error)",
};

export default Reviews;