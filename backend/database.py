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


supabase: Client = get_supabase_client()


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

    Applies to Pressure, Temperature, and Electrical sessions. Weighing
    sessions store their raw data in the weighing_* tables instead — see
    get_weighing_repeatability_tests, get_weighing_off_center_readings,
    and get_weighing_hysteresis_readings below.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        list: A list of reading records ordered by point number.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("readings").select("*").eq("session_id", session_id).order("point_number").execute()
    return response.data


def get_uncertainty_budget(session_id: str) -> dict:
    """Fetch the uncertainty budget for a calibration session.

    Args:
        session_id: The UUID of the calibration session.

    Returns:
        dict: The uncertainty budget record.

    Raises:
        Exception: If the database query fails.
    """
    response = supabase.table("uncertainty_budgets").select("*").eq("session_id", session_id).single().execute()
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