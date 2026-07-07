"""calculation_engine.py

Implements the GUM-compliant uncertainty budget calculations for calibration
sessions. Built out for Pressure and Weighing (confirmed real formula files,
see formulas/pressure.json and formulas/weighing.json), and Temperature
(see formulas/temperature.json and calculate_type_a_temperature onward -
Temperature currently supports one setpoint per session only, see
formula_manager.py's _build_temperature_budget). Electrical functions are
not yet implemented — waiting on 11 function types' worth of formulas.

Function order and naming follows the original project roadmap:
    calculate_type_a, calculate_u_std, calculate_u_res, calculate_u_hys,
    calculate_u_zero, calculate_u_temp, calculate_u_head (placeholder),
    calculate_combined_uncertainty, calculate_expanded_uncertainty,
    calculate_final_applied_uncertainty

Pressure uses these directly. Weighing's procedure doesn't map cleanly onto
the same component names (no u_temp/u_head, and its Type A/Type B sources
are structurally different — see formulas/weighing.json's notes field) so
it has its own parallel set of functions rather than being forced into the
Pressure-shaped ones.
"""

import math
import statistics


# ── Shared helpers ────────────────────────────────────────────────────────

def root_sum_square(*components: float) -> float:
    """Combine uncertainty components via root sum of squares.

    Args:
        *components: Any number of standard uncertainty values to combine.
            None values are treated as 0 (component not applicable).

    Returns:
        float: The combined standard uncertainty.
    """
    return math.sqrt(sum((c or 0.0) ** 2 for c in components))


# ── Pressure (and, structurally, Temperature/Electrical once their files
#    arrive — this flat six-component shape is expected to generalize) ────

def calculate_type_a(readings: list[dict]) -> float:
    """Calculate the Type A uncertainty as the standard deviation of the
    mean, across repeated mean-error readings.

    GUM-correct: this is the *standard deviation of the mean*
    (s / sqrt(n)), not the raw sample standard deviation - matches
    calculate_type_a_temperature's convention. Previously this returned
    stdev(mean_errors) with no divisor, which overestimates Type A
    uncertainty by a factor of sqrt(n). Caught via an external code
    audit and verified against calculate_type_a_temperature (which
    already divided correctly) before fixing - this changes the actual
    numeric result of every Pressure uncertainty calculation, not just
    the code, so any previously-reviewed Pressure certificate numbers
    will differ (smaller, correctly) after this fix.

    Args:
        readings: List of reading dicts, each with a 'mean_error' key.

    Returns:
        float: stdev(mean_errors) / sqrt(n). Returns 0.0 if fewer than 2
            readings are provided (stdev is undefined for a single point).

    Raises:
        ValueError: If readings is empty.
    """
    if not readings:
        raise ValueError("Cannot calculate Type A uncertainty from zero readings.")
    mean_errors = [r["mean_error"] for r in readings]
    if len(mean_errors) < 2:
        return 0.0
    return statistics.stdev(mean_errors) / math.sqrt(len(mean_errors))


def calculate_u_std(master_uncertainty: float, coverage_factor: float = 2.0) -> float:
    """Calculate the standard uncertainty contribution from the master
    instrument's own certificate (Ub1).

    Args:
        master_uncertainty: The uncertainty value stated on the master
            instrument's calibration certificate (master_instruments.uncertainty_u).
        coverage_factor: The coverage factor the master's uncertainty was
            expanded with (typically k=2, normal distribution).

    Returns:
        float: Standard uncertainty (master_uncertainty / coverage_factor).

    Raises:
        ValueError: If master_uncertainty is None.
    """
    if master_uncertainty is None:
        raise ValueError(
            "master_instruments.uncertainty_u is not set for the master instrument "
            "linked to this session. This field is required to calculate u_std."
        )
    return master_uncertainty / coverage_factor


def calculate_u_std_accuracy(master_accuracy: float, coverage_factor: float = 2.0) -> float:
    """Calculate the standard uncertainty contribution from the master
    instrument's stated accuracy (Ub2). Specific to the Pressure formula
    file's six-component model — not part of the original four-category
    plan, included here because the real source file uses it.

    Args:
        master_accuracy: The accuracy value from the master instrument record.
        coverage_factor: Coverage factor to divide by (normal distribution, k=2).

    Returns:
        float: Standard uncertainty (master_accuracy / coverage_factor).

    Raises:
        ValueError: If master_accuracy is None.
    """
    if master_accuracy is None:
        raise ValueError(
            "master_instruments.accuracy is not set for the master instrument "
            "linked to this session. This field is required to calculate u_std_accuracy."
        )
    return master_accuracy / coverage_factor


def calculate_u_res(resolution: float) -> float:
    """Calculate the resolution uncertainty (Ub3), rectangular distribution.

    Args:
        resolution: The instrument's resolution (instruments.resolution).

    Returns:
        float: Standard uncertainty (resolution / 2), i.e. the rectangular
            half-width. Note: the source Excel file does not divide by
            sqrt(3) for this specific component — reproduced faithfully as
            found; confirm with Charkha if this differs from standard GUM
            practice intentionally or by omission.

    Raises:
        ValueError: If resolution is None or negative.
    """
    if resolution is None:
        raise ValueError("instruments.resolution is required to calculate u_res.")
    if resolution < 0:
        raise ValueError(f"resolution must be non-negative, got {resolution}.")
    return resolution / 2


def calculate_u_zero(readings: list[dict]) -> float:
    """Calculate the zero error uncertainty (Ub4): the signed error at the
    nominal zero calibration point.

    Args:
        readings: List of reading dicts, each with 'nominal_value' and
            'mean_error' keys.

    Returns:
        float: The mean_error at the reading whose nominal_value is 0.
            Returns 0.0 if no zero point is found among the readings.
    """
    zero_readings = [r for r in readings if r.get("nominal_value") == 0]
    if not zero_readings:
        return 0.0
    return abs(zero_readings[0]["mean_error"])


def calculate_u_repeatability(readings: list[dict]) -> float:
    """Calculate the repeatability uncertainty (Ub5): standard deviation of
    successive differences between consecutive readings' mean errors.

    This is distinct from calculate_type_a — the source file computes both
    Ua1 (Type A, stdev of mean errors) and Ub5 (Repeatability, stdev of
    successive differences) as separate components, despite both being
    repeatability-flavored. Reproduced as two separate functions to match.

    Args:
        readings: List of reading dicts ordered by point_number, each with
            a 'mean_error' key.

    Returns:
        float: Standard deviation of successive differences. Returns 0.0
            if fewer than 3 readings (need at least 2 differences to get
            a stdev).
    """
    if len(readings) < 3:
        return 0.0
    mean_errors = [r["mean_error"] for r in readings]
    successive_diffs = [abs(mean_errors[i] - mean_errors[i - 1]) for i in range(1, len(mean_errors))]
    return statistics.stdev(successive_diffs)


def calculate_u_hys(readings: list[dict]) -> float:
    """Calculate the hysteresis uncertainty (Ub6), rectangular distribution.

    Args:
        readings: List of reading dicts, each with a 'hysteresis' key
            (absolute difference between ascending and descending
            measurements at that point).

    Returns:
        float: Standard uncertainty (max hysteresis across all points / 2).
            Returns 0.0 if no readings have a hysteresis value.
    """
    hysteresis_values = [r["hysteresis"] for r in readings if r.get("hysteresis") is not None]
    if not hysteresis_values:
        return 0.0
    return max(hysteresis_values) / 2


def calculate_u_temp(temperature_coefficient: float, ambient_deviation: float) -> float:
    """Calculate the temperature influence uncertainty, rectangular
    distribution. NOT observed in the real Pressure source file (no u_temp
    component was present) — implemented per the original roadmap spec in
    case a different pressure scope (e.g. liquid medium) or another
    category needs it. Confirm applicability with Charkha before using.

    Args:
        temperature_coefficient: The instrument's temperature coefficient
            (units per degree C, from instrument spec).
        ambient_deviation: Deviation of ambient temperature from the
            reference 20 degrees C.

    Returns:
        float: Standard uncertainty (rectangular half-width / sqrt(3)).
    """
    half_width = abs(temperature_coefficient * ambient_deviation)
    return half_width / math.sqrt(3)


def calculate_u_head(*args, **kwargs) -> float:
    """Calculate the medium head correction uncertainty. Pressure
    instruments with liquid medium only. Placeholder per the original
    roadmap — not observed in the real Pressure source file (which covers
    pneumatic/hydraulic gauge scopes, not liquid-column head correction).

    Raises:
        NotImplementedError: Always. Formula not yet confirmed with supervisor.
    """
    raise NotImplementedError(
        "u_head (medium head correction) formula not yet confirmed with supervisor. "
        "Not present in the real Pressure source file received so far — only "
        "relevant if a liquid-medium pressure scope is added."
    )


def calculate_combined_uncertainty(*components: float) -> float:
    """Calculate the combined standard uncertainty as the root sum of
    squares of all applicable components (including Type A).

    Args:
        *components: Standard uncertainty values to combine.

    Returns:
        float: The combined standard uncertainty (Uc).
    """
    return root_sum_square(*components)


def calculate_expanded_uncertainty(combined_uncertainty: float, k: float = 2.0) -> float:
    """Calculate the expanded uncertainty.

    Args:
        combined_uncertainty: The combined standard uncertainty (Uc).
        k: Coverage factor (default 2.0, ~95% confidence for normal distribution).

    Returns:
        float: Expanded uncertainty (Uc * k).
    """
    return combined_uncertainty * k


def calculate_final_applied_uncertainty(expanded_uncertainty: float, cmc: float) -> float:
    """Calculate the final applied uncertainty as the larger of the
    expanded uncertainty and the claimed CMC.

    Args:
        expanded_uncertainty: The expanded uncertainty (U).
        cmc: The claimed measurement capability (master_instruments.claimed_cmc).

    Returns:
        float: The larger of expanded_uncertainty and cmc.
    """
    return max(expanded_uncertainty, cmc or 0.0)


def build_pressure_uncertainty_budget(
    readings: list[dict],
    master_uncertainty: float,
    master_accuracy: float,
    resolution: float,
    cmc_bands: list[dict],
) -> dict:
    """Orchestrate the full Pressure uncertainty budget calculation.

    CMC is looked up from cmc_bands by the highest nominal_value tested
    across the session's readings, rather than taken as a flat
    master_instruments.claimed_cmc value. This matches how Weighing
    already works, and was changed here after extracting real data from
    the supervisor's CMC_CALCULATION_-PRESSURE-_2023.xls file, which shows
    CMC is genuinely range-dependent for Pressure too (e.g. ~0.0106 bar
    near 1 bar vs ~11.9 bar near 2500 bar) - a flat per-instrument number
    can't represent that.

    Args:
        readings: List of reading dicts for the session (point_number,
            nominal_value, mean_error, hysteresis).
        master_uncertainty: master_instruments.uncertainty_u for the
            master instrument used.
        master_accuracy: master_instruments.accuracy for the master
            instrument used.
        resolution: instruments.resolution for the UUC.
        cmc_bands: All cmc_bands records for instrument_type='Pressure'.

    Returns:
        dict: All uncertainty budget fields, matching the shape expected
            by UncertaintyBudgetCreate — ready to pass to
            database.insert_uncertainty_budget after adding session_id.

    Raises:
        ValueError: If readings is empty, required master instrument
            fields are missing (propagated from the individual calculate_*
            functions), or no cmc_bands entry covers the tested range.
    """
    type_a = calculate_type_a(readings)
    u_std = calculate_u_std(master_uncertainty)
    u_std_accuracy = calculate_u_std_accuracy(master_accuracy)
    u_res = calculate_u_res(resolution)
    u_zero = calculate_u_zero(readings)
    u_repeatability = calculate_u_repeatability(readings)
    u_hys = calculate_u_hys(readings)

    combined = calculate_combined_uncertainty(
        type_a, u_std, u_std_accuracy, u_res, u_zero, u_repeatability, u_hys
    )
    expanded = calculate_expanded_uncertainty(combined, k=2.0)

    highest_nominal_value = max(abs(r["nominal_value"]) for r in readings)
    cmc_band = lookup_cmc_band(cmc_bands, highest_nominal_value)
    if cmc_band is None:
        raise ValueError(
            f"No CMC band found covering nominal value {highest_nominal_value} "
            f"for instrument_type='Pressure'. Check that cmc_bands has been "
            f"seeded with the correct ranges."
        )
    cmc = cmc_band["cmc_value"]

    final_applied = calculate_final_applied_uncertainty(expanded, cmc)

    return {
        "type_a_value": type_a,
        "u_std": u_std,
        "u_std_accuracy": u_std_accuracy,
        "u_res": u_res,
        "u_hys": u_hys,
        "u_zero": u_zero,
        "u_repeatability": u_repeatability,
        "cmc": cmc,
        "combined_uncertainty": combined,
        "expanded_uncertainty": expanded,
        "k_value": 2.0,
        "final_applied_uncertainty": final_applied,
    }


# ── Weighing ──────────────────────────────────────────────────────────────
# Structurally different from Pressure: Type A is derived from three
# separate repeatability tests (not a single readings list), and Type B
# sources depend on the off-center test's own output rather than being
# independent coefficients. See formulas/weighing.json for the full
# annotated breakdown, including the eccentric-loading formula quirk.

def calculate_type_a_weighing(repeatability_tests: list[dict]) -> float:
    """Calculate Type A uncertainty for weighing: the worst of the three
    repeatability tests' standard deviations, divided by sqrt(n_readings).

    Args:
        repeatability_tests: List of 3 dicts, one per test_point
            (near_zero, fifty_percent, hundred_percent), each with a
            'readings' key containing 10 dicts with 'reading_before',
            'reading_with_load', 'reading_after'.

    Returns:
        float: MAX(stdev of the three tests' mean errors) / sqrt(10).

    Raises:
        ValueError: If fewer than 3 test points are supplied, or any test
            point has fewer than 2 readings (stdev undefined).
    """
    if len(repeatability_tests) < 3:
        raise ValueError(
            f"Weighing repeatability requires all 3 test points (near_zero, "
            f"fifty_percent, hundred_percent), got {len(repeatability_tests)}."
        )

    stdevs = []
    n_readings = None
    for test in repeatability_tests:
        readings = test["readings"]
        if len(readings) < 2:
            raise ValueError(
                f"Repeatability test '{test.get('test_point')}' has fewer than "
                f"2 readings; cannot compute standard deviation."
            )
        n_readings = len(readings)
        mean_errors = [
            r["reading_with_load"] - (r["reading_before"] + r["reading_after"]) / 2
            for r in readings
        ]
        stdevs.append(statistics.stdev(mean_errors))

    return max(stdevs) / math.sqrt(n_readings)


def calculate_u_std_weights(standard_weights_uncertainty: float, coverage_factor: float = 2.0) -> float:
    """Calculate the standard uncertainty contribution from the reference
    standard weights used (UM).

    Args:
        standard_weights_uncertainty: Combined cert uncertainty of the
            standard weight combination used
            (weighing_repeatability_tests.standard_weights_uncertainty).
        coverage_factor: Coverage factor the standard's uncertainty was
            expanded with (typically k=2).

    Returns:
        float: Standard uncertainty (value / coverage_factor).

    Raises:
        ValueError: If standard_weights_uncertainty is None.
    """
    if standard_weights_uncertainty is None:
        raise ValueError(
            "standard_weights_uncertainty is required to calculate u_std_weights. "
            "This should be entered per repeatability test point from the standard "
            "weight combination's own calibration certificate."
        )
    return standard_weights_uncertainty / coverage_factor


def calculate_u_eccentric(off_center_readings: list[dict]) -> float:
    """Calculate the eccentric/off-center loading uncertainty (UL).

    Reproduces the source file's formula exactly: (max - min) / 2 * SQRT(3)
    immediately divided by SQRT(3) in the next cell, which mathematically
    cancels to (max - min) / 2. Implemented directly in the cancelled form
    rather than literally replaying the redundant multiply/divide, since
    the numeric result is identical either way and this is clearer to read.

    Args:
        off_center_readings: List of 5 dicts (one per position: center,
            front, back, left, right), each with 'reading_before',
            'reading_with_load', 'reading_after'.

    Returns:
        float: (max_error - min_error) / 2.

    Raises:
        ValueError: If fewer than 5 position readings are supplied.
    """
    if len(off_center_readings) < 5:
        raise ValueError(
            f"Off-center test requires all 5 positions (center, front, back, "
            f"left, right), got {len(off_center_readings)}."
        )
    errors = [
        r["reading_with_load"] - (r["reading_before"] + r["reading_after"]) / 2
        for r in off_center_readings
    ]
    return (max(errors) - min(errors)) / 2


def calculate_u_resolution_weighing(resolution: float) -> float:
    """Calculate the balance resolution uncertainty (UR) for weighing.

    Unlike Pressure's calculate_u_res, this one DOES divide by sqrt(3) per
    the source file's formula — the two categories' resolution formulas
    are not the same, reproduced faithfully rather than unified.

    Args:
        resolution: The instrument's resolution (instruments.resolution).

    Returns:
        float: Standard uncertainty ((resolution / 2) / sqrt(3)).

    Raises:
        ValueError: If resolution is None or negative.
    """
    if resolution is None:
        raise ValueError("instruments.resolution is required to calculate u_resolution_weighing.")
    if resolution < 0:
        raise ValueError(f"resolution must be non-negative, got {resolution}.")
    return (resolution / 2) / math.sqrt(3)


def lookup_cmc_band(cmc_bands: list[dict], load_value: float) -> dict | None:
    """Find the CMC band applicable to a given load value.

    Args:
        cmc_bands: List of cmc_bands records (min_value, max_value, cmc_value, cmc_unit).
        load_value: The load value to look up, in the same unit as the
            band boundaries (grams, per the source file's convention).

    Returns:
        dict | None: The matching band, or None if no band covers this load_value.
    """
    for band in cmc_bands:
        if band["min_value"] <= load_value < band["max_value"]:
            return band
    return None


def build_weighing_uncertainty_budget(
    repeatability_tests: list[dict],
    off_center_readings: list[dict],
    resolution: float,
    load_value_g: float,
    cmc_bands: list[dict],
) -> dict:
    """Orchestrate the full Weighing uncertainty budget calculation.

    Args:
        repeatability_tests: 3 test point dicts, each with 'readings' (10
            dicts) and 'standard_weights_uncertainty'.
        off_center_readings: 5 position dicts for the eccentricity test.
        resolution: instruments.resolution for the UUC.
        load_value_g: The load value (in grams) to look up the applicable
            CMC band for.
        cmc_bands: All cmc_bands records for instrument_type='Weighing'.

    Returns:
        dict: All uncertainty budget fields, matching the shape expected
            by UncertaintyBudgetCreate (using u_std_weights and
            u_eccentric rather than u_std/u_hys) — ready to pass to
            database.insert_uncertainty_budget after adding session_id.

    Raises:
        ValueError: If any required test data is missing or incomplete
            (propagated from the individual calculate_* functions), or if
            no CMC band covers the given load_value_g.
    """
    type_a = calculate_type_a_weighing(repeatability_tests)

    # Use the standard_weights_uncertainty from the highest-load test point,
    # matching the source file's pattern of the uncertainty accumulating as
    # load increases toward full range.
    hundred_percent_test = next(
        (t for t in repeatability_tests if t.get("test_point") == "hundred_percent"), None
    )
    if hundred_percent_test is None:
        raise ValueError("hundred_percent repeatability test not found among repeatability_tests.")

    u_std_weights = calculate_u_std_weights(hundred_percent_test.get("standard_weights_uncertainty"))
    u_eccentric = calculate_u_eccentric(off_center_readings)
    u_resolution = calculate_u_resolution_weighing(resolution)

    combined = calculate_combined_uncertainty(type_a, u_std_weights, u_eccentric, u_resolution)
    expanded_kg = calculate_expanded_uncertainty(combined, k=2.0)
    expanded_g = expanded_kg * 1000

    cmc_band = lookup_cmc_band(cmc_bands, load_value_g)
    if cmc_band is None:
        raise ValueError(
            f"No CMC band found covering load value {load_value_g}g for instrument_type='Weighing'. "
            f"Check that cmc_bands has been seeded with the correct ranges."
        )
    cmc_g = cmc_band["cmc_value"] if cmc_band["cmc_unit"] == "g" else cmc_band["cmc_value"] / 1000

    final_applied = calculate_final_applied_uncertainty(expanded_g, cmc_g)

    return {
        "type_a_value": type_a,
        "u_std_weights": u_std_weights,
        "u_eccentric": u_eccentric,
        "u_res": u_resolution,
        "cmc": cmc_g,
        "combined_uncertainty": combined,
        "expanded_uncertainty": expanded_g,
        "k_value": 2.0,
        "final_applied_uncertainty": final_applied,
    }


# ── Temperature ───────────────────────────────────────────────────────────
# Four sub-types (TCK, RTD, DTI, DryBlock) share Ua + Ub1-Ub7; TCK alone has
# an additional Ub8 (wire homogeneity). Every formula below was verified
# against the real source files' own computed "Standard Uncertainty" column
# before being implemented - see formulas/temperature.json's
# anomalies_found for two genuine discrepancies in the source data
# (Ub3's drift value, and TCK's own buggy Ub7 result) that are NOT
# reproduced here; the GUM-correct formulas are used instead.

def calculate_type_a_temperature(readings: list[float], n_readings: int = 3) -> float:
    """Calculate Type A uncertainty for Temperature: standard deviation of
    repeated readings at a single setpoint, divided by sqrt(n).

    Args:
        readings: List of repeated reading values at one setpoint
            (typically 3, per the real source files).
        n_readings: Number of readings taken (used as the divisor's base;
            defaults to 3 matching all four source files).

    Returns:
        float: stdev(readings) / sqrt(n_readings). Returns 0.0 if fewer
            than 2 readings are provided.

    Raises:
        ValueError: If readings is empty.
    """
    if not readings:
        raise ValueError("Cannot calculate Type A uncertainty from zero readings.")
    if len(readings) < 2:
        return 0.0
    return statistics.stdev(readings) / math.sqrt(n_readings)


def calculate_u_std_temperature(master_uncertainty: float, coverage_factor: float = 2.0) -> float:
    """Calculate the standard uncertainty contribution from the master
    instrument's own certificate (Ub1). Same formula as Pressure's
    calculate_u_std; kept as a separate named function for clarity and
    in case Temperature's coverage factor convention ever diverges.

    Args:
        master_uncertainty: master_instruments.uncertainty_u.
        coverage_factor: Coverage factor the master's uncertainty was
            expanded with (typically k=2).

    Returns:
        float: Standard uncertainty (master_uncertainty / coverage_factor).

    Raises:
        ValueError: If master_uncertainty is None.
    """
    if master_uncertainty is None:
        raise ValueError(
            "master_instruments.uncertainty_u is not set for the master instrument "
            "linked to this session. Required to calculate u_std."
        )
    return master_uncertainty / coverage_factor


def calculate_u_std_accuracy_temperature(master_accuracy: float) -> float:
    """Calculate the standard uncertainty contribution from the master
    instrument's accuracy (Ub2), rectangular distribution.

    Args:
        master_accuracy: master_instruments.accuracy.

    Returns:
        float: Standard uncertainty (master_accuracy / sqrt(3)).

    Raises:
        ValueError: If master_accuracy is None.
    """
    if master_accuracy is None:
        raise ValueError(
            "master_instruments.accuracy is not set for the master instrument "
            "linked to this session. Required to calculate u_std_accuracy."
        )
    return master_accuracy / math.sqrt(3)


def calculate_u_drift(drift_standard_uncertainty: float) -> float:
    """Return the drift uncertainty contribution (Ub3) as a direct
    pass-through of an already-known standard uncertainty value.

    Deliberately NOT derived from a raw "drift spec value" via a
    value/divisor formula in-app. Verification against the real source
    files found the displayed Value column for this component doesn't
    reliably match its own computed result across TCK/RTD/DTI/DryBlock
    (e.g. TCK/RTD/DryBlock all show Value=0.017 but a computed result
    that only matches if the real input were 0.007) - the raw value is
    not trustworthy enough to re-derive from. This value should be
    entered directly (temperature_repeatability_tests.drift_standard_uncertainty),
    the same pattern used for weighing's standard_weights_uncertainty.

    Args:
        drift_standard_uncertainty: The already-computed drift standard
            uncertainty, sourced from the supervisor's own worksheet or
            comparison against the instrument's previous certificate.

    Returns:
        float: The value passed in, unchanged.

    Raises:
        ValueError: If drift_standard_uncertainty is None.
    """
    if drift_standard_uncertainty is None:
        raise ValueError(
            "drift_standard_uncertainty is not set. This must be entered directly "
            "(not derived from a raw spec value) - see this function's docstring "
            "for why the source files' raw Value column isn't reliable for this "
            "component."
        )
    return drift_standard_uncertainty


def calculate_u_res_temperature(resolution: float) -> float:
    """Calculate the resolution uncertainty (Ub4), rectangular distribution.

    Args:
        resolution: instruments.resolution.

    Returns:
        float: Standard uncertainty ((resolution / 2) / sqrt(3)).

    Raises:
        ValueError: If resolution is None or negative.
    """
    if resolution is None:
        raise ValueError("instruments.resolution is required to calculate u_res_temperature.")
    if resolution < 0:
        raise ValueError(f"resolution must be non-negative, got {resolution}.")
    return (resolution / 2) / math.sqrt(3)


def calculate_u_hys_temperature(hysteresis_value: float) -> float:
    """Calculate the hysteresis uncertainty (Ub5), rectangular distribution.

    Unlike Pressure/Weighing's hysteresis formulas, there is no /2 half-width
    step here - the raw value is divided directly by sqrt(3), and its sign
    is preserved (harmless, since combining via root-sum-square squares it
    away regardless).

    Args:
        hysteresis_value: The signed hysteresis reading.

    Returns:
        float: hysteresis_value / sqrt(3).
    """
    if hysteresis_value is None:
        return 0.0
    return hysteresis_value / math.sqrt(3)


def calculate_u_bath_stability(bath_stability_value: float) -> float:
    """Calculate the bath stability uncertainty (Ub6), rectangular distribution.

    Args:
        bath_stability_value: temperature_repeatability_tests.bath_stability_value.

    Returns:
        float: bath_stability_value / sqrt(3).

    Raises:
        ValueError: If bath_stability_value is None.
    """
    if bath_stability_value is None:
        raise ValueError("bath_stability_value is required to calculate u_bath_stability.")
    return bath_stability_value / math.sqrt(3)


def calculate_u_bath_uniformity(bath_uniformity_value: float) -> float:
    """Calculate the bath uniformity uncertainty (Ub7), rectangular
    distribution. Uses the verified value/sqrt(3) formula - NOT TCK's own
    displayed result of 0 for this component, which was confirmed to be a
    spreadsheet bug (see formulas/temperature.json's anomalies_found).

    Args:
        bath_uniformity_value: temperature_repeatability_tests.bath_uniformity_value.

    Returns:
        float: bath_uniformity_value / sqrt(3).

    Raises:
        ValueError: If bath_uniformity_value is None.
    """
    if bath_uniformity_value is None:
        raise ValueError("bath_uniformity_value is required to calculate u_bath_uniformity.")
    return bath_uniformity_value / math.sqrt(3)


def calculate_u_wire_homogeneity(wire_homogeneity_value: float) -> float:
    """Calculate the thermocouple wire homogeneity uncertainty (Ub8),
    rectangular distribution. TCK sub-type only.

    Args:
        wire_homogeneity_value: temperature_repeatability_tests.wire_homogeneity_value.

    Returns:
        float: wire_homogeneity_value / sqrt(3).

    Raises:
        ValueError: If wire_homogeneity_value is None.
    """
    if wire_homogeneity_value is None:
        raise ValueError(
            "wire_homogeneity_value is required to calculate u_wire_homogeneity "
            "for a TCK (thermocouple) instrument."
        )
    return wire_homogeneity_value / math.sqrt(3)


def build_temperature_uncertainty_budget(
    instrument_subtype: str,
    repeated_readings: list[float],
    master_uncertainty: float,
    master_accuracy: float,
    drift_standard_uncertainty: float,
    resolution: float,
    hysteresis_value: float,
    bath_stability_value: float,
    bath_uniformity_value: float,
    cmc: float,
    wire_homogeneity_value: float = None,
) -> dict:
    """Orchestrate the full Temperature uncertainty budget calculation.

    Args:
        instrument_subtype: One of 'TCK', 'RTD', 'DTI', 'DryBlock'.
        repeated_readings: The repeated readings at this setpoint (typically 3).
        master_uncertainty: master_instruments.uncertainty_u.
        master_accuracy: master_instruments.accuracy.
        drift_standard_uncertainty: Pre-computed drift figure - see
            calculate_u_drift's docstring.
        resolution: instruments.resolution.
        hysteresis_value: Signed hysteresis reading.
        bath_stability_value: Raw bath stability value.
        bath_uniformity_value: Raw bath uniformity value.
        cmc: master_instruments.claimed_cmc.
        wire_homogeneity_value: Raw wire homogeneity value. Required if
            instrument_subtype is 'TCK', ignored otherwise.

    Returns:
        dict: Uncertainty budget fields matching UncertaintyBudgetCreate,
            ready for database.insert_uncertainty_budget after adding
            session_id.

    Raises:
        ValueError: If instrument_subtype is 'TCK' and wire_homogeneity_value
            is not provided, if instrument_subtype is not one of the four
            known sub-types, or if any required field is missing
            (propagated from the individual calculate_* functions).
    """
    valid_subtypes = {"TCK", "RTD", "DTI", "DryBlock"}
    if instrument_subtype not in valid_subtypes:
        raise ValueError(
            f"Unknown instrument_subtype '{instrument_subtype}' for Temperature. "
            f"Must be one of: {sorted(valid_subtypes)}."
        )

    type_a = calculate_type_a_temperature(repeated_readings, n_readings=len(repeated_readings) or 3)
    u_std = calculate_u_std_temperature(master_uncertainty)
    u_std_accuracy = calculate_u_std_accuracy_temperature(master_accuracy)
    u_drift = calculate_u_drift(drift_standard_uncertainty)
    u_res = calculate_u_res_temperature(resolution)
    u_hys = calculate_u_hys_temperature(hysteresis_value)
    u_bath_stability = calculate_u_bath_stability(bath_stability_value)
    u_bath_uniformity = calculate_u_bath_uniformity(bath_uniformity_value)

    components = [type_a, u_std, u_std_accuracy, u_drift, u_res, u_hys, u_bath_stability, u_bath_uniformity]

    u_wire_homogeneity = None
    if instrument_subtype == "TCK":
        if wire_homogeneity_value is None:
            raise ValueError(
                "wire_homogeneity_value is required for TCK (thermocouple) instruments "
                "but was not provided."
            )
        u_wire_homogeneity = calculate_u_wire_homogeneity(wire_homogeneity_value)
        components.append(u_wire_homogeneity)

    combined = calculate_combined_uncertainty(*components)
    expanded = calculate_expanded_uncertainty(combined, k=2.0)
    final_applied = calculate_final_applied_uncertainty(expanded, cmc)

    return {
        "type_a_value": type_a,
        "u_std": u_std,
        "u_std_accuracy": u_std_accuracy,
        "u_drift": u_drift,
        "u_res": u_res,
        "u_hys": u_hys,
        "u_bath_stability": u_bath_stability,
        "u_bath_uniformity": u_bath_uniformity,
        "u_wire_homogeneity": u_wire_homogeneity,
        "cmc": cmc,
        "combined_uncertainty": combined,
        "expanded_uncertainty": expanded,
        "k_value": 2.0,
        "final_applied_uncertainty": final_applied,
    }


# ── Electrical (11 function types: DCV, ACV, DCA, ACA, Resistance, ──────────
#    Frequency, Insulation Resistance, Temperature R/S/B, Temperature
#    K/J/N/E/T, DCA (Coil), ACA (Coil) — see formulas/electrical.json.
#
#    Built from the real computed uncertainty budget tables in
#    Eletrical_CMC_-_Lab___Site_-_2023.xls and Clamp_meter_cmc_-_2023.xls,
#    cross-checked against a real issued certificate
#    (DMM_Cal_Cert_2020098677R1.xls) — not from Adi's initial formula
#    summary alone, which turned out to disagree with the real data on
#    the Type A divisor (see calculate_type_a_electrical below).
#
#    Unlike Pressure/Weighing/Temperature, none of the four Type B input
#    values (cert_uncertainty_limit, calibrator_accuracy_limit,
#    thermo_electric_limit, coil_accuracy_limit) have a confirmed mapping
#    to a real database column yet — formula_manager.py dispatch and any
#    session/instrument wiring is deliberately NOT built yet, pending that
#    schema decision. These functions are pure and independently testable
#    without a database, same rigor as everything else in this file.

def calculate_type_a_electrical(readings: list[float], extra_addend: float = 0.0) -> float:
    """Calculate the Type A uncertainty (Ua) for an Electrical function type.

    IMPORTANT DEVIATION FROM STANDARD GUM: this divides by a flat 2, NOT
    sqrt(n) as GUM theory (and Adi's original formula document) specify.
    Confirmed against the real source files' own explicit "Devisor"
    column — literally showing the value 2 for Ua, not 1.732051 (sqrt(3),
    which appears for the rectangular Type B components in the same
    table) — consistently across the DCV, ACV, and DCA (Coil) sheets.
    Reproduced faithfully as found rather than silently corrected, same
    as formulas/pressure.json's u_res anomaly. Confirm with Charkha
    whether this is an intentional lab convention or a spreadsheet error.

    Args:
        readings: List of repeated UUC reading values (typically 3).
        extra_addend: DCV-specific quirk only - the real DCV sheet adds
            thermo_electric_limit directly into the Ua estimate BEFORE
            dividing by 2, in addition to thermo_electric_limit appearing
            as its own separate Ub4 rectangular component elsewhere in
            the same budget (possible double-counting - see
            formulas/electrical.json's anomalies_found). Leave at the
            default 0.0 for every function type except DCV.

    Returns:
        float: (stdev(readings) + extra_addend) / 2. Returns
            extra_addend / 2 if fewer than 2 readings are provided
            (stdev undefined for a single point).

    Raises:
        ValueError: If readings is empty.
    """
    if not readings:
        raise ValueError("Cannot calculate Type A uncertainty from zero readings.")
    if len(readings) < 2:
        return extra_addend / 2
    return (statistics.stdev(readings) + extra_addend) / 2


def calculate_u_rectangular_from_limit(value: float) -> float:
    """Calculate a Type B uncertainty from a value that is ALREADY a
    rectangular-distribution half-width (i.e. divide only by sqrt(3),
    with no separate /2 step first).

    Used for Ub2 (Accuracy of Standard Calibrator) on every Electrical
    function type, Ub4 (Thermo Electric Voltage) on DCV, and Ub3 (Accuracy
    of Current Coil) on the two Coil function types — all three are the
    exact same formula in the real source data, just applied to a
    different named input.

    Args:
        value: The half-width limit value (e.g. calibrator's accuracy
            spec, already representing the full ± range).

    Returns:
        float: value / sqrt(3).

    Raises:
        ValueError: If value is None.
    """
    if value is None:
        raise ValueError("A limit value is required to calculate this rectangular Type B component.")
    return value / math.sqrt(3)


def calculate_u_resolution_electrical(resolution: float) -> float:
    """Calculate the UUC resolution uncertainty for Electrical (Ub3 on
    most function types, Ub4 on the two Coil types).

    Unlike Pressure's calculate_u_res (which is missing this exact
    divisor - see that function's docstring), this is the full, correct
    GUM rectangular-distribution treatment: half-width (resolution / 2),
    then divided by sqrt(3). Confirmed against the real source data,
    e.g. DCA (Coil)'s own budget table: resolution 0.1 -> (0.1/2)/sqrt(3)
    = 0.028868, matching the sheet's own computed value exactly.

    Args:
        resolution: The instrument's resolution.

    Returns:
        float: (resolution / 2) / sqrt(3).

    Raises:
        ValueError: If resolution is None or negative.
    """
    if resolution is None:
        raise ValueError("resolution is required to calculate this component.")
    if resolution < 0:
        raise ValueError(f"resolution must be non-negative, got {resolution}.")
    return (resolution / 2) / math.sqrt(3)


def build_electrical_uncertainty_budget(
    function_type: str,
    readings: list[float],
    cert_uncertainty_limit: float,
    calibrator_accuracy_limit: float,
    resolution: float,
    thermo_electric_limit: float | None = None,
    coil_accuracy_limit: float | None = None,
    cmc: float = 0.0,
    k_override: float | None = None,
) -> dict:
    """Build the full uncertainty budget for one Electrical function type.

    Dispatches on function_type to assemble the right set of Type B
    components — see formulas/electrical.json's function_types for which
    shape each of the 11 types uses. All 11 types share the same Type A
    treatment (calculate_type_a_electrical) and the same combine/expand/
    final-applied logic; they differ only in which Type B components
    apply and, for DCV, an extra Type A addend.

    Args:
        function_type: One of "DCV", "ACV", "DCA", "ACA", "Resistance",
            "Frequency", "Insulation Resistance", "Temperature (R,S,B)",
            "Temperature (K,J,N,E,T)", "DCA (Coil)", "ACA (Coil)" — must
            match formulas/electrical.json's function_types keys exactly.
        readings: List of repeated UUC reading values.
        cert_uncertainty_limit: Standard calibrator's own uncertainty (Ub1 input).
        calibrator_accuracy_limit: Standard calibrator's accuracy (Ub2 input).
        resolution: The UUC's resolution.
        thermo_electric_limit: Thermo-electric voltage limit - required
            for DCV only (used both as calculate_type_a_electrical's
            extra_addend and as an independent Ub4 component - see that
            function's docstring for the double-counting concern).
        coil_accuracy_limit: Current coil's accuracy - required for the
            two Coil function types only (used as Ub3; resolution becomes
            Ub4 for these two types instead of Ub3).
        cmc: Claimed measurement capability. Defaults to 0.0 (not yet
            wired to a real master_instruments value - see
            formulas/electrical.json's cmc_source).
        k_override: Pre-computed coverage factor for "Temperature
            (K,J,N,E,T)" only. The real source data derives this via the
            Welch-Satterthwaite equation from each component's own
            degrees of freedom, which isn't implemented here yet (would
            need a t-distribution lookup, e.g. via scipy.stats.t.ppf) -
            pass a known value if you have one from a reference
            certificate; otherwise this defaults to 2.0, which the real
            data shows is accurate to within about 0.03% for realistic
            inputs (observed real k values: 2.0005-2.0007).

    Returns:
        dict: Uncertainty budget fields (type_a_value, u_b1..u_b4 as
            applicable, combined_uncertainty, expanded_uncertainty,
            k_value, final_applied_uncertainty).

    Raises:
        ValueError: If function_type is unrecognized, or if a
            function-type-specific required input is missing (e.g.
            thermo_electric_limit for DCV).
    """
    coil_types = {"DCA (Coil)", "ACA (Coil)"}
    four_component_types = {"DCV"} | coil_types
    known_types = four_component_types | {
        "ACV", "DCA", "ACA", "Resistance", "Frequency",
        "Insulation Resistance", "Temperature (R,S,B)", "Temperature (K,J,N,E,T)",
    }
    if function_type not in known_types:
        raise ValueError(f"Unknown Electrical function_type: '{function_type}'.")

    dcv_addend = 0.0
    if function_type == "DCV":
        if thermo_electric_limit is None:
            raise ValueError("thermo_electric_limit is required for DCV but was not provided.")
        dcv_addend = thermo_electric_limit

    type_a = calculate_type_a_electrical(readings, extra_addend=dcv_addend)
    u_b1 = calculate_u_std(cert_uncertainty_limit)
    u_b2 = calculate_u_rectangular_from_limit(calibrator_accuracy_limit)

    if function_type in coil_types:
        if coil_accuracy_limit is None:
            raise ValueError(f"coil_accuracy_limit is required for {function_type} but was not provided.")
        u_b3 = calculate_u_rectangular_from_limit(coil_accuracy_limit)
        u_b4 = calculate_u_resolution_electrical(resolution)
        components = [type_a, u_b1, u_b2, u_b3, u_b4]
    elif function_type == "DCV":
        u_b3 = calculate_u_resolution_electrical(resolution)
        u_b4 = calculate_u_rectangular_from_limit(thermo_electric_limit)
        components = [type_a, u_b1, u_b2, u_b3, u_b4]
    else:
        u_b3 = calculate_u_resolution_electrical(resolution)
        u_b4 = None
        components = [type_a, u_b1, u_b2, u_b3]

    combined = calculate_combined_uncertainty(*components)

    if function_type == "Temperature (K,J,N,E,T)":
        k = k_override if k_override is not None else 2.0
    else:
        k = 2.0

    expanded = calculate_expanded_uncertainty(combined, k=k)
    final_applied = calculate_final_applied_uncertainty(expanded, cmc)

    return {
        "type_a_value": type_a,
        "u_b1": u_b1,
        "u_b2": u_b2,
        "u_b3": u_b3,
        "u_b4": u_b4,
        "cmc": cmc,
        "combined_uncertainty": combined,
        "expanded_uncertainty": expanded,
        "k_value": k,
        "final_applied_uncertainty": final_applied,
    }