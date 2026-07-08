"""formula_manager.py

Loads the per-category formula definition JSON files (formulas/*.json) and
orchestrates building an uncertainty budget for a session by gathering the
right data from the database and dispatching to the correct
calculation_engine functions for that instrument_type.

build_uncertainty_budget ALWAYS returns a LIST of budget dicts, even for
Pressure and Weighing (which will always have exactly one item). This is
a deliberate consistency choice: Temperature (one budget per setpoint) and
Electrical (one budget per function-type/range) both genuinely need
multiple budgets per session, and rather than have some categories return
a dict and others a list, every category returns a list. Callers (main.py,
validation.py, reporting.py) handle "a list of 1" and "a list of N" the
same way.

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


def build_uncertainty_budget(session_id: str) -> list[dict]:
    """Build the full uncertainty budget(s) for a calibration session.

    Gathers the instrument, session, master instrument, and readings data
    needed, then dispatches to the correct calculation_engine functions
    based on the instrument's type.

    ALWAYS returns a list, even for Pressure/Weighing which will always
    have exactly one item — see this module's docstring for why.

    Args:
        session_id: UUID of the calibration session to calculate for.

    Returns:
        list[dict]: One or more uncertainty budget dicts, each matching
            UncertaintyBudgetCreate, with session_id (and, for Temperature/
            Electrical, temperature_test_id/electrical_test_id) included —
            ready to pass directly to database.insert_uncertainty_budget,
            one at a time.

    Raises:
        ValueError: If the session, instrument, or master instrument can't
            be found, if the master instrument is missing required numeric
            fields (uncertainty_u, accuracy, claimed_cmc — the "TBA" fields
            flagged when the reference workbook came back partially filled),
            or if required test data is incomplete.
        NotImplementedError: If instrument_type is unrecognized.
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
        # Unchanged internally - wrapped in a list for contract consistency.
        # temperature_test_id/electrical_test_id are irrelevant to this
        # category, so both stay None.
        budget = _build_pressure_budget(session_id, instrument, master)
        budget["temperature_test_id"] = None
        budget["electrical_test_id"] = None
        return [budget]
    elif instrument_type == "Weighing":
        budget = _build_weighing_budget(session_id, instrument, master)
        budget["temperature_test_id"] = None
        budget["electrical_test_id"] = None
        return [budget]
    elif instrument_type == "Temperature":
        return _build_temperature_budgets(session_id, instrument, master)
    elif instrument_type == "Electrical":
        return _build_electrical_budgets(session_id, instrument, master)
    else:
        raise ValueError(f"Unknown instrument_type: '{instrument_type}'.")


def _build_pressure_budget(session_id: str, instrument: dict, master: dict) -> dict:
    """Build the uncertainty budget for a Pressure session.

    CMC is looked up from cmc_bands by the highest nominal_value tested,
    not taken from master_instruments.claimed_cmc — see
    calculation_engine.build_pressure_uncertainty_budget's docstring for
    why this changed after extracting real range-dependent CMC data from
    the supervisor's CMC_CALCULATION_-PRESSURE-_2023.xls file.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        dict: Uncertainty budget fields with session_id included.

    Raises:
        ValueError: If readings are missing, if the master instrument is
            missing uncertainty_u or accuracy (still marked "TBA" in the
            reference workbook for most instruments as of the last
            check), or if no cmc_bands entry covers the tested range.
    """
    readings = database.get_readings(session_id)
    if not readings:
        raise ValueError(
            f"No readings found for session {session_id}. Enter calibration "
            f"readings before calculating the uncertainty budget."
        )

    _require_master_field(master, "uncertainty_u")
    _require_master_field(master, "accuracy")

    cmc_bands_response = database.supabase.table("cmc_bands").select("*").eq(
        "instrument_type", "Pressure"
    ).execute()
    cmc_bands = cmc_bands_response.data
    if not cmc_bands:
        raise ValueError(
            "cmc_bands table has no rows for instrument_type='Pressure'. "
            "Seed this table before calculating pressure uncertainty budgets."
        )

    budget = ce.build_pressure_uncertainty_budget(
        readings=readings,
        master_uncertainty=master["uncertainty_u"],
        master_accuracy=master["accuracy"],
        resolution=instrument["resolution"],
        cmc_bands=cmc_bands,
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


def _build_temperature_budgets(session_id: str, instrument: dict, master: dict) -> list[dict]:
    """Build one uncertainty budget per Temperature setpoint tested.

    Requires instruments.instrument_subtype to be one of 'TCK', 'RTD',
    'DTI', 'DryBlock' — dispatches which components apply (TCK alone needs
    wire_homogeneity_value). Previously this rejected any session with
    more than one setpoint tested (uncertainty_budgets only supported one
    row per session_id) — now that uncertainty_budgets.temperature_test_id
    exists, every setpoint gets its own budget row instead.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        list[dict]: One uncertainty budget dict per setpoint tested, each
            tagged with temperature_test_id identifying which setpoint it's
            for. electrical_test_id is None on every item.

    Raises:
        ValueError: If instrument_subtype is not set or not recognized, if
            no repeatability test data exists for this session, or if any
            required field (including the master's uncertainty_u/accuracy,
            or any individual setpoint's readings/wire_homogeneity_value)
            is missing.
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

    _require_master_field(master, "uncertainty_u")
    _require_master_field(master, "accuracy")
    _require_master_field(master, "claimed_cmc")

    budgets = []
    for test in repeatability_tests:
        readings_key = "temperature_repeatability_readings"
        reading_values = [r["reading_value"] for r in test.get(readings_key, [])]
        if len(reading_values) != 3:
            raise ValueError(
                f"Repeatability test for setpoint '{test.get('setpoint_label')}' has "
                f"{len(reading_values)} of 3 required readings."
            )

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
        budget["temperature_test_id"] = test["id"]
        budget["electrical_test_id"] = None
        budgets.append(budget)

    return budgets


def _build_electrical_budgets(session_id: str, instrument: dict, master: dict) -> list[dict]:
    """Build one uncertainty budget per Electrical function-type/range tested.

    A single Electrical instrument (e.g. one multifunction calibrator) is
    typically tested across several function types (DCV, ACV, DCA, ...)
    and several ranges within each, all in one calibration session — see
    Eletrical_CMC_-_Lab___Site_-_2023.xls's 11 sheets, all for the same
    physical instrument. function_type and range_label live on each
    electrical_tests row rather than on the instrument itself, since one
    instrument covers many of both within a single session.

    Args:
        session_id: UUID of the calibration session.
        instrument: The UUC instrument record.
        master: The master instrument record.

    Returns:
        list[dict]: One uncertainty budget dict per function-type/range
            tested, each tagged with electrical_test_id identifying which
            one it's for. temperature_test_id is None on every item.

    Raises:
        ValueError: If no Electrical test data exists for this session, if
            any individual test's readings are missing, or if any test's
            function_type isn't one of the 11 recognized types (see
            calculation_engine.build_electrical_uncertainty_budget).

    Note:
        cmc defaults to 0.0 for every test — Master_Instrument_Details.xlsx
        confirms all 4 real Electrical master instruments still have
        claimed_cmc marked "TBA" (same blocker as Pressure), so there is
        no real value to require yet. Revisit _require_master_field for
        claimed_cmc once real numbers exist, matching Pressure/Temperature's
        pattern.
    """
    electrical_tests = database.get_electrical_tests(session_id)
    if not electrical_tests:
        raise ValueError(
            f"No Electrical test data found for session {session_id}. "
            f"Enter Electrical test readings before calculating the uncertainty budget."
        )

    budgets = []
    for test in electrical_tests:
        readings_key = "electrical_readings"
        reading_values = [r["reading_value"] for r in test.get(readings_key, [])]
        if not reading_values:
            raise ValueError(
                f"No readings found for Electrical test '{test.get('function_type')}' "
                f"range '{test.get('range_label')}'."
            )

        budget = ce.build_electrical_uncertainty_budget(
            function_type=test["function_type"],
            readings=reading_values,
            cert_uncertainty_limit=test.get("cert_uncertainty_limit"),
            calibrator_accuracy_limit=test.get("calibrator_accuracy_limit"),
            resolution=test.get("resolution"),
            thermo_electric_limit=test.get("thermo_electric_limit"),
            coil_accuracy_limit=test.get("coil_accuracy_limit"),
            cmc=master.get("claimed_cmc") or 0.0,
        )
        budget["session_id"] = session_id
        budget["temperature_test_id"] = None
        budget["electrical_test_id"] = test["id"]
        # type_a_value maps to Electrical's u_b1-u_b4 field names, not
        # Pressure/Weighing/Temperature's u_std/u_res/etc - the budget
        # dict from build_electrical_uncertainty_budget already uses the
        # right keys (u_b1..u_b4) directly, matching UncertaintyBudgetCreate.
        budgets.append(budget)

    return budgets


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