"""tests/test_weighing_session_id_optional.py

Regression tests for a bug where WeighingOffCenterReadingCreate and
WeighingHysteresisReadingCreate declared `session_id: UUID` as a required
field on the per-reading body model.

The frontend never sends session_id per-reading - it's already in the URL
path (POST /api/sessions/{session_id}/weighing/off-center, .../hysteresis)
and main.py correctly injects it into each row itself, after validation,
right before insert. Because the field was required with no default,
FastAPI rejected every real submission with a 422 (5x "Field required")
before the endpoint body ever ran. The fix makes session_id
`Optional[UUID] = None` on both models, matching the established
convention already used by WeighingRepeatabilityReadingCreate.test_id.

These tests submit the payload shape actually sent by
WeighingReadingsForm.jsx - no session_id on any reading - and assert the
request succeeds, which is the exact case the old required field broke.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import auth

app = main.app
app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
client = TestClient(app)

SESSION_ID = "33333333-3333-3333-3333-333333333333"


def _mock_session_and_instrument():
    return (
        {"id": SESSION_ID, "instrument_id": "instr-1"},
        {"id": "instr-1", "type": "Weighing"},
    )


def _five_off_center_no_session_id():
    """Exactly the shape submitOffCenter() in WeighingReadingsForm.jsx sends -
    no session_id key anywhere, since it's only known via the URL path."""
    return [
        {"position": p, "nominal_load": 1550.0, "unit": "g",
         "reading_before": 0.0, "reading_with_load": 1550.05, "reading_after": 0.01}
        for p in ["center", "front", "back", "left", "right"]
    ]


def _five_hysteresis_no_session_id():
    """Exactly the shape submitHysteresis() sends - no session_id key."""
    return [
        {"sequence_order": i, "phase": f"p{i}", "reading_value": 1.0, "unit": "kg"}
        for i in range(1, 6)
    ]


def test_off_center_succeeds_without_session_id_in_payload():
    session, instrument = _mock_session_and_instrument()
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_weighing_off_center_readings"), \
         patch.object(main.database, "insert_weighing_off_center_readings", return_value=[]) as mock_insert:
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/off-center",
            json=_five_off_center_no_session_id(),
        )
    assert resp.status_code == 200
    # Confirm the backend still injected the real session_id server-side,
    # into every row, before calling the insert.
    inserted_rows = mock_insert.call_args[0][0]
    assert len(inserted_rows) == 5
    assert all(row["session_id"] == SESSION_ID for row in inserted_rows)


def test_hysteresis_succeeds_without_session_id_in_payload():
    session, instrument = _mock_session_and_instrument()
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument), \
         patch.object(main.database, "delete_weighing_hysteresis_readings"), \
         patch.object(main.database, "insert_weighing_hysteresis_readings", return_value=[]) as mock_insert:
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/hysteresis",
            json=_five_hysteresis_no_session_id(),
        )
    assert resp.status_code == 200
    inserted_rows = mock_insert.call_args[0][0]
    assert len(inserted_rows) == 5
    assert all(row["session_id"] == SESSION_ID for row in inserted_rows)


def test_off_center_still_rejects_bad_position_value():
    """Sanity check the fix didn't loosen validation on other required
    fields - a genuinely malformed payload should still 422."""
    session, instrument = _mock_session_and_instrument()
    with patch.object(main.database, "get_session", return_value=session), \
         patch.object(main.database, "get_instrument", return_value=instrument):
        payload = _five_off_center_no_session_id()
        del payload[0]["nominal_load"]  # remove a genuinely required field
        resp = client.post(
            f"/api/sessions/{SESSION_ID}/weighing/off-center",
            json=payload,
        )
    assert resp.status_code == 422