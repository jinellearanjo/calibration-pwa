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
    get_weighing_repeatability_tests,
    get_weighing_off_center_readings,
    get_weighing_hysteresis_readings,
    get_temperature_repeatability_tests,
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

    if instrument_type == "Weighing":
        # Weighing sessions store raw data across three separate tables
        # rather than the single readings table used by Pressure/Electrical.
        # Completeness is checked against each of the three.
        repeatability_tests = get_weighing_repeatability_tests(session_id) or []
        off_center_readings = get_weighing_off_center_readings(session_id) or []
        hysteresis_readings = get_weighing_hysteresis_readings(session_id) or []

        expected_test_points = {"near_zero", "fifty_percent", "hundred_percent"}
        found_test_points = {t.get("test_point") for t in repeatability_tests}
        missing_test_points = expected_test_points - found_test_points
        if missing_test_points:
            flags.append(
                f"Repeatability test missing for load point(s): {', '.join(sorted(missing_test_points))}."
            )
        for test in repeatability_tests:
            reading_count = len(test.get("weighing_repeatability_readings", []) or [])
            if reading_count != 10:
                flags.append(
                    f"Repeatability test '{test.get('test_point')}' has {reading_count} "
                    f"of 10 required readings."
                )

        expected_positions = {"center", "front", "back", "left", "right"}
        found_positions = {r.get("position") for r in off_center_readings}
        missing_positions = expected_positions - found_positions
        if missing_positions:
            flags.append(
                f"Off-center test missing position(s): {', '.join(sorted(missing_positions))}."
            )

        if len(hysteresis_readings) != 5:
            flags.append(
                f"Hysteresis test has {len(hysteresis_readings)} of 5 required readings."
            )

        if not repeatability_tests and not off_center_readings and not hysteresis_readings:
            flags.append("No weighing test data found for this session.")

    elif instrument_type == "Temperature":
        # Temperature sessions store raw data in their own repeatability
        # table too, same reasoning as Weighing - the readings table's
        # single ascending/descending-per-point shape doesn't fit
        # Temperature's 3-repeated-readings-per-setpoint structure.
        repeatability_tests = get_temperature_repeatability_tests(session_id) or []
        if not repeatability_tests:
            flags.append("No temperature repeatability test data found for this session.")
        else:
            for test in repeatability_tests:
                reading_count = len(test.get("temperature_repeatability_readings", []) or [])
                if reading_count != 3:
                    flags.append(
                        f"Repeatability test for setpoint '{test.get('setpoint_label')}' "
                        f"has {reading_count} of 3 required readings."
                    )

    else:
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