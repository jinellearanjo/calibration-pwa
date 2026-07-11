"""tests/test_reporting.py

Regression tests for modules/reporting.py's shared block-builder helpers:
_build_readings_blocks and _build_uncertainty_budget_blocks.

Both are shared by generate_pdf_report and generate_excel_report
specifically so the two renderers can't independently drift out of sync
with each other - these tests exercise the shared builders directly
(cheaper and more precise than generating a real PDF/Excel file and
extracting text from it, which is what past sessions did by hand each
time a category was added).

Covers the two real bugs this project found in these builders:
1. The readings table used to be hardcoded to Pressure's shape for every
   category, so Weighing/Temperature/Electrical certificates rendered an
   empty or wrong-shaped table.
2. Multi-budget sessions (Temperature/Electrical) used to raise a
   RuntimeError instead of rendering, before per-budget blocks existed.
"""

import dataclasses

import pytest

from modules.reporting import (
    ReportData,
    _build_readings_blocks,
    _build_uncertainty_budget_blocks,
)


def _make_report_data(instrument_type: str, **overrides) -> ReportData:
    """Builds a minimal-but-valid ReportData for a given category, with
    every required field filled with an inert placeholder value. Tests
    only need to override the specific fields relevant to what they're
    checking (instrument_type plus whichever test-data lists matter).
    """
    required_fields = {
        f.name for f in dataclasses.fields(ReportData)
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    base = {name: f"placeholder_{name}" for name in required_fields}
    base["instrument_type"] = instrument_type
    base.update(overrides)
    return ReportData(**base)


# ── _build_readings_blocks: category-aware shape ──────────────────────────

def test_pressure_readings_block_uses_ascending_descending_shape():
    report_data = _make_report_data(
        "Pressure",
        readings=[
            {"nominal_value": 10, "measured_value_up": 10.01, "measured_value_down": 9.99,
             "mean_error": 0.01, "hysteresis": 0.02},
        ],
    )
    blocks = _build_readings_blocks(report_data)

    assert len(blocks) == 1
    assert blocks[0]["title"] is None
    assert blocks[0]["header"] == [
        "Nominal Value", "Ascending Measured", "Descending Measured", "Mean Error", "Hysteresis"
    ]
    assert blocks[0]["rows"] == [["10", "10.01", "9.99", "0.01", "0.02"]]


def test_weighing_readings_block_returns_three_labeled_sub_tables():
    """Locks in the Round 3 fix: Weighing must NOT reuse Pressure's shape -
    it needs three separate, labeled sub-tables.
    """
    report_data = _make_report_data(
        "Weighing",
        weighing_repeatability=[{
            "test_point": "near_zero", "nominal_load": 10, "unit": "g",
            "weighing_repeatability_readings": [
                {"reading_number": 1, "reading_before": 10.0, "reading_with_load": 10.1, "reading_after": 10.0},
            ],
        }],
        weighing_off_center=[{
            "position": "center", "nominal_load": 10, "unit": "g",
            "reading_before": 10.0, "reading_with_load": 10.1, "reading_after": 10.0,
        }],
        weighing_hysteresis=[{
            "sequence_order": 1, "phase": "up", "reading_value": 10.0, "unit": "g",
        }],
    )
    blocks = _build_readings_blocks(report_data)

    assert len(blocks) == 3
    titles = [b["title"] for b in blocks]
    assert titles == ["Repeatability", "Off-Center (Eccentricity)", "Hysteresis"]
    # Each sub-table actually has its own real rows, not an empty/wrong shape.
    assert len(blocks[0]["rows"]) == 1
    assert len(blocks[1]["rows"]) == 1
    assert len(blocks[2]["rows"]) == 1


def test_temperature_readings_block_uses_setpoint_shape_not_pressure_shape():
    report_data = _make_report_data(
        "Temperature",
        temperature_repeatability=[{
            "setpoint_label": "110c", "nominal_temperature": 110, "unit": "\u00b0C",
            "temperature_repeatability_readings": [
                {"reading_number": 1, "reading_value": 110.1},
                {"reading_number": 2, "reading_value": 109.9},
            ],
        }],
    )
    blocks = _build_readings_blocks(report_data)

    assert len(blocks) == 1
    assert blocks[0]["header"] == ["Setpoint", "Nominal Temperature", "Unit", "Reading #", "Reading Value"]
    assert len(blocks[0]["rows"]) == 2  # one row per nested reading, not per setpoint
    assert blocks[0]["rows"][0][0] == "110c"


def test_electrical_readings_block_uses_function_type_shape_not_pressure_shape():
    """Locks in the Round 9 fix: Electrical was found silently falling
    through to Pressure's ascending/descending shape (same bug class as
    Weighing/Temperature, just not caught until Electrical existed).
    """
    report_data = _make_report_data(
        "Electrical",
        electrical_tests=[{
            "function_type": "ACV", "range_label": "200mV", "unit": "mV",
            "electrical_readings": [{"reading_number": 1, "reading_value": 200.1}],
        }],
    )
    blocks = _build_readings_blocks(report_data)

    assert len(blocks) == 1
    assert blocks[0]["header"] == ["Function Type", "Range", "Unit", "Reading #", "Reading Value"]
    assert blocks[0]["rows"] == [["ACV", "200mV", "mV", "1", "200.1"]]


def test_readings_block_rows_are_pre_stringified_and_none_becomes_em_dash():
    # _safe_str's None -> em-dash substitution must actually be applied,
    # not just documented - a raw None reaching ReportLab's Table crashes it.
    report_data = _make_report_data(
        "Pressure",
        readings=[{"nominal_value": 10, "measured_value_up": None, "measured_value_down": 9.99,
                   "mean_error": None, "hysteresis": None}],
    )
    blocks = _build_readings_blocks(report_data)
    row = blocks[0]["rows"][0]
    assert all(isinstance(cell, str) for cell in row)
    assert row[1] == "\u2014"  # measured_value_up was None


# ── _build_uncertainty_budget_blocks: single vs multi-budget ──────────────

def test_single_budget_produces_one_untitled_block():
    """The single-budget case (Pressure/Weighing, or Temperature/
    Electrical with exactly one setpoint/range) must have title=None -
    matching the certificate's look from before multi-budget sessions
    existed, per _build_uncertainty_budget_blocks' own docstring.
    """
    report_data = _make_report_data(
        "Pressure",
        all_uncertainty_budgets=[{
            "type_a_value": 0.01, "u_std": 0.02, "cmc": 0.05,
            "combined_uncertainty": 0.03, "expanded_uncertainty": 0.06,
            "k_value": 2.0, "final_applied_uncertainty": 0.06,
        }],
    )
    blocks = _build_uncertainty_budget_blocks(report_data)

    assert len(blocks) == 1
    assert blocks[0]["title"] is None


def test_multi_budget_temperature_produces_one_labeled_block_per_setpoint():
    """Locks in the Round 9 fix: multi-budget sessions used to raise a
    RuntimeError instead of rendering at all.
    """
    report_data = _make_report_data(
        "Temperature",
        temperature_repeatability=[
            {"id": "t1", "setpoint_label": "minus_15c"},
            {"id": "t2", "setpoint_label": "300c"},
        ],
        all_uncertainty_budgets=[
            {"temperature_test_id": "t1", "type_a_value": 0.01, "cmc": 0.05,
             "combined_uncertainty": 0.02, "expanded_uncertainty": 0.04,
             "k_value": 2.0, "final_applied_uncertainty": 0.04},
            {"temperature_test_id": "t2", "type_a_value": 0.03, "cmc": 0.05,
             "combined_uncertainty": 0.05, "expanded_uncertainty": 0.10,
             "k_value": 2.0, "final_applied_uncertainty": 0.10},
        ],
    )
    blocks = _build_uncertainty_budget_blocks(report_data)

    assert len(blocks) == 2
    titles = {b["title"] for b in blocks}
    assert titles == {"Setpoint: minus_15c", "Setpoint: 300c"}


def test_multi_budget_electrical_labels_use_function_type_and_range():
    report_data = _make_report_data(
        "Electrical",
        electrical_tests=[
            {"id": "e1", "function_type": "ACV", "range_label": "200mV"},
            {"id": "e2", "function_type": "DCA", "range_label": "10A"},
        ],
        all_uncertainty_budgets=[
            {"electrical_test_id": "e1", "u_b1": 0.01, "cmc": 0.05,
             "combined_uncertainty": 0.02, "expanded_uncertainty": 0.04,
             "k_value": 2.0, "final_applied_uncertainty": 0.04},
            {"electrical_test_id": "e2", "u_b1": 0.02, "cmc": 0.05,
             "combined_uncertainty": 0.03, "expanded_uncertainty": 0.06,
             "k_value": 2.0, "final_applied_uncertainty": 0.06},
        ],
    )
    blocks = _build_uncertainty_budget_blocks(report_data)

    assert len(blocks) == 2
    titles = {b["title"] for b in blocks}
    assert titles == {"ACV - 200mV", "DCA - 10A"}


def test_budget_block_only_includes_components_actually_present():
    # Components not applicable to this category (None) must be omitted
    # from the rendered rows entirely, not shown as a blank/em-dash row.
    report_data = _make_report_data(
        "Pressure",
        all_uncertainty_budgets=[{
            "type_a_value": 0.01,
            "u_std": None,       # not present for this budget
            "u_hys": 0.005,
            "cmc": 0.05, "combined_uncertainty": 0.03,
            "expanded_uncertainty": 0.06, "k_value": 2.0,
            "final_applied_uncertainty": 0.06,
        }],
    )
    blocks = _build_uncertainty_budget_blocks(report_data)
    row_labels = [label for label, _ in blocks[0]["rows"]]

    assert "Type A Uncertainty (u_A)" in row_labels
    assert "Hysteresis Uncertainty (u_hys)" in row_labels
    assert "Standard Uncertainty (u_std)" not in row_labels