from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from uuid import UUID


class InstrumentCreate(BaseModel):
    """Pydantic model for creating a new instrument record.

    Attributes:
        name: Human-readable instrument name.
        type: Instrument category (Pressure, Temperature, Electrical, Weighing).
        make: Manufacturer name.
        model: Model designation.
        serial_number: Instrument serial number.
        range_min: Minimum of measurement range.
        range_max: Maximum of measurement range.
        unit: Unit of measurement.
        resolution: Instrument resolution.
        accuracy_class: Accuracy class string.
        tag_number: Site tag or asset number.
        calibration_carried_at: Location where calibration is carried out.
        dial_size: Dial size if applicable.
        mounting_orientation: Mounting orientation if applicable.
        instrument_location: Physical location of the instrument.
        medium_used: Medium used during calibration.
    """
    name: str
    type: str
    instrument_subtype: Optional[str] = None
    make: str
    model: str
    serial_number: str
    range_min: float
    range_max: float
    unit: str
    resolution: float
    accuracy_class: str
    tag_number: Optional[str] = None
    calibration_carried_at: Optional[str] = None
    dial_size: Optional[str] = None
    mounting_orientation: Optional[str] = None
    instrument_location: Optional[str] = None
    medium_used: Optional[str] = None


class CalibrationSessionCreate(BaseModel):
    """Pydantic model for creating a new calibration session.

    Attributes:
        instrument_id: UUID of the instrument being calibrated.
        master_instrument_id: UUID of the master instrument used as the
            calibration standard for this session. Optional because older
            rows predate this field, but should be set for every new session
            so reporting.gather_report_data can populate master_record.
        date: Date of the calibration session.
        technician: Name of the technician performing calibration.
        temperature_c: Ambient temperature in degrees Celsius.
        humidity_pct: Relative humidity percentage.
        notes: Optional session notes.
    """
    instrument_id: UUID
    master_instrument_id: Optional[UUID] = None
    date: date
    technician: str
    temperature_c: float
    humidity_pct: float
    notes: Optional[str] = None


class ReadingCreate(BaseModel):
    """Pydantic model for creating a calibration reading record.

    Used by Pressure, Temperature, and Electrical sessions. Weighing sessions
    do not use this model — see WeighingRepeatabilityReadingCreate,
    WeighingOffCenterReadingCreate, and WeighingHysteresisReadingCreate below.

    Attributes:
        session_id: UUID of the parent calibration session.
        point_number: Sequential calibration point number.
        nominal_value: The nominal or target value at this point.
        measured_value_up: Ascending measurement at this point.
        measured_value_down: Descending measurement at this point.
        reference_value: Reference instrument reading at this point.
        correction: Correction value applied.
        mean_error: Mean of ascending and descending errors.
        hysteresis: Absolute difference between ascending and descending readings.
    """
    session_id: UUID
    point_number: int
    nominal_value: float
    measured_value_up: float
    measured_value_down: float
    reference_value: float
    correction: float
    mean_error: float
    hysteresis: float


class MasterInstrumentCreate(BaseModel):
    """Pydantic model for creating a master instrument record.

    Attributes:
        name: Master instrument name.
        make: Manufacturer name.
        model: Model designation.
        serial_number: Serial number.
        asset_number: Asset or inventory number.
        traceability_chain: Documented traceability chain string.
        uncertainty_u: Uncertainty value from calibration certificate.
        accuracy: Accuracy of the master instrument.
        resolution: Resolution of the master instrument.
        cal_due_date: Next calibration due date.
        claimed_cmc: Claimed measurement capability of the laboratory.
        instrument_type: Category of instrument (Pressure, Temperature, etc).
        master_certificate_number: The master instrument's own calibration
            certificate number, as issued by whichever lab calibrated it.
            Optional since older/legacy master instruments may not have
            this recorded.
    """
    name: str
    make: str
    model: str
    serial_number: str
    asset_number: str
    traceability_chain: str
    uncertainty_u: float
    accuracy: float
    resolution: float
    cal_due_date: date
    claimed_cmc: float
    instrument_type: str
    master_certificate_number: Optional[str] = None


class CalibrationReferenceCreate(BaseModel):
    """Pydantic model for creating a calibration reference record.

    Attributes:
        session_id: UUID of the associated calibration session.
        certificate_number: Unique certificate number.
        date_of_calibration: Date the calibration was performed.
        cal_due_date: Next calibration due date.
        item_received_date: Date the instrument was received.
        date_of_issue: Date the certificate was issued.
        customer_name: Name of the customer.
        customer_address: Address of the customer.
    """
    session_id: UUID
    certificate_number: str
    date_of_calibration: date
    cal_due_date: date
    item_received_date: date
    date_of_issue: date
    customer_name: str
    customer_address: str


class UncertaintyBudgetCreate(BaseModel):
    """Pydantic model for creating an uncertainty budget record.

    Attributes:
        session_id: UUID of the associated calibration session.
        type_a_value: Type A uncertainty evaluation result.
        u_std: Standard uncertainty from master certificate.
        u_res: Resolution uncertainty.
        u_hys: Hysteresis uncertainty.
        u_head: Medium head correction uncertainty.
        u_zero: Zero offset uncertainty.
        u_temp: Temperature influence uncertainty.
        u_std_weights: Standard weights' contributed uncertainty. Weighing
            sessions only; leave unset for Pressure/Temperature/Electrical.
        u_eccentric: Eccentric/off-center loading uncertainty. Weighing
            sessions only; leave unset for Pressure/Temperature/Electrical.
        cmc: Claimed measurement capability.
        combined_uncertainty: Root sum of squares of all components.
        expanded_uncertainty: Combined uncertainty multiplied by coverage factor.
        k_value: Coverage factor.
        final_applied_uncertainty: Larger of expanded uncertainty and CMC.
        temperature_test_id: UUID of the specific temperature_repeatability_test
            this budget is for. Temperature sessions only - one budget row
            per setpoint, not one per session. None for every other category.
        electrical_test_id: UUID of the specific electrical_test this budget
            is for. Electrical sessions only - one budget row per function-
            type/range tested, not one per session. None for every other category.
        u_b1: Electrical Type B component 1 (Uncertainty of Standard
            Calibrator). Electrical sessions only.
        u_b2: Electrical Type B component 2 (Accuracy of Standard
            Calibrator). Electrical sessions only.
        u_b3: Electrical Type B component 3 (UUC Resolution, or Accuracy
            of Current Coil for the two Coil function types). Electrical
            sessions only.
        u_b4: Electrical Type B component 4 (Thermo-Electric Voltage for
            DCV, or UUC Resolution for the two Coil function types).
            Electrical sessions only; None for the 8 function types that
            only have 3 Type B components.
    """
    session_id: UUID
    type_a_value: float
    u_std: Optional[float] = None
    u_std_accuracy: Optional[float] = None
    u_res: Optional[float] = None
    u_hys: Optional[float] = None
    u_head: Optional[float] = None
    u_zero: Optional[float] = None
    u_temp: Optional[float] = None
    u_repeatability: Optional[float] = None
    u_std_weights: Optional[float] = None
    u_eccentric: Optional[float] = None
    u_drift: Optional[float] = None
    u_bath_stability: Optional[float] = None
    u_bath_uniformity: Optional[float] = None
    u_wire_homogeneity: Optional[float] = None
    cmc: float
    combined_uncertainty: float
    expanded_uncertainty: float
    k_value: float
    final_applied_uncertainty: float
    temperature_test_id: Optional[UUID] = None
    electrical_test_id: Optional[UUID] = None
    u_b1: Optional[float] = None
    u_b2: Optional[float] = None
    u_b3: Optional[float] = None
    u_b4: Optional[float] = None


# ── Weighing test models ────────────────────────────────────────────────────
# Weighing sessions capture raw test data across three separate procedures
# (repeatability, off-center, hysteresis) rather than the single
# ascending/descending-per-point pattern used by Pressure/Temperature/Electrical.
# See ReadingCreate above for the pattern used by the other three categories.

class WeighingRepeatabilityTestCreate(BaseModel):
    """Pydantic model for creating a weighing repeatability test record.

    One record per test_point (near_zero, fifty_percent, hundred_percent).
    Each test_point has 10 associated readings — see
    WeighingRepeatabilityReadingCreate.

    Attributes:
        session_id: UUID of the parent calibration session.
        test_point: Which of the three fixed load points this test covers.
        nominal_load: The nominal load applied at this test point.
        unit: Unit of measurement (e.g. kg, g).
        standard_weights_uncertainty: Combined uncertainty of the standard
            weight combination used at this point, taken from the
            standard weights' own calibration certificates.
    """
    session_id: UUID
    test_point: str  # 'near_zero' | 'fifty_percent' | 'hundred_percent'
    nominal_load: float
    unit: str
    standard_weights_uncertainty: Optional[float] = None


class WeighingRepeatabilityReadingCreate(BaseModel):
    """Pydantic model for creating a single repeatability reading.

    Attributes:
        test_id: UUID of the parent WeighingRepeatabilityTest.
        reading_number: Which of the 10 readings this is (1-10).
        reading_before: Zero/tare reading before load is applied.
        reading_with_load: Reading with the nominal load applied.
        reading_after: Zero/tare reading after load is removed.
    """
    test_id: Optional[UUID] = None
    reading_number: int
    reading_before: float
    reading_with_load: float
    reading_after: float


class WeighingOffCenterReadingCreate(BaseModel):
    """Pydantic model for creating a single off-center (eccentricity) reading.

    Five fixed positions are tested at a chosen load, typically 50% of range.

    Attributes:
        session_id: UUID of the parent calibration session. Optional because
            the client never sends it per-reading - it's already in the URL
            path (POST /api/sessions/{session_id}/weighing/off-center) and is
            filled in server-side before insert. Requiring it here caused
            every submission to fail 422 validation before the endpoint body
            ever ran, since the frontend correctly never included it.
        position: Which of the five fixed positions this reading is for.
        nominal_load: The nominal load applied for this test.
        unit: Unit of measurement.
        reading_before: Zero/tare reading before load is applied.
        reading_with_load: Reading with the nominal load applied at this position.
        reading_after: Zero/tare reading after load is removed.
    """
    session_id: Optional[UUID] = None
    position: str  # 'center' | 'front' | 'back' | 'left' | 'right'
    nominal_load: float
    unit: str
    reading_before: float
    reading_with_load: float
    reading_after: float


class WeighingHysteresisReadingCreate(BaseModel):
    """Pydantic model for creating a single hysteresis sequence reading.

    Five-step fixed sequence: zero_before -> half_load_ascending -> full_load
    -> half_load_descending -> zero_after.

    Attributes:
        session_id: UUID of the parent calibration session. Optional for the
            same reason as WeighingOffCenterReadingCreate.session_id - it's
            supplied via the URL path and filled in server-side, never sent
            per-reading by the client.
        sequence_order: Position in the 5-step sequence (1-5).
        phase: Which phase of the sequence this reading represents.
        reading_value: The recorded reading at this phase.
        unit: Unit of measurement.
    """
    session_id: Optional[UUID] = None
    sequence_order: int
    phase: str  # 'zero_before' | 'half_load_ascending' | 'full_load' | 'half_load_descending' | 'zero_after'
    reading_value: float
    unit: str


class CMCBandCreate(BaseModel):
    """Pydantic model for creating a CMC-by-load-band lookup record.

    Shared reference data (not per-user) used to determine the claimed
    measurement capability applicable to a given load value.

    Attributes:
        instrument_type: Category this band applies to (e.g. 'Weighing').
        min_value: Lower bound of the load range this band covers.
        max_value: Upper bound of the load range this band covers.
        unit: Unit for min_value/max_value.
        cmc_value: The CMC value for this load band.
        cmc_unit: Unit for cmc_value.
        standard_ref: Optional reference to the accreditation scope document.
    """
    instrument_type: str
    min_value: float
    max_value: float
    unit: str
    cmc_value: float
    cmc_unit: str
    standard_ref: Optional[str] = None


# ── Temperature repeatability test models ───────────────────────────────────
# Mirrors the weighing_repeatability_* pattern: one row per setpoint tested,
# each with 3 repeated readings, rather than the single ascending/descending
# per-point shape used by the 'readings' table for Pressure/Electrical.

class TemperatureRepeatabilityTestCreate(BaseModel):
    """Pydantic model for creating a temperature repeatability test record.

    One record per setpoint tested (e.g. -15C, 110C, 300C, 650C). Each
    setpoint has 3 associated readings — see
    TemperatureRepeatabilityReadingCreate.

    Attributes:
        session_id: UUID of the parent calibration session.
        setpoint_label: Free-text label for this setpoint (e.g. 'minus_15c').
        nominal_temperature: The nominal temperature at this setpoint.
        unit: Unit of measurement (default 'C').
        standard_uncertainty: Master's own cert uncertainty at this setpoint (Ub1).
        standard_accuracy: Master's accuracy at this setpoint (Ub2).
        drift_standard_uncertainty: Pre-computed drift figure (Ub3) — entered
            directly rather than derived from a raw spec value; see
            calculation_engine.calculate_u_drift's docstring for why.
        hysteresis_value: Signed hysteresis reading at this setpoint (Ub5).
        bath_stability_value: Raw bath stability value (Ub6).
        bath_uniformity_value: Raw bath uniformity value (Ub7).
        wire_homogeneity_value: Raw wire homogeneity value (Ub8), TCK
            sub-type only; null for RTD/DTI/DryBlock.
    """
    session_id: UUID
    setpoint_label: str
    nominal_temperature: float
    unit: str = "C"
    standard_uncertainty: Optional[float] = None
    standard_accuracy: Optional[float] = None
    drift_standard_uncertainty: Optional[float] = None
    hysteresis_value: Optional[float] = None
    bath_stability_value: Optional[float] = None
    bath_uniformity_value: Optional[float] = None
    wire_homogeneity_value: Optional[float] = None


class TemperatureRepeatabilityReadingCreate(BaseModel):
    """Pydantic model for creating a single temperature repeatability reading.

    Attributes:
        test_id: UUID of the parent TemperatureRepeatabilityTest.
        reading_number: Which of the 3 readings this is (1-3).
        reading_value: The recorded temperature reading.
    """
    test_id: Optional[UUID] = None
    reading_number: int
    reading_value: float


# ── Electrical test models ───────────────────────────────────────────────────
# One row per function-type-and-range tested (e.g. a single DMM session
# might test DCV at 6 different ranges), same pattern as Temperature's
# one-row-per-setpoint. See formulas/electrical.json for the 11 valid
# function_type values and which of thermo_electric_limit/
# coil_accuracy_limit apply to which.

class ElectricalTestCreate(BaseModel):
    """Pydantic model for creating an Electrical test (one function-type/range).

    Attributes:
        session_id: UUID of the associated calibration session.
        function_type: One of the 11 function types (e.g. 'DCV', 'ACV',
            'DCA (Coil)') - must match formulas/electrical.json's
            function_types keys exactly.
        range_label: Human-readable range identifier (e.g. '20mV', '50A').
        nominal_value: The numeric nominal test point within this range.
        unit: Unit of measurement (e.g. 'mV', 'A', 'Ohm').
        cert_uncertainty_limit: Ub1 input - Uncertainty of Standard Calibrator.
        calibrator_accuracy_limit: Ub2 input - Accuracy of Standard Calibrator.
        resolution: Ub3 (or Ub4 for Coil types) input - UUC resolution.
        thermo_electric_limit: DCV only - required for DCV, None otherwise.
        coil_accuracy_limit: DCA (Coil) / ACA (Coil) only - required for
            those two, None otherwise.
    """
    session_id: UUID
    function_type: str
    range_label: str
    nominal_value: Optional[float] = None
    unit: str
    cert_uncertainty_limit: Optional[float] = None
    calibrator_accuracy_limit: Optional[float] = None
    resolution: Optional[float] = None
    thermo_electric_limit: Optional[float] = None
    coil_accuracy_limit: Optional[float] = None


class ElectricalReadingCreate(BaseModel):
    """Pydantic model for creating a single Electrical repeated reading.

    Attributes:
        test_id: UUID of the parent ElectricalTest. Optional since it
            can't be known client-side before the parent test row is
            inserted - same reasoning as WeighingRepeatabilityReadingCreate
            and TemperatureRepeatabilityReadingCreate's test_id fields.
        reading_number: Which repeated reading this is (1-indexed).
        reading_value: The recorded UUC reading.
    """
    test_id: Optional[UUID] = None
    reading_number: int
    reading_value: float


# ── Roles / review workflow ───────────────────────────────────────────────

VALID_TITLES = ("QM", "TM", "MR", "MD", "Cal Tech", "Engineer", "Admin", "Lab Staff", "Viewer")
# Titles a user may request via the role-change request flow. Deliberately
# excludes nothing today (any title can be requested) - if MD/MR should
# ever be excluded from self-service requests, restrict this tuple, not
# VALID_TITLES above (which profiles.title itself still allows).
REQUESTABLE_TITLES = ("QM", "TM", "MR", "MD", "Cal Tech", "Engineer", "Admin", "Lab Staff")


class ProfileUpdate(BaseModel):
    """Pydantic model for updating a user's own profile.

    Attributes:
        full_name: New display name.
        employee_id: Employee ID / payroll number - free text, display-only.
        site_location: Site/facility location - free text, display-only.
        department: Assigned lab/department - free text, display-only.

    Title is deliberately NOT editable here - title changes only happen
    via an approved RoleChangeRequestCreate, handled by a full-edit-tier
    user. is_active is also not editable here - see the dedicated
    deactivate/reactivate endpoints in main.py.

    All fields are optional so a partial update (e.g. just changing
    site_location) doesn't require resending everything else.
    """
    full_name: Optional[str] = None
    employee_id: Optional[str] = None
    site_location: Optional[str] = None
    department: Optional[str] = None


class RoleChangeRequestCreate(BaseModel):
    """Pydantic model for a user requesting a different job title.

    Attributes:
        requested_title: The title being requested (must be one of
            REQUESTABLE_TITLES).
        reason: Optional free-text explanation shown to the reviewer.
    """
    requested_title: str
    reason: Optional[str] = None


class RoleChangeReviewDecision(BaseModel):
    """Pydantic model for a full-edit-tier user approving or denying a
    pending role-change request.

    Attributes:
        reason: Optional note explaining the decision, most useful on a
            denial so the requester knows why.
    """
    reason: Optional[str] = None


class SessionReviewDecision(BaseModel):
    """Pydantic model for a full-edit-tier user approving or rejecting a
    session flagged by check_master_instrument_validity.

    Attributes:
        review_note: Optional replacement note - e.g. a rejection reason
            beyond the original flag. If omitted, the original flag
            reason (set when the session was first flagged) is kept as-is.
    """
    review_note: Optional[str] = None