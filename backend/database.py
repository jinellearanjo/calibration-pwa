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

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        dict: The calibration reference record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("calibration_reference").select("*").eq("session_id", session_id).single().execute()
    return response.data


def get_acceptance_limit(instrument_type: str, parameter: str) -> dict:
    """Fetch the acceptance limit for a given instrument type and parameter.

    Args:
        instrument_type: The type of instrument (e.g. Pressure, Temperature).
        parameter: The parameter being checked (e.g. accuracy).

    Returns:
        dict: The acceptance limit record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("acceptance_limits").select("*").eq("instrument_type", instrument_type).eq("parameter", parameter).single().execute()
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