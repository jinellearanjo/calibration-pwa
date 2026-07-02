from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from uuid import UUID

from config import settings
from auth import get_current_user_id
from models import (
    InstrumentCreate,
    CalibrationSessionCreate,
    ReadingCreate,
    MasterInstrumentCreate,
    CalibrationReferenceCreate,
    UncertaintyBudgetCreate,
    WeighingRepeatabilityTestCreate,
    WeighingRepeatabilityReadingCreate,
    WeighingOffCenterReadingCreate,
    WeighingHysteresisReadingCreate,
)
import database
from modules import validation, reporting

app = FastAPI(title="Calibration Uncertainty Calculator API")

# CORS is configured here and nowhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Check that the API is running.

    Returns:
        dict: A status message confirming the API is healthy.
    """
    return {"status": "ok"}


# ── Instruments ───────────────────────────────────────────────────────────────

@app.post("/api/instruments")
def create_instrument(
    payload: InstrumentCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new instrument record for the authenticated user.

    Args:
        payload: Instrument fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created instrument record.
    """
    data = payload.dict()
    data["user_id"] = user_id
    response = database.supabase.table("instruments").insert(data).execute()
    return response.data


@app.get("/api/instruments/{instrument_id}")
def get_instrument(
    instrument_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch a single instrument by ID.

    Args:
        instrument_id: UUID of the instrument.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The instrument record.

    Raises:
        HTTPException: 404 if the instrument is not found.
    """
    record = database.get_instrument(str(instrument_id))
    if not record:
        raise HTTPException(status_code=404, detail="Instrument not found.")
    return record


# ── Calibration Sessions ──────────────────────────────────────────────────────

@app.post("/api/sessions")
def create_session(
    payload: CalibrationSessionCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new calibration session.

    Args:
        payload: Session fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created session record.
    """
    data = payload.dict()
    data["user_id"] = user_id
    data["status"] = "PENDING"
    # Convert date and UUID fields to strings for Supabase.
    data["instrument_id"] = str(data["instrument_id"])
    data["date"] = str(data["date"])
    if data.get("master_instrument_id") is not None:
        data["master_instrument_id"] = str(data["master_instrument_id"])
    response = database.supabase.table("calibration_sessions").insert(data).execute()
    return response.data


@app.get("/api/sessions")
def list_sessions(user_id: str = Depends(get_current_user_id)):
    """List all calibration sessions for the authenticated user.

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: All session records for the user.
    """
    response = database.supabase.table("calibration_sessions").select(
        "*, instruments(name)"
    ).eq("user_id", user_id).order("created_at", desc=True).execute()
    return response.data


@app.get("/api/sessions/{session_id}")
def get_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch a single calibration session by ID.

    Args:
        session_id: UUID of the session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The session record.

    Raises:
        HTTPException: 404 if the session is not found.
    """
    record = database.get_session(str(session_id))
    if not record:
        raise HTTPException(status_code=404, detail="Session not found.")
    return record


# ── Calibration Reference ─────────────────────────────────────────────────────

@app.post("/api/calibration-reference")
def create_calibration_reference(
    payload: CalibrationReferenceCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a calibration reference record for a session.

    Args:
        payload: Calibration reference fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created calibration reference record.
    """
    data = payload.dict()
    data["session_id"] = str(data["session_id"])
    for date_field in ["date_of_calibration", "cal_due_date", "item_received_date", "date_of_issue"]:
        data[date_field] = str(data[date_field])
    response = database.supabase.table("calibration_reference").insert(data).execute()
    return response.data


# ── Readings ──────────────────────────────────────────────────────────────────
# Used by Pressure, Temperature, and Electrical sessions. See the Weighing
# section below for the three test-specific endpoints Weighing sessions use
# instead.

@app.post("/api/readings")
def create_reading(
    payload: ReadingCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a single calibration reading record.

    Args:
        payload: Reading fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created reading record.
    """
    data = payload.dict()
    data["session_id"] = str(data["session_id"])
    response = database.supabase.table("readings").insert(data).execute()
    return response.data


@app.get("/api/sessions/{session_id}/readings")
def get_session_readings(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch all readings for a calibration session.

    Args:
        session_id: UUID of the session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: All reading records for the session ordered by point number.
    """
    return database.get_readings(str(session_id))


# ── Master Instruments ────────────────────────────────────────────────────────

@app.post("/api/master-instruments")
def create_master_instrument(
    payload: MasterInstrumentCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new master instrument record.

    Args:
        payload: Master instrument fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created master instrument record.
    """
    data = payload.dict()
    data["user_id"] = user_id
    data["cal_due_date"] = str(data["cal_due_date"])
    response = database.supabase.table("master_instruments").insert(data).execute()
    return response.data


@app.get("/api/master-instruments")
def list_master_instruments(user_id: str = Depends(get_current_user_id)):
    """List all master instruments for the authenticated user.

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: All master instrument records for the user.
    """
    response = database.supabase.table("master_instruments").select("*").eq(
        "user_id", user_id
    ).execute()
    return response.data


@app.get("/api/master-instruments/{master_id}")
def get_master_instrument(
    master_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch a single master instrument by ID.

    Args:
        master_id: UUID of the master instrument.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The master instrument record.

    Raises:
        HTTPException: 404 if the master instrument is not found.
    """
    record = database.get_master_instrument(str(master_id))
    if not record:
        raise HTTPException(status_code=404, detail="Master instrument not found.")
    return record


@app.delete("/api/master-instruments/{master_id}")
def delete_master_instrument(
    master_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a master instrument record.

    Args:
        master_id: UUID of the master instrument.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: Confirmation message.
    """
    database.supabase.table("master_instruments").delete().eq(
        "id", str(master_id)
    ).execute()
    return {"message": "Master instrument deleted."}


# ── Uncertainty Budgets ───────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/budget")
def create_uncertainty_budget(
    session_id: UUID,
    payload: UncertaintyBudgetCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create an uncertainty budget for a session.

    Args:
        session_id: UUID of the calibration session.
        payload: Uncertainty budget fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created uncertainty budget record.
    """
    data = payload.dict()
    data["session_id"] = str(session_id)
    return database.insert_uncertainty_budget(data)


@app.get("/api/sessions/{session_id}/budget")
def get_uncertainty_budget(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch the uncertainty budget for a session.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The uncertainty budget record.

    Raises:
        HTTPException: 404 if no budget exists for this session.
    """
    record = database.get_uncertainty_budget(str(session_id))
    if not record:
        raise HTTPException(status_code=404, detail="Uncertainty budget not found.")
    return record


# ── Weighing: Repeatability test ────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/weighing/repeatability")
def create_weighing_repeatability_test(
    session_id: UUID,
    payload: WeighingRepeatabilityTestCreate,
    readings: list[WeighingRepeatabilityReadingCreate],
    user_id: str = Depends(get_current_user_id),
):
    """Create a weighing repeatability test and its 10 readings together.

    Args:
        session_id: UUID of the calibration session.
        payload: Test-level fields (test_point, nominal_load, unit,
            standard_weights_uncertainty).
        readings: The 10 individual readings for this test point.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created test record with its readings nested under
            "readings".

    Raises:
        HTTPException: 400 if fewer or more than 10 readings are supplied.
    """
    if len(readings) != 10:
        raise HTTPException(
            status_code=400,
            detail=f"Repeatability test requires exactly 10 readings, got {len(readings)}.",
        )

    test_data = payload.dict()
    test_data["session_id"] = str(session_id)
    test_record = database.insert_weighing_repeatability_test(test_data)
    test_id = test_record[0]["id"]

    reading_rows = []
    for r in readings:
        row = r.dict()
        row["test_id"] = test_id
        reading_rows.append(row)
    reading_records = database.insert_weighing_repeatability_readings(reading_rows)

    return {**test_record[0], "readings": reading_records}


@app.get("/api/sessions/{session_id}/weighing/repeatability")
def get_weighing_repeatability_tests(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch all repeatability tests (with readings) for a session.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Repeatability test records with nested readings.
    """
    return database.get_weighing_repeatability_tests(str(session_id))


# ── Weighing: Off-center test ────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/weighing/off-center")
def create_weighing_off_center_readings(
    session_id: UUID,
    readings: list[WeighingOffCenterReadingCreate],
    user_id: str = Depends(get_current_user_id),
):
    """Create the 5 off-center position readings for a session.

    Args:
        session_id: UUID of the calibration session.
        readings: The 5 readings, one per position (center/front/back/left/right).
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: The created off-center reading records.

    Raises:
        HTTPException: 400 if not exactly 5 readings are supplied.
    """
    if len(readings) != 5:
        raise HTTPException(
            status_code=400,
            detail=f"Off-center test requires exactly 5 readings, got {len(readings)}.",
        )

    rows = []
    for r in readings:
        row = r.dict()
        row["session_id"] = str(session_id)
        rows.append(row)
    return database.insert_weighing_off_center_readings(rows)


@app.get("/api/sessions/{session_id}/weighing/off-center")
def get_weighing_off_center_readings(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch all off-center readings for a session.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Off-center reading records.
    """
    return database.get_weighing_off_center_readings(str(session_id))


# ── Weighing: Hysteresis test ────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/weighing/hysteresis")
def create_weighing_hysteresis_readings(
    session_id: UUID,
    readings: list[WeighingHysteresisReadingCreate],
    user_id: str = Depends(get_current_user_id),
):
    """Create the 5-step hysteresis sequence readings for a session.

    Args:
        session_id: UUID of the calibration session.
        readings: The 5 readings in sequence order 1-5.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: The created hysteresis reading records.

    Raises:
        HTTPException: 400 if not exactly 5 readings are supplied.
    """
    if len(readings) != 5:
        raise HTTPException(
            status_code=400,
            detail=f"Hysteresis test requires exactly 5 readings, got {len(readings)}.",
        )

    rows = []
    for r in readings:
        row = r.dict()
        row["session_id"] = str(session_id)
        rows.append(row)
    return database.insert_weighing_hysteresis_readings(rows)


@app.get("/api/sessions/{session_id}/weighing/hysteresis")
def get_weighing_hysteresis_readings(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch all hysteresis sequence readings for a session, in order.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Hysteresis reading records ordered by sequence_order.
    """
    return database.get_weighing_hysteresis_readings(str(session_id))


# ── Validation ────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/validate")
def validate_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Validate a calibration session and return the compliance result.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: Validation result with status, uncertainty values, and flags.

    Raises:
        HTTPException: 400 if validation cannot be completed.
    """
    try:
        return validation.validate_session(str(session_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Reports ───────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/report")
def generate_report(
    session_id: UUID,
    format: str = "pdf",
    user_id: str = Depends(get_current_user_id),
):
    """Generate and download a calibration certificate.

    Args:
        session_id: UUID of the calibration session.
        format: Report format, either pdf or excel.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        FileResponse: The generated report file.

    Raises:
        HTTPException: 400 if the session is rejected or format is invalid.
        HTTPException: 404 if required data is missing.
    """
    try:
        if format == "pdf":
            return reporting.generate_pdf_report(str(session_id))
        elif format == "excel":
            return reporting.generate_excel_report(str(session_id))
        else:
            raise HTTPException(status_code=400, detail="Format must be pdf or excel.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))