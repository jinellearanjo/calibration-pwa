"""
modules/validation.py
=====================
Validation module for the calibration application.

Compares the final applied uncertainty from the uncertainty_budgets table
against the acceptance limit from the acceptance_limits table and assigns
a session status of ACCEPTED, REVIEW REQUIRED, or REJECTED.

Rules enforced throughout
--------------------------
* No calculation logic — reads completed uncertainty budget only.
* No hardcoded limit values — all limits come from acceptance_limits table.
* Only three permitted status values: ACCEPTED, REVIEW REQUIRED, REJECTED.
* All database access goes through functions imported from database.py.
* No raw database queries.
"""

from database import (
    get_uncertainty_budget,
    get_readings,
    get_acceptance_limit,
    get_instrument,
    get_session,
    update_session_status,
)


def validate_session(session_id: str) -> dict:
    """Validate a calibration session and assign a compliance status.

    Reads the completed uncertainty budget and compares the final applied
    uncertainty against the acceptance limit for the instrument type.
    Never recalculates anything — reads from uncertainty_budgets only.

    Decision logic:
    - ACCEPTED: final_applied_uncertainty is within the acceptance limit,
      all readings are present, and all required inputs are complete.
    - REVIEW REQUIRED: final_applied_uncertainty exceeds the acceptance
      limit, or hysteresis is outside the permitted range.
    - REJECTED: required inputs are missing or formula conditions
      cannot be met.

    Args:
        session_id: UUID of the calibration session to validate.

    Returns:
        dict: A result dictionary containing:
            - status (str): One of ACCEPTED, REVIEW REQUIRED, REJECTED.
            - final_applied_uncertainty (float): Value from uncertainty budget.
            - acceptance_limit (float): Limit used for comparison.
            - cmc (float): CMC value from uncertainty budget.
            - flags (list[str]): List of issue descriptions if any exist.

    Raises:
        ValueError: If the session, uncertainty budget, or instrument
            record cannot be found.
    """
    flags = []

    # Fetch session record to get instrument_id and status.
    session_record = get_session(session_id)
    if session_record is None:
        raise ValueError(f"No session found for session_id={session_id}.")

    # Fetch the completed uncertainty budget — never recalculate here.
    budget = get_uncertainty_budget(session_id)
    if budget is None:
        # Missing budget means required inputs are incomplete.
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "final_applied_uncertainty": None,
            "acceptance_limit": None,
            "cmc": None,
            "flags": ["Uncertainty budget is missing. Cannot validate session."],
        }

    final_applied_uncertainty = budget.get("final_applied_uncertainty")
    cmc = budget.get("cmc")

    # A missing final_applied_uncertainty means the budget is incomplete.
    if final_applied_uncertainty is None:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "final_applied_uncertainty": None,
            "acceptance_limit": None,
            "cmc": cmc,
            "flags": ["Final applied uncertainty is missing from budget."],
        }

    # Fetch the instrument to determine its type for the acceptance limit lookup.
    instrument_id = session_record.get("instrument_id")
    instrument_record = get_instrument(instrument_id)
    if instrument_record is None:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "final_applied_uncertainty": final_applied_uncertainty,
            "acceptance_limit": None,
            "cmc": cmc,
            "flags": ["Instrument record not found. Cannot look up acceptance limit."],
        }

    instrument_type = instrument_record.get("type")

    # Fetch acceptance limit from the table — no hardcoded values.
    acceptance_limit_record = get_acceptance_limit(instrument_type, "accuracy")
    if acceptance_limit_record is None:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "final_applied_uncertainty": final_applied_uncertainty,
            "acceptance_limit": None,
            "cmc": cmc,
            "flags": [
                f"No acceptance limit found for instrument type '{instrument_type}'."
            ],
        }

    acceptance_limit = acceptance_limit_record.get("limit_value")

    # Fetch readings to check completeness and hysteresis.
    readings = get_readings(session_id)
    if not readings:
        flags.append("No readings found for this session.")
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "final_applied_uncertainty": final_applied_uncertainty,
            "acceptance_limit": acceptance_limit,
            "cmc": cmc,
            "flags": flags,
        }

    # Check that every reading has both ascending and descending values.
    for reading in readings:
        if reading.get("measured_value_up") is None or reading.get("measured_value_down") is None:
            flags.append(
                f"Point {reading.get('point_number')} is missing ascending or descending measurement."
            )

    # Check hysteresis against acceptance limit for each reading.
    for reading in readings:
        hysteresis = reading.get("hysteresis")
        if hysteresis is not None and hysteresis > acceptance_limit:
            flags.append(
                f"Point {reading.get('point_number')} hysteresis ({hysteresis}) "
                f"exceeds acceptance limit ({acceptance_limit})."
            )

    # Determine final status based on uncertainty comparison and flags.
    if flags:
        # Incomplete readings mean we cannot validate — reject.
        missing_readings = [f for f in flags if "missing" in f.lower()]
        if missing_readings:
            status = "REJECTED"
        else:
            # Hysteresis out of range — needs human review.
            status = "REVIEW REQUIRED"
    elif final_applied_uncertainty <= acceptance_limit:
        status = "ACCEPTED"
    else:
        # Uncertainty exceeds limit — needs human review.
        status = "REVIEW REQUIRED"
        flags.append(
            f"Final applied uncertainty ({final_applied_uncertainty}) "
            f"exceeds acceptance limit ({acceptance_limit})."
        )

    update_session_status(session_id, status)

    return {
        "status": status,
        "final_applied_uncertainty": final_applied_uncertainty,
        "acceptance_limit": acceptance_limit,
        "cmc": cmc,
        "flags": flags,
    }