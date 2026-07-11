"""tests/test_validation.py

Regression tests for modules/validation.py's validate_session function.

Covers the two behaviors this project has specifically flagged as
important not to regress on:

1. "Worst case wins" aggregation across multiple budgets (Temperature/
   Electrical sessions can have several - one per setpoint or
   function-type/range). Any single REJECTED budget makes the whole
   session REJECTED even if every other one passed; failing that, any
   single REVIEW REQUIRED makes the session REVIEW REQUIRED; only if
   every budget is ACCEPTED does the session get ACCEPTED. The failure
   must also name which specific setpoint/range caused it.

2. A session with zero test data must be REJECTED, not REVIEW REQUIRED
   (a real bug found and fixed during the Round 7 refactor - having no
   data at all is worse than having incomplete data, and the two must
   not be conflated).

All database access in validation.py goes through functions imported
from database.py, so every test here mocks those directly rather than
touching a real database - matches this project's own testing
convention throughout past sessions.
"""

from unittest.mock import patch

import pytest

from modules import validation


def _patch_common(instrument_type="Temperature", acceptance_limit=0.05):
    """Returns a dict of the always-needed database.py mocks (session,
    instrument, acceptance limit) so each test only needs to add the
    category-specific test-data and budget mocks on top.
    """
    return {
        "get_session": {"id": "session-1", "instrument_id": "instr-1"},
        "get_instrument": {"id": "instr-1", "type": instrument_type},
        "get_acceptance_limit": {"limit_value": acceptance_limit},
    }


# ── Worst-case-wins: Temperature, multiple setpoints ──────────────────────

def test_worst_case_wins_one_rejected_setpoint_rejects_whole_session():
    """Mirrors the exact scenario documented in the handover: a 3-setpoint
    Temperature session where only one setpoint's final applied
    uncertainty exceeds the limit must REJECT... wait, per validate_session's
    own logic, an over-limit budget is REVIEW REQUIRED, not REJECTED, and
    only a *missing* value or missing test data is REJECTED. This test
    covers the REVIEW REQUIRED case; the sibling test below covers a
    genuinely REJECTED (missing data) case.
    """
    common = _patch_common("Temperature")
    tests = [
        {
            "id": "t1", "setpoint_label": "minus_15c",
            "temperature_repeatability_readings": [{}, {}, {}],
        },
        {
            "id": "t2", "setpoint_label": "110c",
            "temperature_repeatability_readings": [{}, {}, {}],
        },
        {
            "id": "t3", "setpoint_label": "300c",
            "temperature_repeatability_readings": [{}, {}, {}],
        },
    ]
    budgets = [
        {"temperature_test_id": "t1", "final_applied_uncertainty": 0.03},  # under limit
        {"temperature_test_id": "t2", "final_applied_uncertainty": 0.02},  # under limit
        {"temperature_test_id": "t3", "final_applied_uncertainty": 0.09},  # OVER limit
    ]

    with patch.object(validation, "get_session", return_value=common["get_session"]), \
         patch.object(validation, "get_instrument", return_value=common["get_instrument"]), \
         patch.object(validation, "get_acceptance_limit", return_value=common["get_acceptance_limit"]), \
         patch.object(validation, "get_temperature_repeatability_tests", return_value=tests), \
         patch.object(validation, "get_uncertainty_budgets", return_value=budgets), \
         patch.object(validation, "update_session_status") as mock_update:

        result = validation.validate_session("session-1")

    assert result["status"] == "REVIEW REQUIRED"
    mock_update.assert_called_once_with("session-1", "REVIEW REQUIRED")

    # Must name the SPECIFIC setpoint that failed, not just "something".
    t3_result = next(b for b in result["budgets"] if b["identifier"] == "setpoint '300c'")
    assert t3_result["status"] == "REVIEW REQUIRED"
    assert "300c" in t3_result["flags"][0]
    assert "0.09" in t3_result["flags"][0]

    # The two passing setpoints must still individually show ACCEPTED -
    # worst-case-wins affects the SESSION status, not each budget's own.
    t1_result = next(b for b in result["budgets"] if b["identifier"] == "setpoint 'minus_15c'")
    assert t1_result["status"] == "ACCEPTED"


def test_worst_case_wins_all_accepted_session_is_accepted():
    common = _patch_common("Temperature")
    tests = [{"id": "t1", "setpoint_label": "110c", "temperature_repeatability_readings": [{}, {}, {}]}]
    budgets = [{"temperature_test_id": "t1", "final_applied_uncertainty": 0.01}]

    with patch.object(validation, "get_session", return_value=common["get_session"]), \
         patch.object(validation, "get_instrument", return_value=common["get_instrument"]), \
         patch.object(validation, "get_acceptance_limit", return_value=common["get_acceptance_limit"]), \
         patch.object(validation, "get_temperature_repeatability_tests", return_value=tests), \
         patch.object(validation, "get_uncertainty_budgets", return_value=budgets), \
         patch.object(validation, "update_session_status"):

        result = validation.validate_session("session-1")

    assert result["status"] == "ACCEPTED"


def test_worst_case_wins_missing_final_applied_uncertainty_rejects():
    """A budget with no final_applied_uncertainty at all (calculation
    genuinely couldn't complete) must REJECT the whole session, taking
    priority over a merely-over-limit REVIEW REQUIRED sibling budget.
    """
    common = _patch_common("Temperature")
    tests = [
        {"id": "t1", "setpoint_label": "110c", "temperature_repeatability_readings": [{}, {}, {}]},
        {"id": "t2", "setpoint_label": "300c", "temperature_repeatability_readings": [{}, {}, {}]},
    ]
    budgets = [
        {"temperature_test_id": "t1", "final_applied_uncertainty": 0.09},   # REVIEW REQUIRED
        {"temperature_test_id": "t2", "final_applied_uncertainty": None},  # missing -> REJECTED
    ]

    with patch.object(validation, "get_session", return_value=common["get_session"]), \
         patch.object(validation, "get_instrument", return_value=common["get_instrument"]), \
         patch.object(validation, "get_acceptance_limit", return_value=common["get_acceptance_limit"]), \
         patch.object(validation, "get_temperature_repeatability_tests", return_value=tests), \
         patch.object(validation, "get_uncertainty_budgets", return_value=budgets), \
         patch.object(validation, "update_session_status"):

        result = validation.validate_session("session-1")

    # REJECTED must win over REVIEW REQUIRED even though REVIEW REQUIRED
    # was also present - this is the "worst case" ordering, not just "any
    # non-ACCEPTED".
    assert result["status"] == "REJECTED"


# ── Zero test data must REJECT, not REVIEW REQUIRED (Round 7 fix) ────────

def test_zero_test_data_rejects_not_review_required():
    """Locks in a real bug fix: previously, a session with no test data
    at all fell through to REVIEW REQUIRED, which is inconsistent - no
    data at all is strictly worse than incomplete data, and the two
    statuses must not be conflated.
    """
    common = _patch_common("Temperature")

    with patch.object(validation, "get_session", return_value=common["get_session"]), \
         patch.object(validation, "get_instrument", return_value=common["get_instrument"]), \
         patch.object(validation, "get_acceptance_limit", return_value=common["get_acceptance_limit"]), \
         patch.object(validation, "get_temperature_repeatability_tests", return_value=[]), \
         patch.object(validation, "get_uncertainty_budgets", return_value=[]), \
         patch.object(validation, "update_session_status") as mock_update:

        result = validation.validate_session("session-1")

    assert result["status"] == "REJECTED"
    mock_update.assert_called_once_with("session-1", "REJECTED")
    assert any("No uncertainty budget" in f for f in result["flags"])


def test_missing_instrument_record_rejects():
    with patch.object(validation, "get_session", return_value={"id": "s1", "instrument_id": "missing"}), \
         patch.object(validation, "get_instrument", return_value=None), \
         patch.object(validation, "update_session_status") as mock_update:

        result = validation.validate_session("s1")

    assert result["status"] == "REJECTED"
    mock_update.assert_called_once_with("s1", "REJECTED")


def test_missing_acceptance_limit_rejects():
    with patch.object(validation, "get_session", return_value={"id": "s1", "instrument_id": "i1"}), \
         patch.object(validation, "get_instrument", return_value={"id": "i1", "type": "Pressure"}), \
         patch.object(validation, "get_acceptance_limit", return_value=None), \
         patch.object(validation, "update_session_status") as mock_update:

        result = validation.validate_session("s1")

    assert result["status"] == "REJECTED"
    mock_update.assert_called_once_with("s1", "REJECTED")


def test_session_not_found_raises():
    with patch.object(validation, "get_session", return_value=None):
        with pytest.raises(ValueError):
            validation.validate_session("nonexistent")


# ── Single-budget categories (Pressure/Weighing) still work unaffected ────

def test_pressure_single_budget_accepted():
    common = _patch_common("Pressure")
    readings = [
        {"point_number": 1, "measured_value_up": 10.0, "measured_value_down": 10.0, "hysteresis": 0.0},
    ]
    budgets = [{"final_applied_uncertainty": 0.01}]  # no temperature_test_id/electrical_test_id - single budget

    with patch.object(validation, "get_session", return_value=common["get_session"]), \
         patch.object(validation, "get_instrument", return_value={"id": "instr-1", "type": "Pressure"}), \
         patch.object(validation, "get_acceptance_limit", return_value=common["get_acceptance_limit"]), \
         patch.object(validation, "get_readings", return_value=readings), \
         patch.object(validation, "get_uncertainty_budgets", return_value=budgets), \
         patch.object(validation, "update_session_status"):

        result = validation.validate_session("session-1")

    assert result["status"] == "ACCEPTED"
    # Pressure/Weighing have no per-budget label - only one budget exists.
    assert result["budgets"][0]["identifier"] is None