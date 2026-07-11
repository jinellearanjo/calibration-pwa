"""tests/test_calculation.py

Regression tests for modules/calculation_engine.py.

This suite exists to catch this project's most expensive-to-repeat class of
bug: calculation logic that silently regresses back to a previous, wrong
behavior (see the full changelog for real examples - the Pressure Type A
divisor, the CMC half-open range bug, etc). Every one of these was
originally found and verified by hand against real generated output during
past sessions; this file exists so that verification doesn't have to be
redone by hand every time - it runs automatically.

Two categories of test here, and they are NOT interchangeable:

1. Tests that lock in a documented, intentional anomaly (e.g.
   calculate_u_res's missing sqrt(3), calculate_type_a_electrical's flat
   divisor of 2). These values deliberately deviate from textbook GUM
   theory to match the real Instruworks source spreadsheets - see
   Section "Known Anomalies" in the handover. If one of these tests
   starts failing after a code change, the change is very likely an
   unauthorized "correction" of a documented anomaly and should NOT be
   merged without Eng. Charkha's explicit sign-off first.

2. Tests that lock in a genuine bug fix (e.g. Pressure Type A's /sqrt(n)
   divisor, the CMC band's inclusive upper bound). If one of these starts
   failing, the bug has likely been silently reintroduced.
"""

import math
import statistics

import pytest

from modules import calculation_engine as ce


# ── root_sum_square ───────────────────────────────────────────────────────

def test_root_sum_square_combines_components_correctly():
    result = ce.root_sum_square(3.0, 4.0)
    assert result == pytest.approx(5.0)  # classic 3-4-5 triangle


def test_root_sum_square_treats_none_as_zero():
    # A None component (e.g. a category with no u_temp) must not crash or
    # be treated as a real contributor.
    assert ce.root_sum_square(3.0, None, 4.0) == pytest.approx(5.0)


def test_root_sum_square_of_nothing_is_zero():
    assert ce.root_sum_square() == 0.0


# ── Pressure: calculate_type_a (the /sqrt(n) fix) ─────────────────────────

def test_calculate_type_a_divides_by_sqrt_n():
    """Locks in the Round 5.5 fix: this must be the standard deviation of
    the MEAN (stdev / sqrt(n)), not the raw sample stdev. Before the fix,
    this function returned stdev(mean_errors) with no divisor at all,
    which overestimates every Pressure certificate's Type A component by
    a factor of sqrt(n). If this test starts failing because the divisor
    was removed again, every previously-issued Pressure certificate's
    numbers would silently be wrong again.
    """
    mean_errors = [0.10, 0.12, 0.11, 0.09, 0.13]
    readings = [{"mean_error": v} for v in mean_errors]

    expected = statistics.stdev(mean_errors) / math.sqrt(len(mean_errors))
    assert ce.calculate_type_a(readings) == pytest.approx(expected)

    # Sanity: the un-fixed (buggy) formula would have been just
    # stdev(mean_errors), which is sqrt(n) times larger - confirm we are
    # NOT matching that.
    buggy_value = statistics.stdev(mean_errors)
    assert ce.calculate_type_a(readings) < buggy_value


def test_calculate_type_a_single_reading_returns_zero():
    # stdev is undefined for n=1; must not raise.
    assert ce.calculate_type_a([{"mean_error": 0.1}]) == 0.0


def test_calculate_type_a_empty_readings_raises():
    with pytest.raises(ValueError):
        ce.calculate_type_a([])


# ── Pressure: calculate_u_res (documented anomaly - do NOT "fix" this) ────

def test_calculate_u_res_matches_documented_anomaly_no_sqrt3():
    """This is INTENTIONALLY not dividing by sqrt(3), even though that's
    what standard GUM rectangular-distribution theory would require for a
    resolution-based component. The real Instruworks source certificate
    format also omits it - see calculate_u_res's own docstring and the
    handover's "Known Anomalies" section. This test exists specifically
    so nobody "fixes" this back to textbook-correct without Eng.
    Charkha's confirmation first - if this test fails, check the
    anomalies section before assuming the code is wrong.
    """
    assert ce.calculate_u_res(0.02) == pytest.approx(0.01)  # 0.02 / 2, NOT / (2*sqrt(3))


def test_calculate_u_res_rejects_negative_resolution():
    with pytest.raises(ValueError):
        ce.calculate_u_res(-0.01)


def test_calculate_u_res_rejects_none():
    with pytest.raises(ValueError):
        ce.calculate_u_res(None)


# ── Pressure: calculate_u_zero, calculate_u_repeatability, calculate_u_hys ─

def test_calculate_u_zero_finds_the_zero_point():
    readings = [
        {"nominal_value": 0, "mean_error": -0.05},
        {"nominal_value": 50, "mean_error": 0.10},
    ]
    assert ce.calculate_u_zero(readings) == pytest.approx(0.05)  # abs()


def test_calculate_u_zero_returns_zero_if_no_zero_point():
    readings = [{"nominal_value": 50, "mean_error": 0.10}]
    assert ce.calculate_u_zero(readings) == 0.0


def test_calculate_u_repeatability_needs_at_least_three_readings():
    assert ce.calculate_u_repeatability([{"mean_error": 0.1}, {"mean_error": 0.2}]) == 0.0


def test_calculate_u_repeatability_uses_successive_differences():
    readings = [{"mean_error": v} for v in [0.10, 0.15, 0.12, 0.18]]
    diffs = [abs(0.15 - 0.10), abs(0.12 - 0.15), abs(0.18 - 0.12)]
    assert ce.calculate_u_repeatability(readings) == pytest.approx(statistics.stdev(diffs))


# ── CMC band lookup (Round 10 fix: inclusive upper bound) ─────────────────

def test_lookup_cmc_band_finds_value_at_exact_top_of_range():
    """Locks in the Round 10 fix. Before it, the lookup used a half-open
    range (min <= value < max), so testing an instrument at exactly the
    top of its range - a completely normal '100% of range' test point -
    would silently fail to match any band. This must now be inclusive on
    both ends.
    """
    bands = [
        {"min_value": 0, "max_value": 100, "cmc_value": 0.05},
        {"min_value": 100, "max_value": 200, "cmc_value": 0.08},
    ]
    # Exactly at the boundary between two bands - inclusive-upper means
    # this matches the first band (0-100), not the second.
    result = ce.lookup_cmc_band(bands, 100)
    assert result is not None
    assert result["cmc_value"] == pytest.approx(0.05)


def test_lookup_cmc_band_finds_value_in_middle_of_range():
    bands = [{"min_value": 0, "max_value": 100, "cmc_value": 0.05}]
    assert ce.lookup_cmc_band(bands, 50)["cmc_value"] == pytest.approx(0.05)


def test_lookup_cmc_band_returns_none_when_out_of_range():
    bands = [{"min_value": 0, "max_value": 100, "cmc_value": 0.05}]
    assert ce.lookup_cmc_band(bands, 150) is None


# ── Electrical: calculate_type_a_electrical (documented anomaly) ──────────

def test_calculate_type_a_electrical_divides_by_flat_2_not_sqrt_n():
    """Locks in a documented anomaly: the real source sheets' own
    "Devisor" column explicitly shows 2 for every Electrical Type A row,
    regardless of how many readings were taken - confirmed across three
    independent sheets (DCV, ACV, DCA Coil). This is NOT textbook GUM
    (which would divide by sqrt(n)) and must not be "corrected" without
    Charkha's confirmation.
    """
    readings = [10.01, 10.02, 9.99, 10.00, 10.03]
    expected = statistics.stdev(readings) / 2
    assert ce.calculate_type_a_electrical(readings) == pytest.approx(expected)

    # Confirm we are NOT accidentally matching the textbook sqrt(n) formula.
    textbook_value = statistics.stdev(readings) / math.sqrt(len(readings))
    assert ce.calculate_type_a_electrical(readings) != pytest.approx(textbook_value)


def test_calculate_type_a_electrical_dcv_extra_addend():
    """DCV's specific quirk: the real sheet adds a thermo-electric limit
    to the Type A estimate BEFORE dividing by 2, not after. This is
    separate from (and, per the handover's anomalies section, possibly
    double-counted with) the same value's own independent Ub4 component -
    that double-counting is a separate, still-unconfirmed question; this
    test only locks in the arithmetic actually implemented.
    """
    readings = [10.01, 10.02, 9.99, 10.00, 10.03]
    extra = 0.02
    expected = (statistics.stdev(readings) + extra) / 2
    assert ce.calculate_type_a_electrical(readings, extra_addend=extra) == pytest.approx(expected)


def test_calculate_type_a_electrical_single_reading_returns_extra_addend_halved():
    # Matches the documented behavior: returns extra_addend / 2 rather
    # than raising, since stdev is undefined for a single reading.
    assert ce.calculate_type_a_electrical([10.0], extra_addend=0.02) == pytest.approx(0.01)


def test_calculate_type_a_electrical_empty_readings_raises():
    with pytest.raises(ValueError):
        ce.calculate_type_a_electrical([], extra_addend=0.0)


def test_calculate_u_rectangular_from_limit():
    # Ub2-style: value / sqrt(3), the correct GUM rectangular treatment
    # (this one is NOT one of the anomalies - Ub2 was independently
    # confirmed correct against real computed values, per the handover).
    assert ce.calculate_u_rectangular_from_limit(1.0) == pytest.approx(1 / math.sqrt(3))


def test_calculate_u_resolution_electrical_full_rectangular_treatment():
    # Ub3: (value/2)/sqrt(3) - confirmed correct against real source data.
    assert ce.calculate_u_resolution_electrical(0.01) == pytest.approx((0.01 / 2) / math.sqrt(3))


# ── Temperature: calculate_type_a_temperature ─────────────────────────────

def test_calculate_type_a_temperature_divides_by_sqrt_n_readings_param():
    # Takes a plain list of floats (not dicts), and divides by the
    # n_readings parameter (default 3, matching all four real source
    # files), not necessarily len(readings).
    values = [0.01, 0.02, 0.015]
    expected = statistics.stdev(values) / math.sqrt(3)
    assert ce.calculate_type_a_temperature(values) == pytest.approx(expected)


def test_calculate_type_a_temperature_single_reading_returns_zero():
    assert ce.calculate_type_a_temperature([0.01]) == 0.0


def test_calculate_type_a_temperature_empty_raises():
    with pytest.raises(ValueError):
        ce.calculate_type_a_temperature([])