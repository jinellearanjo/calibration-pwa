"""tests/test_cors_localhost_ports.py

Regression test for a real bug reported from a teammate's machine: Create
React App silently bumps to port 3001, 3002, etc. whenever the previous
port is already taken (e.g. another dev server still running). The CORS
config's local-dev fallback only ever hardcoded an exact match for
localhost:3000, so a developer's own frontend running on any other port
got a genuine (not masked-crash) CORS rejection on every request -
purely because of which port happened to be free that day, nothing to
do with the actual application code.

Fixed with an `allow_origin_regex` matching any localhost port, in
addition to the existing exact-match allow_origins list (which still
governs real production origins). Safe as a regex specifically because
it's scoped to localhost.
"""

import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def _preflight(origin):
    return client.options(
        "/api/profile",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_localhost_3000_still_works():
    """The original, always-supported port - must not regress."""
    resp = _preflight("http://localhost:3000")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_localhost_non_default_port_now_works():
    """The actual reported bug: CRA bumped to 3001 because 3000 was taken."""
    resp = _preflight("http://localhost:3001")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3001"


def test_localhost_arbitrary_high_port_works():
    """Confirms this is a genuine 'any localhost port' fix, not a
    hardcoded list of a few extra guessed ports."""
    resp = _preflight("http://localhost:54321")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:54321"


def test_non_localhost_unknown_origin_still_rejected():
    """The regex is scoped to localhost only - this must not become a
    blanket allow-everything policy. A real, unrelated origin must still
    be rejected exactly as before."""
    resp = _preflight("http://evil-site.example.com")
    assert resp.headers.get("access-control-allow-origin") is None


def test_https_localhost_is_not_matched():
    """The regex requires http:// specifically - localhost dev servers
    are never served over https, and this keeps the pattern as narrow
    as it needs to be rather than broader than necessary."""
    resp = _preflight("https://localhost:3000")
    assert resp.headers.get("access-control-allow-origin") is None
