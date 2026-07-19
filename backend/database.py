from supabase import create_client, Client
from config import settings


def get_supabase_client() -> Client:
    """Create and return a Supabase client instance.

    Returns:
        Client: An authenticated Supabase client.

    Raises:
        ValueError: If Supabase URL or key are not set in environment.
    """
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("Supabase URL and service role key must be set in environment variables.")

    return create_client(settings.supabase_url, settings.supabase_key)


class _LazySupabaseClient:
    """Defers actual Supabase client creation until first real use, rather
    than at module import time.

    Previously `supabase: Client = get_supabase_client()` ran immediately
    when this module was imported, which means the ValueError it raises
    for missing SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY fires the instant
    ANYTHING imports database.py (directly or transitively via main.py) -
    including tooling that just wants to import the module for static
    analysis, doc generation, or tests that intend to mock the client
    entirely and never needed real credentials in the first place. This
    was a real, repeatedly-hit friction point during this project's own
    testing - every verification script needed dummy env vars set purely
    to get past this import-time check, even when the actual Supabase
    client was never going to be called (e.g. testing a pure calculation
    function).

    Every existing `database.supabase.table(...)` call site continues to
    work completely unchanged - this class forwards any attribute access
    it doesn't define itself (i.e. everything except _ensure_client) to a
    real Client, constructing that Client on first access rather than at
    class instantiation. Verified this remains fully compatible with
    unittest.mock.patch.object(database.supabase, "...") - the standard
    mocking pattern used throughout this project's test suite - since
    patching sets a real attribute directly on this instance, which
    normal Python attribute lookup finds before ever falling through to
    __getattr__.
    """
    def __init__(self):
        self._client = None

    def _ensure_client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def __getattr__(self, name):
        return getattr(self._ensure_client(), name)

    def reset(self) -> None:
        """Discard the cached client so the next call rebuilds it from
        scratch, with a fresh httpx connection pool.

        This client (and its one underlying HTTP/2 connection pool) is
        cached for the entire lifetime of the server process. If Supabase's
        end terminates a pooled connection (idle timeout, load balancer
        recycling, a laptop sleep/wake, a brief network drop) without
        httpx noticing, the next request to reuse it fails with
        httpx.RemoteProtocolError('ConnectionTerminated') - a genuinely
        unhandled exception type, not an HTTPException, which crashes past
        FastAPI's normal response handling (and, as a side effect, past
        CORSMiddleware's header injection too - which is why this can look
        like a CORS error in the browser rather than what it actually is).
        main.py's exception handler for httpx.TransportError calls this to
        recover automatically instead of requiring a manual server restart.
        """
        self._client = None


supabase = _LazySupabaseClient()


def get_instrument(instrument_id: str) -> dict:
    """Fetch a single instrument record by ID.

    Args:
        instrument_id: The UUID of the instrument.

    Returns:
        dict: The instrument record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("instruments").select("*").eq("id", instrument_id).single().execute()
    return response.data


def get_session(session_id: str) -> dict:
    """Fetch a single calibration session by ID.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        dict: The calibration session record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("calibration_sessions").select("*").eq("id", session_id).single().execute()
    return response.data


def get_readings(session_id: str) -> list:
    """Fetch all readings for a calibration session.

    Applies to Pressure sessions only. Weighing sessions store their raw
    data in the weighing_* tables, Temperature in
    temperature_repeatability_tests/readings, and Electrical in
    electrical_tests/readings - each has its own dedicated tables, none
    of them use this generic readings table. (This comment previously
    claimed Electrical used this table too - already flagged and fixed
    once before for this exact function; re-confirmed false by reading
    formula_manager.py's dispatch logic directly.)

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: A list of reading records ordered by point number.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("readings").select("*").eq("session_id", session_id).order("point_number").execute()
    return response.data


def delete_readings(session_id: str) -> None:
    """Delete every reading row for a session.

    Called before re-inserting a fresh set of readings (see
    create_reading's caller in ReadingsForm.jsx's submit flow), so
    resubmitting the same session doesn't stack duplicate rows on top of
    whatever's already there - the exact bug that was already found and
    fixed once for uncertainty_budgets (Round 10's delete_uncertainty_
    budgets) but was never extended to the readings themselves. Without
    this, submitting the same Pressure session's readings twice (e.g. a
    user navigating back to Step 04 and resubmitting) silently created a
    second full set of rows for the same point numbers every time.

    Args:
        session_id: The UUID of the calibration session whose readings
            should be cleared.

    Raises:
        Exception: If the delete query fails.
    """
    supabase.table("readings").delete().eq("session_id", session_id).execute()


def get_uncertainty_budgets(session_id: str) -> list:
    """Fetch ALL uncertainty budget rows for a calibration session.

    Renamed from the old get_uncertainty_budget (singular): Pressure and
    Weighing sessions still only ever have one budget row, but Temperature
    (one per setpoint) and Electrical (one per function-type/range) can
    have several. Previously used .single(), which would raise if more
    than one row matched - now returns a plain list, empty if none exist
    yet, so callers can handle "0 budgets" and "many budgets" the same way.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: All uncertainty budget records for this session, in
            insertion order. Empty list if none exist yet.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("uncertainty_budgets").select("*").eq("session_id", session_id).execute()
    return response.data


def get_master_instrument(master_id: str) -> dict:
    """Fetch a single master instrument record by ID.

    Args:
        master_id: The UUID of the master instrument.

    Returns:
        dict: The master instrument record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("master_instruments").select("*").eq("id", master_id).single().execute()
    return response.data


def get_calibration_reference(session_id: str) -> dict:
    """Fetch the calibration reference details for a session.

    Uses maybe_single() rather than single(): PostgREST's .single() raises
    an exception (not a clean "not found") when zero rows match, which
    previously crashed both call sites below their "if not X: raise 404"
    checks before those checks ever ran - the unhandled crash also bypassed
    CORSMiddleware's header injection, which made it show up in the browser
    as a misleading "blocked by CORS policy" error rather than a normal 404.
    maybe_single() returns None on zero rows instead, letting the existing
    callers' None-checks work as originally intended.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        dict: The calibration reference record, or None if none exists yet.

    Raises:
        Exception: If the database query fails for a reason other than
            "no matching row".
    """
    response = supabase.table("calibration_reference").select("*").eq("session_id", session_id).maybe_single().execute()
    return response.data


def get_acceptance_limit(instrument_type: str, parameter: str) -> dict:
    """Fetch the acceptance limit for a given instrument type and parameter.

    Uses maybe_single() rather than single() - see get_calibration_reference's
    docstring above for why. validation.py already checks this function's
    return value for None and responds with a clean "REJECTED, no acceptance
    limit configured" result; single() previously crashed before that check
    ever ran whenever an instrument type had no acceptance limit row yet.

    Args:
        instrument_type: The type of instrument (e.g. Pressure, Temperature).
        parameter: The parameter being checked (e.g. accuracy).

    Returns:
        dict: The acceptance limit record, or None if none exists yet.

    Raises:
        Exception: If the database query fails for a reason other than
            "no matching row".
    """
    response = supabase.table("acceptance_limits").select("*").eq("instrument_type", instrument_type).eq("parameter", parameter).maybe_single().execute()
    return response.data


def insert_uncertainty_budget(budget: dict) -> dict:
    """Insert a new uncertainty budget record.

    Args:
        budget: A dictionary of uncertainty budget fields and values.

    Returns:
        dict: The inserted uncertainty budget record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("uncertainty_budgets").insert(budget).execute()
    return response.data


def delete_calibration_session_cascade(session_id: str) -> None:
    """Delete a calibration session and every row across every instrument
    category that depends on it, in dependency order (child rows before
    parent rows, so a foreign key never blocks a later delete in this
    same function).

    This does NOT rely on the database having ON DELETE CASCADE set up
    correctly on every table - electrical_tests/electrical_readings and
    uncertainty_budgets.temperature_test_id/electrical_test_id do have
    CASCADE defined in migrations/2026-07-08_electrical_and_multi_budget_
    support.sql, but the original tables (readings, weighing_*,
    temperature_repeatability_tests, calibration_reference,
    uncertainty_budgets.session_id itself) were created directly in the
    Supabase table editor before this repo's migrations folder existed,
    so their cascade behavior was never confirmed in code. Every table is
    deleted explicitly here regardless - deleting rows that a DB-level
    cascade already removed is a harmless no-op, so this is safe either way.

    Args:
        session_id: The UUID of the calibration session to delete, along
            with all of its nested test data.

    Raises:
        Exception: If any individual delete query fails.
    """
    # Weighing: readings key off test_id, so must be deleted before their
    # parent test rows.
    weighing_tests = (
        supabase.table("weighing_repeatability_tests")
        .select("id").eq("session_id", session_id).execute().data
    )
    for t in weighing_tests:
        supabase.table("weighing_repeatability_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("weighing_repeatability_tests").delete().eq("session_id", session_id).execute()
    supabase.table("weighing_off_center_readings").delete().eq("session_id", session_id).execute()
    supabase.table("weighing_hysteresis_readings").delete().eq("session_id", session_id).execute()

    # Temperature: same test_id-before-parent order as Weighing.
    temperature_tests = (
        supabase.table("temperature_repeatability_tests")
        .select("id").eq("session_id", session_id).execute().data
    )
    for t in temperature_tests:
        supabase.table("temperature_repeatability_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("temperature_repeatability_tests").delete().eq("session_id", session_id).execute()

    # Electrical: same shape again.
    electrical_tests = (
        supabase.table("electrical_tests")
        .select("id").eq("session_id", session_id).execute().data
    )
    for t in electrical_tests:
        supabase.table("electrical_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("electrical_tests").delete().eq("session_id", session_id).execute()

    # Pressure's generic readings table.
    supabase.table("readings").delete().eq("session_id", session_id).execute()

    # Uncertainty budgets (covers Pressure/Weighing's single row per
    # session as well as any Temperature/Electrical rows not already
    # removed via their test_id's cascade above).
    supabase.table("uncertainty_budgets").delete().eq("session_id", session_id).execute()

    # Calibration reference (certificate number, customer details, etc.)
    supabase.table("calibration_reference").delete().eq("session_id", session_id).execute()

    # Finally the session row itself.
    supabase.table("calibration_sessions").delete().eq("id", session_id).execute()


def delete_instrument_cascade(instrument_id: str) -> None:
    """Delete an instrument and every calibration session that references
    it (each fully cascaded via delete_calibration_session_cascade), then
    the instrument row itself.

    Args:
        instrument_id: The UUID of the instrument to delete, along with
            every session (and that session's nested test data) that
            references it.

    Raises:
        Exception: If any individual delete query fails.
    """
    sessions = (
        supabase.table("calibration_sessions")
        .select("id").eq("instrument_id", instrument_id).execute().data
    )
    for s in sessions:
        delete_calibration_session_cascade(s["id"])
    supabase.table("instruments").delete().eq("id", instrument_id).execute()


def delete_uncertainty_budgets(session_id: str) -> None:
    """Delete all uncertainty budget rows for a session.

    Called before inserting freshly-calculated budgets, since
    insert_uncertainty_budget is a plain insert with no dedup/upsert
    logic - without this, recalculating a session (e.g. clicking
    "Recalculate" in CalculationView.jsx) would accumulate duplicate
    budget rows every time rather than replacing the old ones, since
    there's nothing else stopping a second calculate call from just
    inserting a second full set of budgets on top of the first. Caught
    via an external code review while checking a related architectural
    concern - verified empirically that this endpoint truly had no
    delete-before-insert step.

    Args:
        session_id: The UUID of the calibration session whose budgets
            should be cleared before recalculating.

    Raises:
        Exception: If the database query fails.
    """
    supabase.table("uncertainty_budgets").delete().eq("session_id", session_id).execute()


def update_session_status(session_id: str, status: str) -> dict:
    """Update the status of a calibration session.

    Args:
        session_id: The UUID of the calibration session.
        status: The new status value (ACCEPTED, REVIEW REQUIRED, or REJECTED).

    Returns:
        dict: The updated session record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("calibration_sessions").update({"status": status}).eq("id", session_id).execute()
    return response.data


def insert_audit_log(entry: dict) -> dict:
    """Insert a new audit log entry.

    Args:
        entry: A dictionary containing audit log fields and values.

    Returns:
        dict: The inserted audit log record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("audit_log").insert(entry).execute()
    return response.data


# ── Weighing: Repeatability test ────────────────────────────────────────────

def insert_weighing_repeatability_test(test: dict) -> dict:
    """Insert a weighing repeatability test record (one per test_point).

    Args:
        test: A dictionary of weighing_repeatability_tests fields and values.

    Returns:
        dict: The inserted test record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("weighing_repeatability_tests").insert(test).execute()
    return response.data


def delete_weighing_repeatability_test_by_key(session_id: str, test_point: str) -> None:
    """Delete any existing repeatability test (and its readings) for this
    session and test_point, before inserting a fresh one.

    Unlike off-center/hysteresis, a session can have multiple repeatability
    tests - one per test_point (near_zero/fifty_percent/hundred_percent) -
    so this must NOT delete every repeatability test for the session (that
    would silently wipe out other test points still on record). Deletes
    only the specific (session_id, test_point) match: its child readings
    first (keyed by test_id, no reliable DB-level cascade - see
    delete_calibration_session_cascade's docstring), then the test row
    itself. A no-op if no existing test matches, which is the normal case
    for a genuinely new test_point.

    Args:
        session_id: The UUID of the calibration session.
        test_point: Which of the three fixed load points to clear before
            re-inserting ('near_zero' | 'fifty_percent' | 'hundred_percent').

    Raises:
        Exception: If the database query fails.
    """
    existing = (
        supabase.table("weighing_repeatability_tests")
        .select("id")
        .eq("session_id", session_id)
        .eq("test_point", test_point)
        .execute()
        .data
    )
    for t in existing:
        supabase.table("weighing_repeatability_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("weighing_repeatability_tests").delete().eq("session_id", session_id).eq("test_point", test_point).execute()


def insert_weighing_repeatability_readings(readings: list) -> list:
    """Bulk-insert the 10 readings for a weighing repeatability test.

    Args:
        readings: A list of dictionaries, each matching
            weighing_repeatability_readings columns. All readings should
            share the same test_id.

    Returns:
        list: The inserted reading records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("weighing_repeatability_readings").insert(readings).execute()
    return response.data


def get_weighing_repeatability_tests(session_id: str) -> list:
    """Fetch all repeatability test records (and their readings) for a session.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: Test records, each with a nested list of its 10 readings via
            the weighing_repeatability_readings foreign key relationship.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("weighing_repeatability_tests")
        .select("*, weighing_repeatability_readings(*)")
        .eq("session_id", session_id)
        .execute()
    )
    return response.data


# ── Weighing: Off-center (eccentricity) test ────────────────────────────────

def insert_weighing_off_center_readings(readings: list) -> list:
    """Bulk-insert the 5 off-center position readings for a session.

    Args:
        readings: A list of dictionaries, each matching
            weighing_off_center_readings columns. All readings should share
            the same session_id, one per position.

    Returns:
        list: The inserted reading records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("weighing_off_center_readings").insert(readings).execute()
    return response.data


def get_weighing_off_center_readings(session_id: str) -> list:
    """Fetch all off-center readings for a session.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: Off-center reading records for all five positions.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("weighing_off_center_readings")
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    return response.data


def delete_weighing_off_center_readings(session_id: str) -> None:
    """Delete all existing off-center readings for a session.

    Off-center is always submitted as one complete, atomic set of exactly
    5 rows (one per position) tied only to session_id - there's no
    sub-key like test_point/setpoint_label to worry about, so a full
    delete-before-insert (the same shape as Pressure's delete_readings)
    is safe and correct here. Call this immediately before re-inserting,
    to fix resubmission stacking duplicate position rows on top of the
    existing set every time the form is saved again.

    Args:
        session_id: The UUID of the calibration session whose off-center
            readings should be cleared before re-inserting.

    Raises:
        Exception: If the database query fails.
    """
    supabase.table("weighing_off_center_readings").delete().eq("session_id", session_id).execute()


# ── Weighing: Hysteresis test ────────────────────────────────────────────────

def insert_weighing_hysteresis_readings(readings: list) -> list:
    """Bulk-insert the 5-step hysteresis sequence readings for a session.

    Args:
        readings: A list of dictionaries, each matching
            weighing_hysteresis_readings columns. All readings should share
            the same session_id, ordered by sequence_order 1-5.

    Returns:
        list: The inserted reading records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("weighing_hysteresis_readings").insert(readings).execute()
    return response.data


def get_weighing_hysteresis_readings(session_id: str) -> list:
    """Fetch all hysteresis sequence readings for a session, in order.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: Hysteresis reading records ordered by sequence_order.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("weighing_hysteresis_readings")
        .select("*")
        .eq("session_id", session_id)
        .order("sequence_order")
        .execute()
    )
    return response.data


def delete_weighing_hysteresis_readings(session_id: str) -> None:
    """Delete all existing hysteresis readings for a session.

    Same reasoning as delete_weighing_off_center_readings above:
    hysteresis is always submitted as one complete, atomic set of exactly
    5 sequence steps tied only to session_id, so a full delete-before-
    insert is safe and correct.

    Args:
        session_id: The UUID of the calibration session whose hysteresis
            readings should be cleared before re-inserting.

    Raises:
        Exception: If the database query fails.
    """
    supabase.table("weighing_hysteresis_readings").delete().eq("session_id", session_id).execute()


# ── CMC bands ─────────────────────────────────────────────────────────────────

def get_cmc_band(instrument_type: str, load_value: float) -> dict:
    """Look up the CMC band applicable to a given load value.

    Finds the row in cmc_bands where min_value <= load_value < max_value
    for the given instrument_type. Note this performs the range comparison
    in Python after fetching candidate rows, rather than as a single
    Supabase range filter, since Supabase's query builder doesn't support
    "value between two columns" filters directly.

    Args:
        instrument_type: The type of instrument (e.g. 'Weighing').
        load_value: The load value to look up a CMC band for.

    Returns:
        dict: The matching cmc_bands record, or None if no band covers
            this load_value.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("cmc_bands")
        .select("*")
        .eq("instrument_type", instrument_type)
        .execute()
    )
    for band in response.data or []:
        if band["min_value"] <= load_value < band["max_value"]:
            return band
    return None


# ── Temperature: Repeatability test ──────────────────────────────────────────

def insert_temperature_repeatability_test(test: dict) -> dict:
    """Insert a temperature repeatability test record (one per setpoint).

    Args:
        test: A dictionary of temperature_repeatability_tests fields and values.

    Returns:
        dict: The inserted test record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("temperature_repeatability_tests").insert(test).execute()
    return response.data


def delete_temperature_repeatability_test_by_key(session_id: str, setpoint_label: str) -> None:
    """Delete any existing repeatability test (and its readings) for this
    session and setpoint_label, before inserting a fresh one.

    Same reasoning as delete_weighing_repeatability_test_by_key: a session
    can have multiple setpoints tested (e.g. -15C, 110C, 300C, 650C), so
    only the matching setpoint_label is cleared, not every test for the
    session.

    Args:
        session_id: The UUID of the calibration session.
        setpoint_label: Which setpoint to clear before re-inserting
            (e.g. 'minus_15c').

    Raises:
        Exception: If the database query fails.
    """
    existing = (
        supabase.table("temperature_repeatability_tests")
        .select("id")
        .eq("session_id", session_id)
        .eq("setpoint_label", setpoint_label)
        .execute()
        .data
    )
    for t in existing:
        supabase.table("temperature_repeatability_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("temperature_repeatability_tests").delete().eq("session_id", session_id).eq("setpoint_label", setpoint_label).execute()


def insert_temperature_repeatability_readings(readings: list) -> list:
    """Bulk-insert the 3 readings for a temperature repeatability test.

    Args:
        readings: A list of dictionaries, each matching
            temperature_repeatability_readings columns. All readings should
            share the same test_id.

    Returns:
        list: The inserted reading records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("temperature_repeatability_readings").insert(readings).execute()
    return response.data


def get_temperature_repeatability_tests(session_id: str) -> list:
    """Fetch all repeatability test records (and their readings) for a session.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: Test records, each with a nested list of its 3 readings via
            the temperature_repeatability_readings foreign key relationship.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("temperature_repeatability_tests")
        .select("*, temperature_repeatability_readings(*)")
        .eq("session_id", session_id)
        .execute()
    )
    return response.data


def insert_electrical_test(test: dict) -> list:
    """Insert a new Electrical test record (one function-type/range).

    Args:
        test: A dictionary of electrical_tests fields and values.

    Returns:
        list: The inserted test record (Supabase's insert response,
            same shape as insert_temperature_repeatability_test).

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("electrical_tests").insert(test).execute()
    return response.data


def delete_electrical_test_by_key(session_id: str, function_type: str, range_label: str) -> None:
    """Delete any existing Electrical test (and its readings) for this
    session, function_type, and range_label, before inserting a fresh one.

    Same reasoning as the Weighing/Temperature equivalents above: a
    session can have multiple Electrical tests - one per function-type/
    range combination (e.g. DCV 20mV, DCV 200mV, ACA 50A) - so only the
    matching (function_type, range_label) pair is cleared, not every
    test for the session.

    Args:
        session_id: The UUID of the calibration session.
        function_type: The function type to clear before re-inserting
            (e.g. 'DCV', 'ACA (Coil)').
        range_label: The range within that function type (e.g. '20mV').

    Raises:
        Exception: If the database query fails.
    """
    existing = (
        supabase.table("electrical_tests")
        .select("id")
        .eq("session_id", session_id)
        .eq("function_type", function_type)
        .eq("range_label", range_label)
        .execute()
        .data
    )
    for t in existing:
        supabase.table("electrical_readings").delete().eq("test_id", t["id"]).execute()
    supabase.table("electrical_tests").delete().eq("session_id", session_id).eq("function_type", function_type).eq("range_label", range_label).execute()


def insert_electrical_readings(readings: list) -> list:
    """Insert multiple Electrical readings for a single test.

    Args:
        readings: A list of dictionaries, each matching the
            electrical_readings table shape (test_id, reading_number,
            reading_value).

    Returns:
        list: The inserted reading records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("electrical_readings").insert(readings).execute()
    return response.data


def get_electrical_tests(session_id: str) -> list:
    """Fetch all Electrical test records (and their readings) for a session.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: Test records, each with a nested list of its readings via
            the electrical_readings foreign key relationship.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("electrical_tests")
        .select("*, electrical_readings(*)")
        .eq("session_id", session_id)
        .execute()
    )
    return response.data


# ── Profiles (roles) ─────────────────────────────────────────────────────────

def get_profile(user_id: str) -> dict:
    """Fetch a user's profile (full_name, title).

    Uses maybe_single() rather than single() - a missing profile (e.g. an
    account created before the 2026-07-19 migration's handle_new_user
    trigger existed) is an expected, non-exceptional case, not a crash;
    callers (see auth.get_current_user_title) default to "Viewer" when
    this returns None.

    Args:
        user_id: The UUID of the user.

    Returns:
        dict: The profile record, or None if no profile row exists yet.

    Raises:
        Exception: If the database query fails for a reason other than
            "no matching row".
    """
    response = supabase.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    return response.data


def list_profiles() -> list:
    """Fetch every user's profile - used for the full-edit-tier "see all
    activity" view and for resolving names/titles for display (e.g. who
    submitted a pending role-change request).

    Returns:
        list: All profile records.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("profiles").select("*").execute()
    return response.data


def update_profile(user_id: str, full_name: str = None, title: str = None) -> dict:
    """Update a user's profile.

    Only the fields actually provided are updated. Role/title changes
    should normally go through the role_change_request approval flow
    (see update_role_change_request below) rather than calling this
    directly with a new title - this function itself doesn't enforce
    that; main.py's endpoints are what decide when a direct title change
    is allowed (e.g. approving a request) versus not.

    Args:
        user_id: The UUID of the user whose profile to update.
        full_name: New display name, if changing.
        title: New job title, if changing.

    Returns:
        dict: The updated profile record.

    Raises:
        Exception: If the database query fails.
    """
    updates = {}
    if full_name is not None:
        updates["full_name"] = full_name
    if title is not None:
        updates["title"] = title
    response = supabase.table("profiles").update(updates).eq("id", user_id).execute()
    return response.data


# ── Role change requests ────────────────────────────────────────────────────

def insert_role_change_request(request: dict) -> dict:
    """Insert a new role-change request (pending status).

    Args:
        request: A dictionary matching role_change_requests columns
            (user_id, requested_title, reason).

    Returns:
        dict: The inserted request record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("role_change_requests").insert(request).execute()
    return response.data


def get_pending_role_change_request_for_user(user_id: str) -> dict:
    """Check whether a user already has a pending (unreviewed) request.

    Used to enforce "only one pending request at a time" in application
    code (main.py), rather than a DB constraint - a denied request can
    always be resubmitted, so this only ever blocks a SECOND simultaneous
    pending request, not a new one after a prior denial.

    Args:
        user_id: The UUID of the user.

    Returns:
        dict: The pending request record, or None if none exists.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("role_change_requests")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .maybe_single()
        .execute()
    )
    return response.data


def list_role_change_requests(status: str = None) -> list:
    """Fetch role-change requests, optionally filtered by status.

    Args:
        status: If given, only return requests in this status
            ("pending", "approved", "denied"). If None, return all.

    Returns:
        list: Matching request records.

    Raises:
        Exception: If the database query fails.
    """
    query = supabase.table("role_change_requests").select("*")
    if status is not None:
        query = query.eq("status", status)
    response = query.execute()
    return response.data


def update_role_change_request(request_id: str, status: str, reviewed_by: str) -> dict:
    """Mark a role-change request as approved or denied.

    Does NOT itself update the requester's profile.title - main.py's
    endpoint calls update_profile separately on approval, keeping "record
    the decision" and "apply the decision" as two explicit steps rather
    than one function silently doing both.

    Args:
        request_id: The UUID of the request.
        status: "approved" or "denied".
        reviewed_by: The UUID of the full-edit-tier user making the decision.

    Returns:
        dict: The updated request record.

    Raises:
        Exception: If the database query fails.
    """
    response = (
        supabase.table("role_change_requests")
        .update({"status": status, "reviewed_by": reviewed_by, "reviewed_at": "now()"})
        .eq("id", request_id)
        .execute()
    )
    return response.data


# ── Session review workflow ──────────────────────────────────────────────────

def flag_session_for_review(session_id: str, review_note: str) -> None:
    """Mark a session as needing full-edit-tier review before its
    certificate can be generated.

    Called when a master-instrument validity check fails at calculation/
    report time (see validation.check_master_instrument_validity). Most
    sessions never call this - review_status defaults to "clean" and
    certificate generation proceeds immediately, exactly as before this
    workflow existed.

    Args:
        session_id: The UUID of the calibration session.
        review_note: Why this session was flagged (e.g. "Master instrument
            'Budenberg DWT-2' calibration expired 2026-05-01"), shown to
            both the reviewer and the original technician.

    Raises:
        Exception: If the database query fails.
    """
    supabase.table("calibration_sessions").update({
        "review_status": "pending_review",
        "review_note": review_note,
    }).eq("id", session_id).execute()


def resolve_session_review(session_id: str, approved: bool, reviewed_by: str, review_note: str = None) -> None:
    """Approve or reject a flagged session, recorded by a full-edit-tier user.

    Args:
        session_id: The UUID of the calibration session.
        approved: True to approve (certificate generation unblocks), False
            to reject.
        reviewed_by: The UUID of the full-edit-tier user making the decision.
        review_note: Optional replacement/updated note - e.g. a rejection
            reason beyond the original flag. If None, the existing
            review_note (the original flag reason) is left as-is.

    Raises:
        Exception: If the database query fails.
    """
    updates = {
        "review_status": "approved" if approved else "rejected",
        "reviewed_by": reviewed_by,
        "reviewed_at": "now()",
    }
    if review_note is not None:
        updates["review_note"] = review_note
    supabase.table("calibration_sessions").update(updates).eq("id", session_id).execute()