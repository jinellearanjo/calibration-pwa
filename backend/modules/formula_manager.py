"""formula_manager.py

Loads the per-category formula definition JSON files (formulas/*.json) and
orchestrates building an uncertainty budget for a session by gathering the
right data from the database and dispatching to the correct
calculation_engine functions for that instrument_type.

Pressure and Weighing have real formula files and are fully wired.
Temperature and Electrical raise NotImplementedError until their Excel
files arrive from the supervisor and formulas/temperature.json /
formulas/electrical.json are written.

Deliberately NOT a single generic parser: Pressure's formula shape (flat
type_b_sources list) and Weighing's (procedural, multi-test) are different
enough that forcing them through one function would make both harder to
read. Each category gets its own branch in build_uncertainty_budget.
"""

import json
from pathlib import Path

import database
from modules import calculation_engine as ce

FORMULAS_DIR = Path(__file__).parent.parent / "formulas"


def parse_excel_formula_file(instrument_type: str) -> dict:
    """Load the formula definition JSON for a given instrument type.

    Despite the name (kept from the original roadmap naming), this reads
    the already-extracted formulas/*.json file rather than parsing the
    supervisor's Excel file directly at runtime — the Excel-to-JSON
    extraction is a one-time manual step done via check_excel.py plus
    hand-analysis (see formulas/pressure.json and formulas/weighing.json
    for how that extraction was done), not something repeated on every
    calculation request.

    Args:
        instrument_type: One of 'Pressure', 'Temperature', 'Electrical', 'Weighing'.

    Returns:
        dict: The parsed formula definition for this instrument type.

    Raises:
        FileNotFoundError: If no formulas/{instrument_type}.json file exists
            yet for this category (expected for Temperature/Electrical
            until their supervisor files arrive).
        ValueError: If the file exists but contains invalid JSON.
    """
    file_path = FORMULAS_DIR / f"{instrument_type.lower()}.json"
    if not file_path.exists():
        raise FileNotFoundError(
            f"No formula file found for instrument_type='{instrument_type}' "
            f"at {file_path}. This category is likely still blocked on the "
            f"supervisor's Excel file — see the project roadmap's 'Blocked "
            f"by Supervisor' section."
        )
    try:
        with open(file_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}")


def build_uncertainty_budget(session_id: str) -> dict:
    """Build the full uncertainty budget for a calibration session.

    Gathers the instrument, session, master instrument, and readings data
    needed, then dispatches to the correct calculation_engine functions
    based on the instrument's type.

    Args:
        session_id: UUID of the calibration session to calculate for.

    Returns:
        dict: The uncertainty budget fields, matching UncertaintyBudgetCreate,
            with session_id included — ready to pass directly to
            database.insert_uncertainty_budget.

    Raises:
        ValueError: If the session, instrument, or master instrument can't
            be found, if the master instrument is missing required numeric
            fields (uncertainty_u, accuracy, claimed_cmc — the "TBA" fields
            flagged when the reference workbook came back partially filled),
            or if required test data is incomplete.
        NotImplementedError: If instrument_type is Temperature or Electrical
            (formula files not yet available).
        FileNotFoundError: If no formula file exists for this instrument_type.
    """
    session = database.get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found.")

    instrument = database.get_instrument(session["instrument_id"])
    if not instrument:
        raise ValueError(f"Instrument {session['instrument_id']} not found for session {session_id}.")

    instrument_type = instrument["type"]

    master_instrument_id = session.get("master_instrument_id")
    if not master_instrument_id:
        raise ValueError(
            f"Session {session_id} has no master_instrument_id set. A master "
            f"instrument must be linked before an uncertainty budget can be "
            f"calculated — set this on the session (see SessionForm.jsx's "
            f"master instrument picker)."
        )
    master = database.get_master_instrument(master_instrument_id)
    if not master:
        raise ValueError(f"Master instrument {master_instrument_id} not found.")

    if instrument_type == "Pressure":
        return _build_pressure_budget(session_id, instrument, master)
    elif instrument_type == "Weighing":
        return _build_weighing_budget(session_id, instrument, master)
    elif instrument_type == "Temperature":
        return _build_temperature_budget(session_id, instrument, master)
    elif instrument_type == "Electrical":
        raise NotImplementedError(
            f"Calculation engine for instrument_type='Electrical' is not yet "
            f"implemented — this category has 11 separate function types "
            f"(DCV/ACV/DCA/ACA/Resistance/Frequency/etc), each needing its own "
            f"formula definition. See formulas/electrical.json (does not exist yet)."
        )
    else:
        raise ValueError(f"Unknown instrument_type: '{instrument_type}'.")


def _build_pressure_budget(session_id: str, instrument: dict, master: dict) -> dict:
    """Build the uncertainty budget for a Pressure session.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        dict: Uncertainty budget fields with session_id included.

    Raises:
        ValueError: If readings are missing, or the master instrument is
            missing uncertainty_u, accuracy, or claimed_cmc (the fields
            still marked "TBA" in the reference workbook for most
            instruments as of the last check).
    """
    readings = database.get_readings(session_id)
    if not readings:
        raise ValueError(
            f"No readings found for session {session_id}. Enter calibration "
            f"readings before calculating the uncertainty budget."
        )

    _require_master_field(master, "uncertainty_u")
    _require_master_field(master, "accuracy")
    _require_master_field(master, "claimed_cmc")

    budget = ce.build_pressure_uncertainty_budget(
        readings=readings,
        master_uncertainty=master["uncertainty_u"],
        master_accuracy=master["accuracy"],
        resolution=instrument["resolution"],
        cmc=master["claimed_cmc"],
    )
    budget["session_id"] = session_id
    return budget


def _build_weighing_budget(session_id: str, instrument: dict, master: dict) -> dict:
    """Build the uncertainty budget for a Weighing session.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        dict: Uncertainty budget fields with session_id included.

    Raises:
        ValueError: If any of the three weighing tests are incomplete, or
            no CMC band covers the session's hundred_percent load value.
    """
    repeatability_tests = database.get_weighing_repeatability_tests(session_id)
    off_center_readings = database.get_weighing_off_center_readings(session_id)

    if not repeatability_tests:
        raise ValueError(
            f"No repeatability test data found for session {session_id}. "
            f"Enter weighing test readings before calculating the uncertainty budget."
        )
    if not off_center_readings:
        raise ValueError(
            f"No off-center test data found for session {session_id}. "
            f"Enter the 5-position off-center test before calculating."
        )

    # Rename the nested Supabase relation key to what calculation_engine expects.
    for test in repeatability_tests:
        if "weighing_repeatability_readings" in test:
            test["readings"] = test.pop("weighing_repeatability_readings")

    hundred_percent_test = next(
        (t for t in repeatability_tests if t.get("test_point") == "hundred_percent"), None
    )
    if hundred_percent_test is None:
        raise ValueError(
            f"hundred_percent repeatability test not found for session {session_id}. "
            f"All three test points (near_zero, fifty_percent, hundred_percent) are required."
        )

    load_value_g = hundred_percent_test["nominal_load"]
    if hundred_percent_test["unit"] == "kg":
        load_value_g = load_value_g * 1000

    cmc_bands_response = database.supabase.table("cmc_bands").select("*").eq(
        "instrument_type", "Weighing"
    ).execute()
    cmc_bands = cmc_bands_response.data
    if not cmc_bands:
        raise ValueError(
            "cmc_bands table has no rows for instrument_type='Weighing'. "
            "Seed this table before calculating weighing uncertainty budgets — "
            "see formulas/weighing.json's cmc_table_from_source_file for the "
            "band structure (values still need confirmation from the supervisor)."
        )

    budget = ce.build_weighing_uncertainty_budget(
        repeatability_tests=repeatability_tests,
        off_center_readings=off_center_readings,
        resolution=instrument["resolution"],
        load_value_g=load_value_g,
        cmc_bands=cmc_bands,
    )
    budget["session_id"] = session_id
    return budget


def _build_temperature_budget(session_id: str, instrument: dict, master: dict) -> dict:
    """Build the uncertainty budget for a Temperature session.

    Requires instruments.instrument_subtype to be one of 'TCK', 'RTD',
    'DTI', 'DryBlock' — dispatches which components apply (TCK alone needs
    wire_homogeneity_value). Uses whichever repeatability test was most
    recently created for this session if multiple setpoints exist; a
    session covering multiple setpoints would need one budget calculated
    per setpoint, which the current single-budget-per-session
    uncertainty_budgets table doesn't yet support — flagged here rather
    than silently picking one arbitrarily.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        dict: Uncertainty budget fields with session_id included.

    Raises:
        ValueError: If instrument_subtype is not set or not recognized, if
            no repeatability test data exists for this session, if more
            than one setpoint was tested in this session (not yet
            supported — see note above), or if any required field
            (including the master's uncertainty_u/accuracy) is missing.
    """
    instrument_subtype = instrument.get("instrument_subtype")
    if not instrument_subtype:
        raise ValueError(
            f"instruments.instrument_subtype is not set for instrument "
            f"{instrument.get('id')}. Required for Temperature — must be one "
            f"of 'TCK', 'RTD', 'DTI', 'DryBlock'."
        )

    repeatability_tests = database.get_temperature_repeatability_tests(session_id)
    if not repeatability_tests:
        raise ValueError(
            f"No repeatability test data found for session {session_id}. "
            f"Enter temperature test readings before calculating the uncertainty budget."
        )
    if len(repeatability_tests) > 1:
        raise ValueError(
            f"Session {session_id} has {len(repeatability_tests)} temperature "
            f"setpoints tested, but calculating a budget for more than one "
            f"setpoint per session is not yet supported — each setpoint needs "
            f"its own uncertainty budget, and uncertainty_budgets currently "
            f"only supports one row per session_id."
        )

    test = repeatability_tests[0]
    readings_key = "temperature_repeatability_readings"
    reading_values = [r["reading_value"] for r in test.get(readings_key, [])]
    if len(reading_values) != 3:
        raise ValueError(
            f"Repeatability test for setpoint '{test.get('setpoint_label')}' has "
            f"{len(reading_values)} of 3 required readings."
        )

    _require_master_field(master, "uncertainty_u")
    _require_master_field(master, "accuracy")
    _require_master_field(master, "claimed_cmc")

    if instrument_subtype == "TCK" and test.get("wire_homogeneity_value") is None:
        raise ValueError(
            f"wire_homogeneity_value is required for TCK (thermocouple) instruments "
            f"but is not set on the repeatability test for setpoint "
            f"'{test.get('setpoint_label')}'."
        )

    budget = ce.build_temperature_uncertainty_budget(
        instrument_subtype=instrument_subtype,
        repeated_readings=reading_values,
        master_uncertainty=master["uncertainty_u"],
        master_accuracy=master["accuracy"],
        drift_standard_uncertainty=test.get("drift_standard_uncertainty"),
        resolution=instrument["resolution"],
        hysteresis_value=test.get("hysteresis_value"),
        bath_stability_value=test.get("bath_stability_value"),
        bath_uniformity_value=test.get("bath_uniformity_value"),
        cmc=master["claimed_cmc"],
        wire_homogeneity_value=test.get("wire_homogeneity_value"),
    )
    budget["session_id"] = session_id
    return budget


def _require_master_field(master: dict, field_name: str):
    """Validate that a required numeric field on a master instrument record
    is actually present and not None.

    Args:
        master: The master instrument record dict.
        field_name: The field name to check.

    Raises:
        ValueError: If the field is missing or None — this is the guard
            against the "TBA" placeholder problem: if Charkha's numbers
            haven't been seeded yet, this fails loudly and specifically
            rather than letting a calculation silently proceed with bad data.
    """
    if master.get(field_name) is None:
        raise ValueError(
            f"master_instruments.{field_name} is not set for master instrument "
            f"'{master.get('name', master.get('id'))}'. This field is required "
            f"to calculate an uncertainty budget — it cannot be a placeholder "
            f"value (e.g. still 'TBA' in the source data)."
        )