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
        date: Date of the calibration session.
        technician: Name of the technician performing calibration.
        temperature_c: Ambient temperature in degrees Celsius.
        humidity_pct: Relative humidity percentage.
        notes: Optional session notes.
    """
    instrument_id: UUID
    date: date
    technician: str
    temperature_c: float
    humidity_pct: float
    notes: Optional[str] = None


class ReadingCreate(BaseModel):
    """Pydantic model for creating a calibration reading record.

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
        cmc: Claimed measurement capability.
        combined_uncertainty: Root sum of squares of all components.
        expanded_uncertainty: Combined uncertainty multiplied by coverage factor.
        k_value: Coverage factor.
        final_applied_uncertainty: Larger of expanded uncertainty and CMC.
    """
    session_id: UUID
    type_a_value: float
    u_std: float
    u_res: float
    u_hys: float
    u_head: Optional[float] = None
    u_zero: float
    u_temp: float
    cmc: float
    combined_uncertainty: float
    expanded_uncertainty: float
    k_value: float
    final_applied_uncertainty: float