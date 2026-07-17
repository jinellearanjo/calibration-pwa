"""tests/test_duplicate_row_fix.py

Regression tests for the "Known, Not Yet Fixed" resubmission-duplicates
bug flagged for Weighing/Temperature/Electrical: create_weighing_
repeatability_test and its siblings (off-center, hysteresis),
create_temperature_repeatability_test, and create_electrical_test all did
a blind insert with no existing-record check, so resubmitting the same
test point / setpoint / function-type+range stacked a second full
test+readings set on top of the first every time, rather than replacing
it (the same root cause already fixed for Pressure's ReadingsForm.jsx).

Two different shapes of fix, matching the two different data shapes:

1. Weighing off-center and hysteresis are always submitted as one
   complete, atomic set tied only to session_id (no sub-key, always
   exactly 5 rows) - full delete-before-insert, same shape as Pressure's
   delete_readings.

2. Weighing repeatability, Temperature repeatability, and Electrical
   tests each key off a sub-field within the session (test_point /
   setpoint_label / function_type+range_label) - a session can have
   MULTIPLE of these, so a full per-session wipe would silently destroy
   sibling test points/setpoints/ranges still on record. These use
   surgical delete-by-matching-key instead: only the row(s) sharing the
   same key are cleared, and their child readings are deleted first
   (keyed by test_id, since there's no confirmed DB-level cascade -
   see delete_calibration_session_cascade's docstring for why).

These tests exercise database.py's new delete_* functions directly
against a mocked Supabase client, asserting the delete call is scoped by
the correct key column(s) - not just session_id - which is the actual
thing that distinguishes "safe surgical replace" from "wipes out other
test points too."
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

import database
import main
import auth

app = main.app
app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
client = TestClient(app)

SESSION_ID = "55555555-5555-5555-5555-555555555555"


# ── database.py: delete-by-key functions scope correctly ─────────────────────

def test_delete_weighing_repeatability_test_by_key_scopes_to_test_point_not_whole_session():
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": "old-test-id"}])
        database.delete_weighing_repeatability_test_by_key(SESSION_ID, "near_zero")

    # The SELECT that finds existing rows to clear must filter by BOTH
    # session_id and test_point - filtering by session_id alone would
    # match (and then delete) every test_point's row, not just this one.
    select_eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
    assert call("session_id", SESSION_ID) in select_eq_calls
    nested_eq_calls = mock_supabase.table.return_value.select.return_value.eq.return_value.eq.call_args_list
    assert call("test_point", "near_zero") in nested_eq_calls

    # Child readings for the matched test must be deleted by test_id.
    mock_supabase.table.return_value.delete.return_value.eq.assert_any_call("test_id", "old-test-id")

    # The test row's own delete must ALSO carry both filters, not just
    # session_id - this is what stops it from being a full-session wipe.
    delete_eq_calls = mock_supabase.table.return_value.delete.return_value.eq.call_args_list
    assert call("session_id", SESSION_ID) in delete_eq_calls


def test_delete_temperature_repeatability_test_by_key_scopes_to_setpoint_not_whole_session():
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": "old-test-id"}])
        database.delete_temperature_repeatability_test_by_key(SESSION_ID, "110c")

    nested_eq_calls = mock_supabase.table.return_value.select.return_value.eq.return_value.eq.call_args_list
    assert call("setpoint_label", "110c") in nested_eq_calls
    mock_supabase.table.return_value.delete.return_value.eq.assert_any_call("test_id", "old-test-id")


def test_delete_electrical_test_by_key_scopes_to_function_and_range_not_whole_session():
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": "old-test-id"}])
        database.delete_electrical_test_by_key(SESSION_ID, "DCV", "20mV")

    mock_supabase.table.return_value.delete.return_value.eq.assert_any_call("test_id", "old-test-id")


def test_delete_by_key_is_a_no_op_on_readings_when_nothing_matches():
    """No existing row for this key -> no readings delete call keyed by
    test_id (there's no test_id to key off of). The test-row delete
    itself still runs - it's a harmless zero-row no-op - just never a
    readings delete for a test_id that doesn't exist. Confirms a
    genuinely new test_point doesn't trigger any incorrect readings delete."""
    with patch.object(database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[])
        database.delete_weighing_repeatability_test_by_key(SESSION_ID, "fifty_percent")
    for c in mock_supabase.table.return_value.delete.return_value.eq.call_args_list:
        assert c != call("test_id", None)
        assert c[0][0] != "test_id"


# ── main.py endpoints: delete-by-key/delete-before-insert actually wired in ──

def _mock_session_and_instrument(instrument_type):
    return (
        {"id": SESSION_ID, "instrument_id": "instr-1"},
        {"id": "instr-1", "type": instrument_type},
    )


def test_weighing_repeatability_endpoint_clears_matching_test_point_before_insert():
    session, instrument = _mock_session_and_instrument("Weighing")
    readings = [{"reading_number": i, "reading_before": 1.0, "reading_with_load": 1.1, "reading_after": 1.0} for i in range(1, 11)]
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_weighing_repeatability_test_by_key") as mock_delete, \
         patch.object(main.database, "insert_weighing_repeatability_test", return_value=[{"id": "t1"}]), \
         patch.object(main.database, "insert_weighing_repeatability_readings", return_value=[]):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/repeatability",
            json={"payload": {"session_id": SESSION_ID, "test_point": "near_zero", "nominal_load": 1.0,
                              "unit": "kg", "standard_weights_uncertainty": 0.01},
                  "readings": readings},
        )
    assert resp.status_code == 200
    mock_delete.assert_called_once_with(SESSION_ID, "near_zero")


def test_temperature_repeatability_endpoint_clears_matching_setpoint_before_insert():
    session, instrument = _mock_session_and_instrument("Temperature")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_temperature_repeatability_test_by_key") as mock_delete, \
         patch.object(main.database, "insert_temperature_repeatability_test", return_value=[{"id": "t1"}]), \
         patch.object(main.database, "insert_temperature_repeatability_readings", return_value=[]):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/temperature/repeatability",
            json={"payload": {
                      "session_id": SESSION_ID,
                      "setpoint_label": "110c", "nominal_temperature": 110, "unit": "C",
                      "standard_uncertainty": 0.17, "standard_accuracy": 0,
                      "drift_standard_uncertainty": 0.004, "hysteresis_value": 0.01,
                      "bath_stability_value": 0.5, "bath_uniformity_value": 0.8,
                  },
                  "readings": [{"reading_number": i, "reading_value": 110.0} for i in range(1, 4)]},
        )
    assert resp.status_code == 200
    mock_delete.assert_called_once_with(SESSION_ID, "110c")


def test_electrical_test_endpoint_clears_matching_function_and_range_before_insert():
    session, instrument = _mock_session_and_instrument("Electrical")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_electrical_test_by_key") as mock_delete, \
         patch.object(main.database, "insert_electrical_test", return_value=[{"id": "t1"}]), \
         patch.object(main.database, "insert_electrical_readings", return_value=[]):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/electrical/tests",
            json={"payload": {"session_id": SESSION_ID, "function_type": "DCV", "range_label": "20mV",
                              "nominal_value": 20, "unit": "mV"},
                  "readings": [{"reading_number": 1, "reading_value": 20.1}]},
        )
    assert resp.status_code == 200
    mock_delete.assert_called_once_with(SESSION_ID, "DCV", "20mV")


def test_weighing_off_center_endpoint_clears_session_before_insert():
    session, instrument = _mock_session_and_instrument("Weighing")
    readings = [{"position": p, "nominal_load": 1.0, "unit": "kg", "reading_before": 1.0,
                 "reading_with_load": 1.1, "reading_after": 1.0}
                for p in ["center", "front", "back", "left", "right"]]
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_weighing_off_center_readings") as mock_delete, \
         patch.object(main.database, "insert_weighing_off_center_readings", return_value=[]):
        resp = client.post(f"/api/sessions/{SESSION_ID}/weighing/off-center", json=readings)
    assert resp.status_code == 200
    mock_delete.assert_called_once_with(SESSION_ID)


def test_weighing_hysteresis_endpoint_clears_session_before_insert():
    session, instrument = _mock_session_and_instrument("Weighing")
    readings = [{"sequence_order": i, "phase": f"p{i}", "reading_value": 1.0, "unit": "kg"} for i in range(1, 6)]
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_weighing_hysteresis_readings") as mock_delete, \
         patch.object(main.database, "insert_weighing_hysteresis_readings", return_value=[]):
        resp = client.post(f"/api/sessions/{SESSION_ID}/weighing/hysteresis", json=readings)
    assert resp.status_code == 200
    mock_delete.assert_called_once_with(SESSION_ID)
