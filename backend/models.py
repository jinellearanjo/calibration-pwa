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
    """
    session_id: UUID
    type_a_value: float
    u_std: Optional[float] = None
    u_res: Optional[float] = None
    u_hys: Optional[float] = None
    u_head: Optional[float] = None
    u_zero: Optional[float] = None
    u_temp: Optional[float] = None
    u_std_weights: Optional[float] = None
    u_eccentric: Optional[float] = None
    cmc: float
    combined_uncertainty: float
    expanded_uncertainty: float
    k_value: float
    final_applied_uncertainty: float


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
    test_id: UUID
    reading_number: int
    reading_before: float
    reading_with_load: float
    reading_after: float


class WeighingOffCenterReadingCreate(BaseModel):
    """Pydantic model for creating a single off-center (eccentricity) reading.

    Five fixed positions are tested at a chosen load, typically 50% of range.

    Attributes:
        session_id: UUID of the parent calibration session.
        position: Which of the five fixed positions this reading is for.
        nominal_load: The nominal load applied for this test.
        unit: Unit of measurement.
        reading_before: Zero/tare reading before load is applied.
        reading_with_load: Reading with the nominal load applied at this position.
        reading_after: Zero/tare reading after load is removed.
    """
    session_id: UUID
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
        session_id: UUID of the parent calibration session.
        sequence_order: Position in the 5-step sequence (1-5).
        phase: Which phase of the sequence this reading represents.
        reading_value: The recorded reading at this phase.
        unit: Unit of measurement.
    """
    session_id: UUID
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