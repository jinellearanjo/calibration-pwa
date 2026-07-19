"""tests/test_master_instrument_validity.py

Tests for validation.check_master_instrument_validity - the governance
check that feeds the session review workflow (a session gets flagged for
full_edit-tier review when its master instrument fails one of these
checks; see main.py's generate_report endpoint).
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from datetime import date, timedelta
from unittest.mock import patch

from modules import validation

SESSION_ID = "77777777-7777-7777-7777-777777777777"
MASTER_ID = "88888888-8888-8888-8888-888888888888"


def _valid_master(**overrides):
    base = {
        "id": MASTER_ID,
        "name": "Budenberg DWT-2",
        "uncertainty_u": 0.01,
        "accuracy": 0.02,
        "resolution": 0.001,
        "claimed_cmc": 0.05,
        "cal_due_date": (date.today() + timedelta(days=180)).isoformat(),
    }
    base.update(overrides)
    return base


def test_valid_master_returns_no_issues():
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=_valid_master()):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert issues == []


def test_expired_cal_due_date_is_flagged():
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    expired_master = _valid_master(cal_due_date=(date.today() - timedelta(days=30)).isoformat())
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=expired_master):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 1
    assert "Budenberg DWT-2" in issues[0]
    assert "expired" in issues[0].lower()


def test_cal_due_date_today_is_not_flagged():
    """Due today, not yet passed - the boundary should not falsely reject."""
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    master = _valid_master(cal_due_date=date.today().isoformat())
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=master):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert issues == []


def test_missing_uncertainty_is_flagged_as_tba():
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    master = _valid_master(uncertainty_u=None)
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=master):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 1
    assert "uncertainty" in issues[0].lower()
    assert "TBA" in issues[0]


def test_multiple_tba_fields_produce_multiple_distinct_issues():
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    master = _valid_master(accuracy=None, resolution=None)
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=master):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 2


def test_no_master_instrument_selected_is_flagged():
    session = {"id": SESSION_ID, "master_instrument_id": None}
    with patch.object(validation, "get_session", return_value=session):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 1
    assert "no master instrument" in issues[0].lower()


def test_master_instrument_record_not_found_is_flagged():
    session = {"id": SESSION_ID, "master_instrument_id": MASTER_ID}
    with patch.object(validation, "get_session", return_value=session), \
         patch.object(validation, "get_master_instrument", return_value=None):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 1
    assert "could not be found" in issues[0].lower()


def test_session_not_found_is_flagged_not_crashed():
    with patch.object(validation, "get_session", return_value=None):
        issues = validation.check_master_instrument_validity(SESSION_ID)
    assert len(issues) == 1
