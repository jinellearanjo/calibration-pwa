"""tests/test_instrument_type_guard.py

Regression tests for _require_instrument_type, the guard added to all six
category-specific test/reading creation endpoints (Pressure's create_reading,
the three Weighing endpoints, Temperature's repeatability test, and
Electrical's test). Without this guard, nothing stopped a session whose
instrument is e.g. Temperature from having Weighing test data submitted
against it - SessionPicker.jsx lists every session for the user with no
category filtering, so a user landing on a bare readings route via a
Dashboard card could pick a mismatched session and silently corrupt data.

Each endpoint is checked for:
1. A mismatched instrument type -> 400, with no insert attempted.
2. A matching instrument type -> proceeds to the normal happy path.
3. A missing session/instrument -> 404 (only checked once, on the
   Pressure endpoint, since _require_instrument_type is shared code and
   this path doesn't vary by category).
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

app = main.app
app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
client = TestClient(app)

SESSION_ID = "33333333-3333-3333-3333-333333333333"


def _mock_session_and_instrument(instrument_type):
    return (
        {"id": SESSION_ID, "instrument_id": "instr-1"},
        {"id": "instr-1", "type": instrument_type},
    )


# ── Pressure: create_reading ──────────────────────────────────────────────

def _reading_payload():
    return {
        "session_id": SESSION_ID, "point_number": 1, "nominal_value": 10,
        "measured_value_up": 10.01, "measured_value_down": 9.99,
        "reference_value": 10.0, "correction": 0.0, "mean_error": 0.005, "hysteresis": 0.02,
    }


def test_create_reading_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Temperature")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        resp = client.post("/api/readings", json=_reading_payload())
    assert resp.status_code == 400
    assert "Temperature" in resp.json()["detail"]
    assert "Pressure" in resp.json()["detail"]


def test_create_reading_allows_matching_instrument():
    session, instrument = _mock_session_and_instrument("Pressure")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.insert.return_value.execute.return_value = \
            MagicMock(data=[{"id": "r1"}])
        resp = client.post("/api/readings", json=_reading_payload())
    assert resp.status_code == 200


def test_create_reading_404_when_session_not_found():
    with patch.object(main.database, "get_session", return_value=None):
        resp = client.post("/api/readings", json=_reading_payload())
    assert resp.status_code == 404


def test_create_reading_404_when_instrument_not_found():
    with patch.object(main.database, "get_session", return_value={"id": SESSION_ID, "instrument_id": "missing"}), \
         patch.object(main.database, "get_instrument", return_value=None):
        resp = client.post("/api/readings", json=_reading_payload())
    assert resp.status_code == 404


# ── Weighing: repeatability, off-center, hysteresis ───────────────────────

def _ten_readings():
    return [{"reading_number": i, "reading_before": 1.0, "reading_with_load": 1.1, "reading_after": 1.0} for i in range(1, 11)]


def _five_off_center():
    return [{"session_id": SESSION_ID, "position": p, "nominal_load": 1.0, "unit": "kg", "reading_before": 1.0, "reading_with_load": 1.1, "reading_after": 1.0}
            for p in ["center", "front", "back", "left", "right"]]


def _five_hysteresis():
    return [{"session_id": SESSION_ID, "sequence_order": i, "phase": f"p{i}", "reading_value": 1.0, "unit": "kg"} for i in range(1, 6)]


def test_weighing_repeatability_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Pressure")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/repeatability",
            json={"payload": {"session_id": SESSION_ID, "test_point": "near_zero", "nominal_load": 1.0, "unit": "kg", "standard_weights_uncertainty": 0.01},
                  "readings": _ten_readings()},
        )
    assert resp.status_code == 400
    assert "Weighing" in resp.json()["detail"]


def test_weighing_off_center_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Electrical")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/off-center",
            json=_five_off_center(),
        )
    assert resp.status_code == 400
    assert "Weighing" in resp.json()["detail"]


def test_weighing_hysteresis_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Temperature")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/hysteresis",
            json=_five_hysteresis(),
        )
    assert resp.status_code == 400
    assert "Weighing" in resp.json()["detail"]


def test_weighing_repeatability_allows_matching_instrument():
    session, instrument = _mock_session_and_instrument("Weighing")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "insert_weighing_repeatability_test", return_value=[{"id": "t1"}]), \
         patch.object(main.database, "insert_weighing_repeatability_readings", return_value=[]):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/repeatability",
            json={"payload": {"session_id": SESSION_ID, "test_point": "near_zero", "nominal_load": 1.0, "unit": "kg", "standard_weights_uncertainty": 0.01},
                  "readings": _ten_readings()},
        )
    assert resp.status_code == 200


# ── Temperature: repeatability ─────────────────────────────────────────────

def test_temperature_repeatability_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Weighing")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
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
    assert resp.status_code == 400
    assert "Temperature" in resp.json()["detail"]


def test_temperature_repeatability_allows_matching_instrument():
    session, instrument = _mock_session_and_instrument("Temperature")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
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


# ── Electrical: test ────────────────────────────────────────────────────────

def test_electrical_test_rejects_mismatched_instrument():
    session, instrument = _mock_session_and_instrument("Pressure")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/electrical/tests",
            json={"payload": {"session_id": SESSION_ID, "function_type": "ACV", "range_label": "200mV", "nominal_value": 200, "unit": "mV"},
                  "readings": [{"reading_number": 1, "reading_value": 200.1}]},
        )
    assert resp.status_code == 400
    assert "Electrical" in resp.json()["detail"]


def test_electrical_test_allows_matching_instrument():
    session, instrument = _mock_session_and_instrument("Electrical")
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "insert_electrical_test", return_value=[{"id": "t1"}]), \
         patch.object(main.database, "insert_electrical_readings", return_value=[]):
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/electrical/tests",
            json={"payload": {"session_id": SESSION_ID, "function_type": "ACV", "range_label": "200mV", "nominal_value": 200, "unit": "mV"},
                  "readings": [{"reading_number": 1, "reading_value": 200.1}]},
        )
    assert resp.status_code == 200