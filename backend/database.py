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