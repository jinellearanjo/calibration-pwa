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
    get_uncertainty_budgets,
    get_readings,
    get_acceptance_limit,
    get_instrument,
    get_session,
    update_session_status,
    get_weighing_repeatability_tests,
    get_weighing_off_center_readings,
    get_weighing_hysteresis_readings,
    get_temperature_repeatability_tests,
    get_electrical_tests,
)


def validate_session(session_id: str) -> dict:
    """Validate a calibration session and assign a compliance status.

    Reads the completed uncertainty budget(s) and compares each one's final
    applied uncertainty against the acceptance limit for the instrument
    type. Never recalculates anything — reads from uncertainty_budgets only.

    Pressure and Weighing sessions have exactly one budget. Temperature
    (one per setpoint) and Electrical (one per function-type/range) can
    have several — each is checked individually, and the overall session
    status is the WORST of all of them ("worst case wins"): any single
    REJECTED setpoint/range makes the whole session REJECTED, even if
    every other one passed; failing that, any single REVIEW REQUIRED
    makes the whole session REVIEW REQUIRED; only if every single one is
    ACCEPTED does the session get ACCEPTED. Flags always name which
    specific setpoint or function-type/range caused a failure, rather
    than just saying "something failed somewhere."

    Decision logic (per budget):
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
            - status (str): One of ACCEPTED, REVIEW REQUIRED, REJECTED -
              the overall, worst-case session status.
            - budgets (list[dict]): Per-budget detail, each with
              identifier (setpoint_label / function_type + range_label /
              None for Pressure-Weighing), final_applied_uncertainty,
              status, and flags specific to that budget.
            - acceptance_limit (float): Limit used for comparison.
            - flags (list[str]): Session-level flags (e.g. missing test
              data) that aren't tied to one specific budget.

    Raises:
        ValueError: If the session or instrument record cannot be found.
    """
    session_flags = []

    session_record = get_session(session_id)
    if session_record is None:
        raise ValueError(f"No session found for session_id={session_id}.")

    instrument_id = session_record.get("instrument_id")
    instrument_record = get_instrument(instrument_id)
    if instrument_record is None:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "budgets": [],
            "acceptance_limit": None,
            "flags": ["Instrument record not found. Cannot look up acceptance limit."],
        }
    instrument_type = instrument_record.get("type")

    acceptance_limit_record = get_acceptance_limit(instrument_type, "accuracy")
    if acceptance_limit_record is None:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "budgets": [],
            "acceptance_limit": None,
            "flags": [f"No acceptance limit found for instrument type '{instrument_type}'."],
        }
    acceptance_limit = acceptance_limit_record.get("limit_value")

    budgets = get_uncertainty_budgets(session_id) or []
    if not budgets:
        update_session_status(session_id, "REJECTED")
        return {
            "status": "REJECTED",
            "budgets": [],
            "acceptance_limit": acceptance_limit,
            "flags": ["No uncertainty budget has been calculated yet for this session."],
        }

    # Build a lookup from test id -> human-readable label, so a failing
    # budget can name exactly which setpoint or function-type/range caused
    # it, rather than just "the session". Also reused for the category's
    # own test-data completeness checks (same checks as before this
    # refactor, just moved here since they're needed either way).
    test_label_by_id: dict[str, str] = {}

    if instrument_type == "Weighing":
        repeatability_tests = get_weighing_repeatability_tests(session_id) or []
        off_center_readings = get_weighing_off_center_readings(session_id) or []
        hysteresis_readings = get_weighing_hysteresis_readings(session_id) or []

        expected_test_points = {"near_zero", "fifty_percent", "hundred_percent"}
        found_test_points = {t.get("test_point") for t in repeatability_tests}
        missing_test_points = expected_test_points - found_test_points
        if missing_test_points:
            session_flags.append(
                f"Repeatability test missing for load point(s): {', '.join(sorted(missing_test_points))}."
            )
        for test in repeatability_tests:
            reading_count = len(test.get("weighing_repeatability_readings", []) or [])
            if reading_count != 10:
                session_flags.append(
                    f"Repeatability test '{test.get('test_point')}' has {reading_count} "
                    f"of 10 required readings."
                )

        expected_positions = {"center", "front", "back", "left", "right"}
        found_positions = {r.get("position") for r in off_center_readings}
        missing_positions = expected_positions - found_positions
        if missing_positions:
            session_flags.append(
                f"Off-center test missing position(s): {', '.join(sorted(missing_positions))}."
            )

        if len(hysteresis_readings) != 5:
            session_flags.append(
                f"Hysteresis test has {len(hysteresis_readings)} of 5 required readings."
            )

        if not repeatability_tests and not off_center_readings and not hysteresis_readings:
            session_flags.append("No weighing test data found for this session.")

    elif instrument_type == "Temperature":
        repeatability_tests = get_temperature_repeatability_tests(session_id) or []
        if not repeatability_tests:
            session_flags.append("No temperature repeatability test data found for this session.")
        else:
            for test in repeatability_tests:
                test_label_by_id[test["id"]] = f"setpoint '{test.get('setpoint_label')}'"
                reading_count = len(test.get("temperature_repeatability_readings", []) or [])
                if reading_count != 3:
                    session_flags.append(
                        f"Repeatability test for setpoint '{test.get('setpoint_label')}' "
                        f"has {reading_count} of 3 required readings."
                    )

    elif instrument_type == "Electrical":
        electrical_tests = get_electrical_tests(session_id) or []
        if not electrical_tests:
            session_flags.append("No Electrical test data found for this session.")
        else:
            for test in electrical_tests:
                test_label_by_id[test["id"]] = (
                    f"{test.get('function_type')} range '{test.get('range_label')}'"
                )
                reading_count = len(test.get("electrical_readings", []) or [])
                if reading_count == 0:
                    session_flags.append(
                        f"{test.get('function_type')} range '{test.get('range_label')}' "
                        f"has no readings."
                    )

    else:
        # Pressure - single readings table, ascending/descending shape.
        readings = get_readings(session_id)
        if not readings:
            session_flags.append("No readings found for this session.")
            update_session_status(session_id, "REJECTED")
            return {
                "status": "REJECTED",
                "budgets": [],
                "acceptance_limit": acceptance_limit,
                "flags": session_flags,
            }

        for reading in readings:
            if reading.get("measured_value_up") is None or reading.get("measured_value_down") is None:
                session_flags.append(
                    f"Point {reading.get('point_number')} is missing ascending or descending measurement."
                )

        for reading in readings:
            hysteresis = reading.get("hysteresis")
            if hysteresis is not None and hysteresis > acceptance_limit:
                session_flags.append(
                    f"Point {reading.get('point_number')} hysteresis ({hysteresis}) "
                    f"exceeds acceptance limit ({acceptance_limit})."
                )

    # ── Per-budget evaluation ────────────────────────────────────────────────
    budget_results = []
    for budget in budgets:
        final_applied_uncertainty = budget.get("final_applied_uncertainty")
        test_id = budget.get("temperature_test_id") or budget.get("electrical_test_id")
        label = test_label_by_id.get(test_id)  # None for Pressure/Weighing - only one budget, no label needed

        budget_flags = []
        if final_applied_uncertainty is None:
            budget_status = "REJECTED"
            where = f" for {label}" if label else ""
            budget_flags.append(f"Final applied uncertainty is missing{where}.")
        elif final_applied_uncertainty > acceptance_limit:
            budget_status = "REVIEW REQUIRED"
            where = f"{label}: " if label else ""
            budget_flags.append(
                f"{where}final applied uncertainty ({final_applied_uncertainty}) "
                f"exceeds acceptance limit ({acceptance_limit})."
            )
        else:
            budget_status = "ACCEPTED"

        budget_results.append({
            "identifier": label,
            "final_applied_uncertainty": final_applied_uncertainty,
            "cmc": budget.get("cmc"),
            "status": budget_status,
            "flags": budget_flags,
        })

    # ── Aggregate: worst case wins ───────────────────────────────────────────
    all_flags = list(session_flags) + [f for b in budget_results for f in b["flags"]]
    missing_data_flags = [f for f in session_flags if "missing" in f.lower() or "no " in f.lower()]
    any_budget_rejected = any(b["status"] == "REJECTED" for b in budget_results)
    any_budget_review = any(b["status"] == "REVIEW REQUIRED" for b in budget_results)

    if missing_data_flags or any_budget_rejected:
        status = "REJECTED"
    elif any_budget_review:
        status = "REVIEW REQUIRED"
    else:
        status = "ACCEPTED"

    update_session_status(session_id, status)

    return {
        "status": status,
        "budgets": budget_results,
        "acceptance_limit": acceptance_limit,
        "flags": all_flags,
    }