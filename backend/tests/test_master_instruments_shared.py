"""tests/test_master_instruments_shared.py

Regression test for list_master_instruments: master instruments are
shared physical lab assets, not personal to whoever registered them, so
GET /api/master-instruments must NOT filter by the requesting user's
user_id - two technicians logged in as different users both need to see
the same physical Dead Weight Tester, Fluke 5560A, etc.

This locks in the fix that removed the previous .eq("user_id", user_id)
filter, which incorrectly hid one user's registered masters from every
other user.
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
app.dependency_overrides[auth.get_current_user_id] = lambda: "user-a"
client = TestClient(app)


def test_list_master_instruments_returns_all_users_masters_not_just_own():
    # Two master instruments created by two DIFFERENT users - both must
    # come back for a request authenticated as a third user entirely.
    all_masters = [
        {"id": "m1", "name": "Dead Weight Tester", "user_id": "user-a"},
        {"id": "m2", "name": "Fluke 5560A", "user_id": "user-b"},
    ]
    with patch.object(main.database, "supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = \
            MagicMock(data=all_masters)
        resp = client.get("/api/master-instruments")

    assert resp.status_code == 200
    returned_ids = {m["id"] for m in resp.json()}
    assert returned_ids == {"m1", "m2"}

    # Confirm the query itself never calls .eq(...) - i.e. no user_id
    # filter was applied anywhere in the chain.
    select_mock = mock_supabase.table.return_value.select.return_value
    select_mock.eq.assert_not_called()


def test_create_master_instrument_still_records_creator_for_audit():
    # user_id must still be stamped on creation (audit trail), even
    # though it no longer gates visibility for GET.
    # This endpoint is now gated to full_edit/cert_creation tiers (not
    # Viewer) - mock a profile with an edit-tier title so the request
    # gets past require_tier.
    payload = {
        "name": "Dead Weight Tester", "instrument_type": "Pressure",
        "make": "Budenberg", "model": "DHB540 DX", "serial_number": "SN1",
        "asset_number": "A1", "traceability_chain": "DCL",
        "uncertainty_u": 0.01, "accuracy": 0.02, "resolution": 0.001,
        "claimed_cmc": 0.05, "cal_due_date": "2027-01-01",
    }
    with patch.object(main.database, "supabase") as mock_supabase, \
         patch.object(main.database, "get_profile", return_value={"id": "user-a", "title": "Cal Tech"}):
        mock_supabase.table.return_value.insert.return_value.execute.return_value = \
            MagicMock(data=[{"id": "m1", **payload, "user_id": "user-a"}])
        resp = client.post("/api/master-instruments", json=payload)

    assert resp.status_code == 200
    inserted_data = mock_supabase.table.return_value.insert.call_args[0][0]
    # Assert against whatever get_current_user_id currently resolves to,
    # not a hardcoded literal. app.dependency_overrides is a single dict
    # shared by every test module across the whole suite (all bound to
    # the same main.app instance), and pytest imports every test file
    # during collection before any test executes - so whichever file is
    # collected last "wins" the override for everyone. Hardcoding a
    # literal here only ever worked by alphabetical luck.
    expected_user_id = app.dependency_overrides[auth.get_current_user_id]()
    assert inserted_data["user_id"] == expected_user_id


def test_create_master_instrument_rejects_viewer():
    """The actual governance fix this phase added: a Viewer must not be
    able to add master instruments, end-to-end through the real
    endpoint - not just checked in isolation against require_tier."""
    payload = {
        "name": "Dead Weight Tester", "instrument_type": "Pressure",
        "make": "Budenberg", "model": "DHB540 DX", "serial_number": "SN1",
        "asset_number": "A1", "traceability_chain": "DCL",
        "uncertainty_u": 0.01, "accuracy": 0.02, "resolution": 0.001,
        "claimed_cmc": 0.05, "cal_due_date": "2027-01-01",
    }
    with patch.object(main.database, "get_profile", return_value={"id": "user-a", "title": "Viewer"}):
        resp = client.post("/api/master-instruments", json=payload)
    assert resp.status_code == 403


def test_delete_master_instrument_rejects_viewer():
    with patch.object(main.database, "get_profile", return_value={"id": "user-a", "title": "Viewer"}):
        resp = client.delete("/api/master-instruments/m1")
    assert resp.status_code == 403