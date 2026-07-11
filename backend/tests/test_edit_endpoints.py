"""tests/test_edit_endpoints.py

Regression tests for the edit-mode endpoints added to support
InstrumentForm.jsx/SessionForm.jsx's edit mode and EditSession.jsx:
PUT /api/instruments/{id}, PUT /api/sessions/{id},
PUT /api/calibration-reference/{session_id}, and
GET /api/calibration-reference-by-session/{session_id}.

Each endpoint is checked for both its happy path and its 404 (record not
found) path - conftest.py's dummy env vars mean this runs with zero
manual setup, same as the rest of this suite.
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

INSTRUMENT_ID = "11111111-1111-1111-1111-111111111111"
SESSION_ID = "22222222-2222-2222-2222-222222222222"

instrument_payload = {
    "name": "Test Gauge", "type": "Pressure", "make": "Acme", "model": "X1",
    "serial_number": "SN1", "range_min": 0, "range_max": 100, "unit": "bar",
    "resolution": 0.1, "accuracy_class": "1.0",
}

session_payload = {
    "instrument_id": INSTRUMENT_ID, "date": "2026-07-11", "technician": "Jinelle",
    "temperature_c": 22.5, "humidity_pct": 45.0,
}

cal_ref_payload = {
    "session_id": SESSION_ID, "certificate_number": "CERT-1",
    "date_of_calibration": "2026-07-11", "cal_due_date": "2027-07-11",
    "item_received_date": "2026-07-10", "date_of_issue": "2026-07-11",
    "customer_name": "Acme Corp", "customer_address": "Dubai",
}


def test_update_instrument_success():
    with patch.object(main.database, "get_instrument", return_value={"id": INSTRUMENT_ID}), \
         patch.object(main.database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[{"id": INSTRUMENT_ID, **instrument_payload}])
        resp = client.put(f"/api/instruments/{INSTRUMENT_ID}", json=instrument_payload)
    print("update_instrument:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["id"] == INSTRUMENT_ID


def test_update_instrument_404_when_not_found():
    with patch.object(main.database, "get_instrument", return_value=None):
        resp = client.put(f"/api/instruments/{INSTRUMENT_ID}", json=instrument_payload)
    print("update_instrument 404:", resp.status_code, resp.json())
    assert resp.status_code == 404


def test_update_session_success():
    with patch.object(main.database, "get_session", return_value={"id": SESSION_ID}), \
         patch.object(main.database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[{"id": SESSION_ID, **session_payload}])
        resp = client.put(f"/api/sessions/{SESSION_ID}", json=session_payload)
    print("update_session:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["id"] == SESSION_ID


def test_update_session_404_when_not_found():
    with patch.object(main.database, "get_session", return_value=None):
        resp = client.put(f"/api/sessions/{SESSION_ID}", json=session_payload)
    assert resp.status_code == 404


def test_update_calibration_reference_success():
    with patch.object(main.database, "get_calibration_reference", return_value={"session_id": SESSION_ID}), \
         patch.object(main.database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[{"session_id": SESSION_ID, **cal_ref_payload}])
        resp = client.put(f"/api/calibration-reference/{SESSION_ID}", json=cal_ref_payload)
    print("update_calibration_reference:", resp.status_code, resp.json())
    assert resp.status_code == 200


def test_update_calibration_reference_404_when_not_found():
    with patch.object(main.database, "get_calibration_reference", return_value=None):
        resp = client.put(f"/api/calibration-reference/{SESSION_ID}", json=cal_ref_payload)
    assert resp.status_code == 404


def test_get_calibration_reference_by_session_success():
    with patch.object(main.database, "get_calibration_reference", return_value=cal_ref_payload):
        resp = client.get(f"/api/calibration-reference-by-session/{SESSION_ID}")
    print("get_by_session:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["certificate_number"] == "CERT-1"


def test_get_calibration_reference_by_session_404_when_none_exists():
    # Non-fatal on the frontend - the form just stays empty for Section 1.
    with patch.object(main.database, "get_calibration_reference", return_value=None):
        resp = client.get(f"/api/calibration-reference-by-session/{SESSION_ID}")
    assert resp.status_code == 404