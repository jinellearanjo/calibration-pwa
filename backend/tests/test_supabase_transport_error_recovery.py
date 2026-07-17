"""tests/test_supabase_transport_error_recovery.py

Regression tests for recovering from a stale/terminated Supabase HTTP/2
connection automatically, instead of requiring a manual server restart.

Real-world trigger (seen in production logs): database.supabase caches
one real Supabase client - and its one underlying HTTP/2 connection pool
- for the entire lifetime of the server process (see
_LazySupabaseClient's docstring). If Supabase's end terminates a pooled
connection without httpx noticing (idle timeout, load balancer
recycling, laptop sleep/wake, a brief network drop), every subsequent
request reusing it fails with an httpx.TransportError subclass (observed:
httpx.RemoteProtocolError("ConnectionTerminated")). This is a genuinely
unhandled exception type - not an HTTPException - so it previously
crashed past FastAPI's normal response handling and, as a side effect,
past CORSMiddleware's header injection too, which is why it could look
like a false "CORS blocked" error in the browser rather than what it
actually was.

The fix: a global exception handler for httpx.TransportError that (1)
resets the cached Supabase client so the next request gets a fresh
connection pool, and (2) returns a clean, retryable 503 through FastAPI's
normal response path - so CORS headers ARE attached this time - instead
of crashing.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import database
import main
import auth

app = main.app
app.dependency_overrides[auth.get_current_user_id] = lambda: "test-user-id"
client = TestClient(app)

SESSION_ID = "66666666-6666-6666-6666-666666666666"


def _connection_terminated_error():
    return httpx.RemoteProtocolError("<ConnectionTerminated error_code:1, last_stream_id:13, additional_data:None>")


def test_lazy_client_reset_forces_rebuild_on_next_access():
    """reset() must actually discard the cached client, not just look
    like it does - otherwise the next request would hit the same dead
    connection again."""
    real_database_module = database
    original_client = real_database_module.supabase._client
    try:
        real_database_module.supabase._client = MagicMock(name="stale-client")
        assert real_database_module.supabase._client is not None
        real_database_module.supabase.reset()
        assert real_database_module.supabase._client is None
    finally:
        real_database_module.supabase._client = original_client


def test_transport_error_returns_clean_503_not_a_crash():
    """A raw httpx.TransportError raised deep inside a database call must
    come back as a normal, clean 503 response through the exception
    handler - not an unhandled crash (which is what previously made this
    look like a CORS failure in the browser, since crashed responses
    never reach CORSMiddleware's header-injection step)."""
    with patch.object(main.database, "get_session", side_effect=_connection_terminated_error()):
        resp = client.get(f"/api/sessions/{SESSION_ID}")
    assert resp.status_code == 503
    assert "connection issue" in resp.json()["detail"].lower()


def test_transport_error_resets_the_cached_client():
    """The handler must reset the cached client, so the very next
    request gets a fresh connection pool instead of hitting the same
    terminated connection again."""
    with patch.object(main.database, "get_session", side_effect=_connection_terminated_error()), \
         patch.object(main.database.supabase, "reset") as mock_reset:
        client.get(f"/api/sessions/{SESSION_ID}")
    mock_reset.assert_called_once()


def test_transport_error_recovery_covers_every_endpoint_not_just_one():
    """The handler is registered globally (not per-endpoint), so this
    must recover identically regardless of which endpoint hit the dead
    connection first - matching the real incident, where get_session,
    get_instrument, and get_temperature_repeatability_tests all failed
    together via the same shared client."""
    with patch.object(main.database, "get_instrument", side_effect=_connection_terminated_error()):
        resp = client.get(f"/api/instruments/{SESSION_ID}")
    assert resp.status_code == 503

    with patch.object(main.database, "get_temperature_repeatability_tests", side_effect=_connection_terminated_error()):
        resp = client.get(f"/api/sessions/{SESSION_ID}/temperature/repeatability")
    assert resp.status_code == 503


def test_normal_requests_are_unaffected():
    """Sanity check the handler doesn't interfere with ordinary
    successful responses."""
    with patch.object(main.database, "get_session", return_value={"id": SESSION_ID, "instrument_id": "instr-1"}):
        resp = client.get(f"/api/sessions/{SESSION_ID}")
    assert resp.status_code == 200
