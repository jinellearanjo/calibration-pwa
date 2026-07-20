"""tests/test_maybe_single_and_date_parsing.py

Regression tests for two small, previously-unfixed bugs from the handover's
"Known, Not Yet Fixed" list:

1. get_calibration_reference and get_acceptance_limit used PostgREST's
   .single(), which raises an exception when zero rows match, instead of
   returning None. Both functions' callers already had "if not result:
   raise 404 / return REJECTED" logic in place - but that logic never ran,
   because .single() crashed first. The unhandled crash also bypassed
   CORSMiddleware's header injection, which is why it showed up in the
   browser as a misleading "blocked by CORS policy" error rather than a
   clean 404. Fixed by switching both to .maybe_single(), which returns
   None on zero rows instead of raising.

2. _format_date in reporting.py used datetime.fromisoformat directly,
   which rejects a trailing "Z" (Zulu/UTC) suffix on Python <3.11, even
   though it's valid ISO 8601 and Supabase timestamps commonly come back
   with one. Fixed with a defensive .replace("Z", "+00:00") before parsing.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import database
import main
import auth
from modules.reporting import _format_date

app = main.app
app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
client = TestClient(app)

SESSION_ID = "44444444-4444-4444-4444-444444444444"


# ── get_calibration_reference / get_acceptance_limit: maybe_single() ──────────

def test_get_calibration_reference_returns_none_instead_of_raising():
    """Zero matching rows must return None, not raise - this is what the
    .single() bug broke."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .maybe_single.return_value.execute.return_value = MagicMock(data=None)
        result = database.get_calibration_reference(SESSION_ID)
    assert result is None


def test_get_calibration_reference_handles_maybe_single_returning_none_directly():
    """Real bug, confirmed in production (Adi's traceback): postgrest-py's
    maybe_single().execute() returns None directly - the whole response,
    not just response.data=None - whenever zero rows match. A caller
    that does response.data unconditionally crashes with
    AttributeError: 'NoneType' object has no attribute 'data'."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .maybe_single.return_value.execute.return_value = None
        result = database.get_calibration_reference(SESSION_ID)
    assert result is None


def test_get_acceptance_limit_returns_none_instead_of_raising():
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        result = database.get_acceptance_limit("Weighing", "accuracy")
    assert result is None


def test_get_profile_handles_maybe_single_returning_none_directly():
    """Same real bug as above, in get_profile - hit on EVERY authenticated
    request via auth.get_current_user_id, since most accounts predating
    the profiles table have no row yet."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .maybe_single.return_value.execute.return_value = None
        result = database.get_profile("some-user-id")
    assert result is None


def test_get_pending_role_change_request_handles_maybe_single_returning_none_directly():
    """The exact function and exact crash reported in production:
    AttributeError: 'NoneType' object has no attribute 'data', thrown
    from POST /api/role-requests for any user with no existing pending
    request - i.e. the normal, common case."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.maybe_single.return_value.execute.return_value = None
        result = database.get_pending_role_change_request_for_user("some-user-id")
    assert result is None


def test_calibration_reference_by_session_endpoint_returns_clean_404_not_crash():
    """End-to-end through the actual endpoint: a session with no
    calibration reference yet must come back as a normal 404, not an
    unhandled exception that would show up client-side as a bogus CORS
    error."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value \
            .maybe_single.return_value.execute.return_value = MagicMock(data=None)
        resp = client.get(f"/api/calibration-reference-by-session/{SESSION_ID}")
    assert resp.status_code == 404
    assert "No calibration reference found" in resp.json()["detail"]


# ── _format_date: ISO 8601 "Z" suffix ─────────────────────────────────────────

def test_format_date_handles_trailing_z_suffix():
    assert _format_date("2026-06-15T10:30:00Z") == "15 Jun 2026"


def test_format_date_still_handles_offset_without_z():
    assert _format_date("2026-06-15T10:30:00+04:00") == "15 Jun 2026"


def test_format_date_still_handles_none():
    assert _format_date(None) == "\u2014"


def test_format_date_still_falls_back_on_genuinely_unparseable_string():
    assert _format_date("not-a-date") == "not-a-date"


# ── reporting._resolve_approver ───────────────────────────────────────────

def test_resolve_approver_returns_none_for_a_clean_never_flagged_session():
    from modules.reporting import _resolve_approver
    session = {"review_status": "clean", "reviewed_by": None}
    assert _resolve_approver(session) == (None, None)


def test_resolve_approver_returns_none_while_still_pending_review():
    """Even if reviewed_by somehow got set early, only an actual
    'approved' status should populate the certificate - a pending or
    rejected session must not show an Approved By name."""
    from modules.reporting import _resolve_approver
    session = {"review_status": "pending_review", "reviewed_by": "reviewer-1"}
    assert _resolve_approver(session) == (None, None)


def test_resolve_approver_returns_none_when_rejected():
    from modules.reporting import _resolve_approver
    session = {"review_status": "rejected", "reviewed_by": "reviewer-1"}
    assert _resolve_approver(session) == (None, None)


def test_resolve_approver_returns_name_and_title_when_approved():
    from modules.reporting import _resolve_approver
    session = {"review_status": "approved", "reviewed_by": "reviewer-1"}
    with patch("modules.reporting.get_profile", return_value={"full_name": "S. Charkha", "title": "TM"}):
        result = _resolve_approver(session)
    assert result == ("S. Charkha", "TM")


def test_resolve_approver_handles_missing_reviewer_profile_gracefully():
    from modules.reporting import _resolve_approver
    session = {"review_status": "approved", "reviewed_by": "reviewer-1"}
    with patch("modules.reporting.get_profile", return_value=None):
        result = _resolve_approver(session)
    assert result == (None, None)