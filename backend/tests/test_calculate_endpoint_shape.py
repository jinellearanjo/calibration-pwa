"""tests/test_calculate_endpoint_shape.py

Regression test for a real bug: the calculate endpoint
(POST /api/sessions/{id}/calculate) was returning a doubly-nested shape -
a list of one-element lists instead of a flat list of budget dicts -
because insert_uncertainty_budget returns response.data (always a list,
even for one row, matching every other insert_* function in database.py),
and this one caller forgot to unwrap it with [0] the way every other
caller does.

The visible symptom: CalculationView.jsx's Summary section has no
null/undefined filter on its fields (unlike Components, which does), so
indexing into the wrong (nested-array) shape rendered the literal string
"undefined" for every summary value, until a subsequent GET (which
returns the correctly flat shape from a plain SELECT) overwrote the
broken state - explaining why it looked "fixed" only after navigating
away and back, or after a page refresh.
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

SESSION_ID = "44444444-4444-4444-4444-444444444444"


def test_calculate_returns_flat_list_of_dicts_not_nested_lists():
    fake_budget_row = {
        "id": "b1", "session_id": SESSION_ID,
        "combined_uncertainty": 0.0527, "k_value": 2,
        "expanded_uncertainty": 0.1055, "cmc": 0.0946,
        "final_applied_uncertainty": 0.1055,
    }

    with patch.object(main.formula_manager, "build_uncertainty_budget", return_value=[{"session_id": SESSION_ID}]), \
         patch.object(main.database, "delete_uncertainty_budgets"), \
         patch.object(main.database, "insert_uncertainty_budget", return_value=[fake_budget_row]) as mock_insert:
        resp = client.post(f"/api/sessions/{SESSION_ID}/calculate")

    assert resp.status_code == 200
    data = resp.json()

    # The critical assertion: data[0] must be the budget dict directly -
    # NOT a one-element list wrapping it. This is exactly what
    # CalculationView.jsx's budget[f.key] lookups need to work at all.
    assert isinstance(data, list)
    assert isinstance(data[0], dict), (
        f"Expected data[0] to be a dict, got {type(data[0])} - "
        f"this is the doubly-nested-list bug if it fails"
    )
    assert data[0]["combined_uncertainty"] == 0.0527
    assert data[0]["final_applied_uncertainty"] == 0.1055

    # Confirm insert_uncertainty_budget was actually called with the
    # budget data (not just that unwrapping happened to work by luck).
    mock_insert.assert_called_once_with({"session_id": SESSION_ID})


def test_calculate_multi_budget_session_all_flat():
    # Temperature/Electrical sessions can return several budgets - every
    # one of them must be correctly unwrapped, not just the first.
    budget_1 = {"id": "b1", "temperature_test_id": "t1", "final_applied_uncertainty": 0.04}
    budget_2 = {"id": "b2", "temperature_test_id": "t2", "final_applied_uncertainty": 0.10}

    with patch.object(main.formula_manager, "build_uncertainty_budget",
                       return_value=[{"temperature_test_id": "t1"}, {"temperature_test_id": "t2"}]), \
         patch.object(main.database, "delete_uncertainty_budgets"), \
         patch.object(main.database, "insert_uncertainty_budget", side_effect=[[budget_1], [budget_2]]):
        resp = client.post(f"/api/sessions/{SESSION_ID}/calculate")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(isinstance(b, dict) for b in data)
    assert data[0]["final_applied_uncertainty"] == 0.04
    assert data[1]["final_applied_uncertainty"] == 0.10
