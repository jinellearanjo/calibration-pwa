"""tests/test_auth_require_tier.py

Unit tests for auth.py's TITLE_PERMISSION_TIER mapping and require_tier
dependency - the foundation the whole roles feature is built on.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

import pytest
from unittest.mock import patch
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

import auth
import database

# A tiny standalone app, not main.app - keeps this test isolated from
# main.py's dependency_overrides used by every other test file (which,
# per the lesson baked into test_master_instruments_shared.py, is a
# single dict shared across the whole pytest session's imports).
_test_app = FastAPI()


@_test_app.get("/full-edit-only")
def _full_edit_route(user_id: str = Depends(auth.require_tier("full_edit"))):
    return {"ok": True, "user_id": user_id}


@_test_app.get("/edit-or-create")
def _edit_or_create_route(user_id: str = Depends(auth.require_tier("full_edit", "cert_creation"))):
    return {"ok": True}


_client = TestClient(_test_app)


@pytest.mark.parametrize("title,tier", [
    ("QM", "full_edit"), ("TM", "full_edit"), ("MR", "full_edit"), ("MD", "full_edit"),
    ("Cal Tech", "cert_creation"), ("Engineer", "cert_creation"),
    ("Admin", "cert_creation"), ("Lab Staff", "cert_creation"),
    ("Viewer", "read_only"),
])
def test_title_permission_tier_mapping_is_exactly_as_specified(title, tier):
    assert auth.TITLE_PERMISSION_TIER[title] == tier


def test_require_tier_allows_matching_tier():
    _test_app.dependency_overrides[auth.get_current_user_id] = lambda: "user-1"
    _test_app.dependency_overrides[auth.get_current_user_title] = lambda: "QM"
    try:
        resp = _client.get("/full-edit-only")
    finally:
        _test_app.dependency_overrides.clear()
    assert resp.status_code == 200


def test_require_tier_rejects_non_matching_tier_with_403():
    _test_app.dependency_overrides[auth.get_current_user_id] = lambda: "user-1"
    _test_app.dependency_overrides[auth.get_current_user_title] = lambda: "Viewer"
    try:
        resp = _client.get("/full-edit-only")
    finally:
        _test_app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_require_tier_accepts_any_of_multiple_allowed_tiers():
    _test_app.dependency_overrides[auth.get_current_user_id] = lambda: "user-1"
    _test_app.dependency_overrides[auth.get_current_user_title] = lambda: "Cal Tech"
    try:
        resp = _client.get("/edit-or-create")
    finally:
        _test_app.dependency_overrides.clear()
    assert resp.status_code == 200

    _test_app.dependency_overrides[auth.get_current_user_id] = lambda: "user-1"
    _test_app.dependency_overrides[auth.get_current_user_title] = lambda: "Viewer"
    try:
        resp = _client.get("/edit-or-create")
    finally:
        _test_app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_get_current_user_title_defaults_to_viewer_when_no_profile_exists():
    with patch.object(database, "get_profile", return_value=None):
        title = auth.get_current_user_title(user_id="some-user-with-no-profile-row")
    assert title == "Viewer"


def test_get_current_user_title_reads_the_real_profile_when_present():
    with patch.object(database, "get_profile", return_value={"id": "u1", "title": "TM"}):
        title = auth.get_current_user_title(user_id="u1")
    assert title == "TM"


# ── Account deactivation ───────────────────────────────────────────────────

def test_get_current_user_id_rejects_deactivated_account():
    """The core of the deactivation feature - a deactivated user must be
    rejected by the universal auth dependency, not just tier-gated
    endpoints, otherwise deactivation wouldn't actually revoke access."""
    with patch.object(database, "get_profile", return_value={"id": "u1", "title": "Cal Tech", "is_active": False}):
        with pytest.raises(Exception) as exc_info:
            auth.get_current_user_id(payload={"sub": "u1"})
    assert "403" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 403


def test_get_current_user_id_allows_active_account():
    with patch.object(database, "get_profile", return_value={"id": "u1", "title": "Cal Tech", "is_active": True}):
        result = auth.get_current_user_id(payload={"sub": "u1"})
    assert result == "u1"


def test_get_current_user_id_allows_account_with_no_profile_row_yet():
    """A missing profile (e.g. pre-migration account) must not be treated
    as deactivated - only an explicit is_active=False should reject."""
    with patch.object(database, "get_profile", return_value=None):
        result = auth.get_current_user_id(payload={"sub": "u1"})
    assert result == "u1"