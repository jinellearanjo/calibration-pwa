"""tests/test_roles_and_review_endpoints.py

Tests for the roles/review-workflow feature's new endpoints:
- GET/PUT /api/profile, GET /api/profiles
- POST/GET /api/role-requests, PUT .../approve, PUT .../deny
- PUT /api/sessions/{id}/review/approve, /reject
- The review gate wired into GET /api/sessions/{id}/report

Each endpoint's require_tier gating is tested for both an allowed and a
rejected tier, since that's the entire point of this feature.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import main
import auth
import database

app = main.app
client = TestClient(app)

SESSION_ID = "99999999-9999-9999-9999-999999999999"
REQUEST_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _as(user_id: str, title: str):
    """Context-manager-less helper: set both dependency overrides for a
    given caller, for the duration of the block. Cleared after every test
    via the fixture below, to avoid the exact cross-file dependency-
    override leakage documented in test_master_instruments_shared.py."""
    app.dependency_overrides[auth.get_current_user_id] = lambda: user_id
    app.dependency_overrides[auth.get_current_user_title] = lambda: title


def setup_function():
    # Every other test file in this suite sets get_current_user_id at
    # module level (once, at import/collection time) and relies on it
    # persisting on the shared main.app singleton for all its own tests.
    # A blanket app.dependency_overrides.clear() in a teardown here would
    # wipe those out too, breaking whichever file happens to execute
    # after this one - restore the suite-wide convention instead of
    # clearing, and only ever touch the two keys this file actually uses.
    app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides.pop(auth.get_current_user_title, None)


def teardown_function():
    app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides.pop(auth.get_current_user_title, None)


# ── /api/profile, /api/profiles ───────────────────────────────────────────

def test_get_my_profile_returns_default_viewer_shape_when_no_profile_row():
    _as("user-1", "Viewer")
    with patch.object(main.database, "get_profile", return_value=None):
        resp = client.get("/api/profile")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Viewer"


def test_get_my_profile_returns_real_profile_when_present():
    _as("user-1", "TM")
    with patch.object(main.database, "get_profile", return_value={"id": "user-1", "full_name": "Jinelle", "title": "TM"}):
        resp = client.get("/api/profile")
    assert resp.status_code == 200
    assert resp.json()["title"] == "TM"


def test_update_my_profile_only_touches_full_name():
    _as("user-1", "Viewer")
    with patch.object(main.database, "update_profile", return_value={"id": "user-1", "full_name": "New Name", "title": "Viewer"}) as mock_update:
        resp = client.put("/api/profile", json={"full_name": "New Name"})
    assert resp.status_code == 200
    mock_update.assert_called_once_with(
        "user-1", full_name="New Name", employee_id=None, site_location=None, department=None
    )


def test_list_all_profiles_allowed_for_full_edit():
    _as("user-1", "QM")
    with patch.object(main.database, "list_profiles", return_value=[{"id": "user-1"}, {"id": "user-2"}]):
        resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_all_profiles_rejected_for_viewer():
    _as("user-1", "Viewer")
    resp = client.get("/api/profiles")
    assert resp.status_code == 403


def test_list_all_profiles_rejected_for_cert_creation_tier():
    """Confirms this is full_edit-only, not full_edit+cert_creation like
    master instruments - Cal Tech etc. shouldn't see the activity view."""
    _as("user-1", "Cal Tech")
    resp = client.get("/api/profiles")
    assert resp.status_code == 403


# ── Account deactivation ───────────────────────────────────────────────────

def test_deactivate_my_account_works_for_any_authenticated_user():
    _as("user-1", "Viewer")
    with patch.object(main.database, "update_profile") as mock_update:
        resp = client.put("/api/profile/deactivate")
    assert resp.status_code == 200
    mock_update.assert_called_once_with("user-1", is_active=False)


def test_deactivate_other_user_rejected_for_non_full_edit():
    _as("user-1", "Cal Tech")
    resp = client.put("/api/profiles/some-other-user/deactivate")
    assert resp.status_code == 403


def test_deactivate_other_user_allowed_for_full_edit():
    _as("reviewer-1", "QM")
    with patch.object(main.database, "update_profile") as mock_update:
        resp = client.put("/api/profiles/target-user/deactivate")
    assert resp.status_code == 200
    mock_update.assert_called_once_with("target-user", is_active=False)


def test_reactivate_user_allowed_for_full_edit():
    _as("reviewer-1", "MD")
    with patch.object(main.database, "update_profile") as mock_update:
        resp = client.put("/api/profiles/target-user/reactivate")
    assert resp.status_code == 200
    mock_update.assert_called_once_with("target-user", is_active=True)


def test_reactivate_user_rejected_for_non_full_edit():
    _as("user-1", "Engineer")
    resp = client.put("/api/profiles/target-user/reactivate")
    assert resp.status_code == 403


# ── /api/role-requests ─────────────────────────────────────────────────────

def test_submit_role_request_succeeds_for_any_authenticated_user():
    _as("user-1", "Viewer")
    with patch.object(main.database, "get_pending_role_change_request_for_user", return_value=None), \
         patch.object(main.database, "insert_role_change_request", return_value={"id": REQUEST_ID}) as mock_insert:
        resp = client.post("/api/role-requests", json={"requested_title": "Cal Tech", "reason": "I do calibrations now"})
    assert resp.status_code == 200
    mock_insert.assert_called_once()
    assert mock_insert.call_args[0][0]["requested_title"] == "Cal Tech"


def test_submit_role_request_rejects_invalid_title():
    _as("user-1", "Viewer")
    resp = client.post("/api/role-requests", json={"requested_title": "Wizard"})
    assert resp.status_code == 400


def test_submit_role_request_rejects_second_simultaneous_pending_request():
    _as("user-1", "Viewer")
    with patch.object(main.database, "get_pending_role_change_request_for_user", return_value={"id": "existing-pending"}):
        resp = client.post("/api/role-requests", json={"requested_title": "Cal Tech"})
    assert resp.status_code == 400
    assert "pending" in resp.json()["detail"].lower()


def test_resubmitting_after_denial_is_allowed():
    """A denied request must not permanently block resubmission -
    get_pending_role_change_request_for_user only checks for a PENDING
    request, so a denied one (status != pending) doesn't count."""
    _as("user-1", "Viewer")
    with patch.object(main.database, "get_pending_role_change_request_for_user", return_value=None), \
         patch.object(main.database, "insert_role_change_request", return_value={"id": "new-request"}):
        resp = client.post("/api/role-requests", json={"requested_title": "Cal Tech"})
    assert resp.status_code == 200


def test_list_role_requests_rejected_for_non_full_edit():
    _as("user-1", "Cal Tech")
    resp = client.get("/api/role-requests")
    assert resp.status_code == 403


def test_approve_role_request_applies_title_and_records_reviewer():
    _as("reviewer-1", "QM")
    pending = [{"id": REQUEST_ID, "user_id": "requester-1", "requested_title": "Cal Tech", "status": "pending"}]
    with patch.object(main.database, "list_role_change_requests", return_value=pending), \
         patch.object(main.database, "update_role_change_request") as mock_update_req, \
         patch.object(main.database, "update_profile") as mock_update_profile:
        resp = client.put(f"/api/role-requests/{REQUEST_ID}/approve", json={})
    assert resp.status_code == 200
    mock_update_req.assert_called_once_with(REQUEST_ID, "approved", "reviewer-1")
    mock_update_profile.assert_called_once_with("requester-1", title="Cal Tech")


def test_approve_role_request_404s_on_unknown_request():
    _as("reviewer-1", "QM")
    with patch.object(main.database, "list_role_change_requests", return_value=[]):
        resp = client.put(f"/api/role-requests/{REQUEST_ID}/approve", json={})
    assert resp.status_code == 404


def test_deny_role_request_does_not_touch_profile():
    _as("reviewer-1", "TM")
    with patch.object(main.database, "update_role_change_request") as mock_update_req, \
         patch.object(main.database, "update_profile") as mock_update_profile:
        resp = client.put(f"/api/role-requests/{REQUEST_ID}/deny", json={"reason": "Not needed for your role"})
    assert resp.status_code == 200
    mock_update_req.assert_called_once_with(REQUEST_ID, "denied", "reviewer-1")
    mock_update_profile.assert_not_called()


def test_approve_and_deny_role_requests_rejected_for_cert_creation_tier():
    _as("user-1", "Cal Tech")
    assert client.put(f"/api/role-requests/{REQUEST_ID}/approve", json={}).status_code == 403
    assert client.put(f"/api/role-requests/{REQUEST_ID}/deny", json={}).status_code == 403


# ── Session review endpoints ─────────────────────────────────────────────

def test_approve_session_review_rejected_for_non_full_edit():
    _as("user-1", "Cal Tech")
    resp = client.put(f"/api/sessions/{SESSION_ID}/review/approve", json={})
    assert resp.status_code == 403


def test_approve_session_review_succeeds_for_full_edit():
    _as("reviewer-1", "MR")
    with patch.object(main.database, "resolve_session_review") as mock_resolve:
        resp = client.put(f"/api/sessions/{SESSION_ID}/review/approve", json={"review_note": "Looks fine now"})
    assert resp.status_code == 200
    mock_resolve.assert_called_once_with(
        SESSION_ID, approved=True, reviewed_by="reviewer-1", review_note="Looks fine now"
    )


def test_reject_session_review_succeeds_for_full_edit():
    _as("reviewer-1", "MD")
    with patch.object(main.database, "resolve_session_review") as mock_resolve:
        resp = client.put(f"/api/sessions/{SESSION_ID}/review/reject", json={"review_note": "Master still expired"})
    assert resp.status_code == 200
    mock_resolve.assert_called_once_with(
        SESSION_ID, approved=False, reviewed_by="reviewer-1", review_note="Master still expired"
    )


# ── Report generation gate ────────────────────────────────────────────────

def test_report_generation_proceeds_normally_for_clean_session():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "clean"}
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.validation, "check_master_instrument_validity", return_value=[]), \
         patch.object(main.reporting, "generate_pdf_report", return_value="fake-file-response") as mock_gen:
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 200
    mock_gen.assert_called_once_with(SESSION_ID)


def test_report_generation_flags_and_blocks_when_validity_check_fails():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "clean"}
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.validation, "check_master_instrument_validity",
                      return_value=["Master instrument 'X' calibration expired 2026-01-01."]), \
         patch.object(main.database, "flag_session_for_review") as mock_flag, \
         patch.object(main.reporting, "generate_pdf_report") as mock_gen:
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"]
    mock_flag.assert_called_once()
    mock_gen.assert_not_called()


def test_report_generation_blocked_while_pending_review():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "pending_review", "review_note": "Awaiting QM sign-off"}
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.reporting, "generate_pdf_report") as mock_gen:
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 403
    assert "Awaiting QM sign-off" in resp.json()["detail"]
    mock_gen.assert_not_called()


def test_report_generation_blocked_when_rejected():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "rejected", "review_note": "Master still expired"}
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.reporting, "generate_pdf_report") as mock_gen:
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 403
    mock_gen.assert_not_called()


def test_rejected_report_shows_the_standard_hod_message():
    """Exact wording specified by Instruworks - the person whose session
    got rejected should see this, not just the reviewer's raw technical
    note by itself."""
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "rejected", "review_note": "Master expired 2026-01-01"}
    with patch.object(main.database, "get_session", return_value=session):
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    detail = resp.json()["detail"]
    assert "Attention: Some readings or calibration inputs may not be accurate" in detail
    assert "consult the concerned HOD" in detail
    # The reviewer's specific note should still be there too, as extra detail.
    assert "Master expired 2026-01-01" in detail


def test_rejected_report_shows_standard_message_even_with_no_reviewer_note():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "rejected", "review_note": None}
    with patch.object(main.database, "get_session", return_value=session):
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert "consult the concerned HOD" in resp.json()["detail"]


def test_report_generation_proceeds_once_approved():
    _as("user-1", "Cal Tech")
    session = {"id": SESSION_ID, "review_status": "approved"}
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.reporting, "generate_pdf_report", return_value="fake-file-response") as mock_gen:
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 200
    mock_gen.assert_called_once_with(SESSION_ID)


def test_report_generation_404s_when_session_missing():
    _as("user-1", "Cal Tech")
    with patch.object(main.database, "get_session", return_value=None):
        resp = client.get(f"/api/sessions/{SESSION_ID}/report")
    assert resp.status_code == 404


# ── Flagged sessions reviewer queue ───────────────────────────────────────

def test_list_flagged_sessions_allowed_for_full_edit():
    _as("reviewer-1", "MR")
    flagged = [{"id": SESSION_ID, "review_status": "pending_review", "review_note": "Master expired"}]
    with patch.object(main.database, "list_flagged_sessions", return_value=flagged):
        resp = client.get("/api/sessions/flagged")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_flagged_sessions_rejected_for_cert_creation_tier():
    _as("user-1", "Cal Tech")
    resp = client.get("/api/sessions/flagged")
    assert resp.status_code == 403


def test_list_flagged_sessions_rejected_for_viewer():
    _as("user-1", "Viewer")
    resp = client.get("/api/sessions/flagged")
    assert resp.status_code == 403