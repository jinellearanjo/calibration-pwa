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
    TemperatureRepeatabilityTestCreate,
    TemperatureRepeatabilityReadingCreate,
    ElectricalTestCreate,
    ElectricalReadingCreate,
)
import database
from modules import validation, reporting, formula_manager

app = FastAPI(title="Calibration Uncertainty Calculator API")

# CORS is configured here and nowhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_instrument_type(session_id: str, expected_type: str) -> None:
    """Guard against submitting category-specific test data (Weighing/
    Temperature/Electrical repeatability, or a Pressure reading) for a
    session whose actual instrument doesn't match that category.

    This exists because SessionPicker.jsx (used as a fallback whenever a
    readings page is reached without a :sessionId in the URL, e.g. via a
    Dashboard card) lists every session for the user with no filtering by
    category - so nothing on the frontend actually stops someone from
    landing on, say, the Weighing readings page and picking a Temperature
    session from the dropdown. Without this guard, that would silently
    insert Weighing test rows against a session whose instrument is
    Temperature, corrupting the session's data with no error at all.

    Args:
        session_id: UUID (as a string) of the calibration session.
        expected_type: The category this endpoint is for - one of
            "Pressure", "Temperature", "Weighing", "Electrical".

    Raises:
        HTTPException: 404 if the session or its instrument can't be
            found; 400 if the instrument's actual type doesn't match
            expected_type.
    """
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    instrument = database.get_instrument(session["instrument_id"])
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found for this session.")
    actual_type = instrument.get("type")
    if actual_type != expected_type:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This session's instrument is type '{actual_type}', not "
                f"'{expected_type}'. Cannot submit {expected_type} test data "
                f"for a session whose instrument category doesn't match."
            ),
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
    data = payload.model_dump()
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


@app.delete("/api/instruments/{instrument_id}")
def delete_instrument(
    instrument_id: UUID,
    cascade: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """Delete an instrument.

    By default, blocks deletion if any calibration session references
    this instrument - same safety pattern as delete_master_instrument
    below. Pass ?cascade=true to also delete every referencing session
    (and all of that session's nested readings/tests/budgets) along with
    the instrument in one action.

    Args:
        instrument_id: UUID of the instrument to delete.
        cascade: If true, also delete every session referencing this
            instrument (and all of that session's nested data) first.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: A confirmation message.

    Raises:
        HTTPException: 400 if the instrument is referenced by one or more
            sessions and cascade was not set to true; 500 if any delete
            query fails.
    """
    linked = database.supabase.table("calibration_sessions").select("id").eq(
        "instrument_id", str(instrument_id)
    ).execute()
    if linked.data and not cascade:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete this instrument — it is referenced by "
                f"{len(linked.data)} calibration session(s). Pass "
                f"?cascade=true to delete those sessions (and all their "
                f"test data) along with the instrument."
            ),
        )
    try:
        if cascade:
            database.delete_instrument_cascade(str(instrument_id))
        else:
            database.supabase.table("instruments").delete().eq(
                "id", str(instrument_id)
            ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")
    return {"message": "Instrument deleted."}


@app.put("/api/instruments/{instrument_id}")
def update_instrument(
    instrument_id: UUID,
    payload: InstrumentCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing instrument record.

    Reuses InstrumentCreate (same shape as the create payload) rather than
    a separate partial-update model - matches the frontend's edit form,
    which pre-fills every field and resubmits the whole record, same
    pattern as update_session/update_calibration_reference below.

    Args:
        instrument_id: UUID of the instrument to update.
        payload: Updated instrument fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The updated instrument record.

    Raises:
        HTTPException: 404 if the instrument is not found.
        HTTPException: 500 if the update query fails.
    """
    existing = database.get_instrument(str(instrument_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Instrument not found.")
    data = payload.model_dump()
    try:
        response = database.supabase.table("instruments").update(data).eq(
            "id", str(instrument_id)
        ).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Update returned no data.")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


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
    data = payload.model_dump()
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
        "*, instruments(name, type)"
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


@app.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a calibration session and all of its nested data (readings,
    tests, uncertainty budgets, calibration reference) across every
    instrument category, via database.delete_calibration_session_cascade.

    Does NOT delete the instrument itself - the underlying instrument
    registration may still be worth keeping even if this particular test
    attempt is being discarded. Use DELETE /api/instruments/{id}?cascade=true
    to remove the instrument along with all of its sessions in one action.

    Args:
        session_id: UUID of the session to delete.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: A confirmation message.

    Raises:
        HTTPException: 500 if any delete query fails.
    """
    try:
        database.delete_calibration_session_cascade(str(session_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")
    return {"message": "Session and all associated test data deleted."}


@app.put("/api/sessions/{session_id}")
def update_session(
    session_id: UUID,
    payload: CalibrationSessionCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing calibration session record.

    Only updates the session metadata (date, technician, environmental
    conditions, master_instrument_id). Does not touch readings, budgets,
    or validation status - those have their own endpoints.

    Note: editing temperature_c/humidity_pct after a budget has already
    been calculated does not invalidate or recalculate that budget -
    Pressure's u_temp component is derived from these values at
    calculate time, not re-derived on session edit. If environmental
    conditions are corrected after calculation, the session should be
    recalculated to keep the budget consistent - not automated here since
    silently recalculating could overwrite a result someone is actively
    reviewing.

    Args:
        session_id: UUID of the session to update.
        payload: Updated session fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The updated session record.

    Raises:
        HTTPException: 404 if the session is not found.
        HTTPException: 500 if the update query fails.
    """
    existing = database.get_session(str(session_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found.")
    data = payload.model_dump()
    data["instrument_id"] = str(data["instrument_id"])
    data["date"] = str(data["date"])
    if data.get("master_instrument_id") is not None:
        data["master_instrument_id"] = str(data["master_instrument_id"])
    try:
        response = database.supabase.table("calibration_sessions").update(data).eq(
            "id", str(session_id)
        ).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Update returned no data.")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


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
    data = payload.model_dump()
    data["session_id"] = str(data["session_id"])
    for date_field in ["date_of_calibration", "cal_due_date", "item_received_date", "date_of_issue"]:
        data[date_field] = str(data[date_field])
    response = database.supabase.table("calibration_reference").insert(data).execute()
    return response.data


@app.put("/api/calibration-reference/{session_id}")
def update_calibration_reference(
    session_id: UUID,
    payload: CalibrationReferenceCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing calibration reference record for a session.

    Args:
        session_id: UUID of the session whose calibration reference
            should be updated.
        payload: Updated calibration reference fields from the request body.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The updated calibration reference record.

    Raises:
        HTTPException: 404 if no calibration reference exists for this session.
        HTTPException: 500 if the update query fails.
    """
    existing = database.get_calibration_reference(str(session_id))
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="No calibration reference found for this session."
        )
    data = payload.model_dump()
    data["session_id"] = str(data["session_id"])
    for date_field in ["date_of_calibration", "cal_due_date", "item_received_date", "date_of_issue"]:
        data[date_field] = str(data[date_field])
    try:
        response = database.supabase.table("calibration_reference").update(data).eq(
            "session_id", str(session_id)
        ).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Update returned no data.")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@app.get("/api/calibration-reference-by-session/{session_id}")
def get_calibration_reference_by_session(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch the calibration reference record for a session (used by
    InstrumentForm.jsx's edit mode to pre-fill Section 1).

    Args:
        session_id: UUID of the session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The calibration reference record.

    Raises:
        HTTPException: 404 if no calibration reference exists for this session -
            expected and non-fatal on the frontend for a session that was
            created but never had Section 1 (certificate/customer details)
            filled in yet.
    """
    record = database.get_calibration_reference(str(session_id))
    if not record:
        raise HTTPException(
            status_code=404,
            detail="No calibration reference found for this session."
        )
    return record


# ── Readings ──────────────────────────────────────────────────────────────────
# Used by Pressure sessions only. Temperature, Electrical, and Weighing each
# have their own dedicated tables/endpoints (see the sections below) - this
# comment previously claimed Temperature/Electrical used this generic table
# too, which was already flagged and fixed once before; re-confirmed false
# by reading formula_manager.py's dispatch logic directly.

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

    Raises:
        HTTPException: 404 if the session/instrument can't be found; 400
            if the session's instrument isn't a Pressure instrument.
    """
    data = payload.model_dump()
    data["session_id"] = str(data["session_id"])
    _require_instrument_type(data["session_id"], "Pressure")
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


@app.delete("/api/sessions/{session_id}/readings")
def delete_session_readings(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Delete all readings for a calibration session.

    Called by the frontend immediately before resubmitting a fresh set
    of readings (see ReadingsForm.jsx's submit handler), so resubmitting
    the same session doesn't stack duplicate rows on top of whatever's
    already there - the exact bug already found and fixed once for
    uncertainty_budgets (Round 10) but never extended to readings
    themselves until now.

    Args:
        session_id: UUID of the session whose readings should be cleared.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: A confirmation message.

    Raises:
        HTTPException: 500 if the delete query fails.
    """
    try:
        database.delete_readings(str(session_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")
    return {"message": "Readings deleted."}


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
    data = payload.model_dump()
    data["user_id"] = user_id
    data["cal_due_date"] = str(data["cal_due_date"])
    response = database.supabase.table("master_instruments").insert(data).execute()
    return response.data


@app.get("/api/master-instruments")
def list_master_instruments(user_id: str = Depends(get_current_user_id)):
    """List all master instruments.

    Master instruments are shared physical lab assets, not personal to
    whoever registered them - two technicians logged in as different
    users both need to see and select the same physical Dead Weight
    Tester, Fluke 5560A, etc. So visibility is intentionally NOT scoped
    to the creator, unlike instruments/calibration_sessions which are
    per-user. user_id is still recorded on creation (see
    create_master_instrument) purely for an audit trail of who
    registered each asset - it does not gate who can see it.

    Args:
        user_id: UUID of the authenticated user from JWT (required for
            auth, not used to filter results here).

    Returns:
        list: Every master instrument record, regardless of creator.
    """
    response = database.supabase.table("master_instruments").select("*").execute()
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
    linked = database.supabase.table("calibration_sessions").select("id").eq(
        "master_instrument_id", str(master_id)
    ).execute()
    if linked.data:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete this master instrument — it is referenced by "
                f"{len(linked.data)} calibration session(s). Remove or reassign "
                f"those sessions before deleting the master instrument."
            ),
        )
    try:
        database.supabase.table("master_instruments").delete().eq(
            "id", str(master_id)
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")
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
    data = payload.model_dump()
    data["session_id"] = str(session_id)
    return database.insert_uncertainty_budget(data)


@app.get("/api/sessions/{session_id}/budget")
def get_uncertainty_budgets(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch ALL uncertainty budget rows for a session.

    Renamed from the old singular get_uncertainty_budget: Pressure and
    Weighing sessions still only ever have one budget, but Temperature
    (one per setpoint) and Electrical (one per function-type/range) can
    have several — always returns a list now, even when it's a list of one.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list[dict]: All uncertainty budget records for this session.
            Empty list (not a 404) if none have been calculated yet -
            "no budget calculated" is a normal state, not an error.
    """
    return database.get_uncertainty_budgets(str(session_id))


@app.post("/api/sessions/{session_id}/calculate")
def calculate_uncertainty_budget(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Calculate and store the uncertainty budget(s) for a session.

    Dispatches to the correct calculation logic based on the session's
    instrument type (see formula_manager.build_uncertainty_budget, which
    always returns a list — one item for Pressure/Weighing, one item per
    setpoint for Temperature, one item per function-type/range for
    Electrical). Every returned budget is inserted; if any single insert
    fails partway through, the ones already inserted are NOT rolled back
    (Supabase doesn't give this endpoint a multi-row transaction) - the
    session can simply be recalculated, since calculation is idempotent
    per setpoint/range and doesn't depend on order.

    Args:
        session_id: UUID of the calibration session to calculate for.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list[dict]: The calculated and stored uncertainty budget records,
            one per setpoint/range (or a list of one for Pressure/Weighing).

    Raises:
        HTTPException: 400 if the session, instrument, or master instrument
            can't be found, or if required data (readings, master instrument
            numeric fields, weighing/temperature/electrical test data) is
            missing or incomplete.
        HTTPException: 501 if the instrument's category doesn't have a
            calculation engine implemented yet (none currently — all four
            categories have calculation engines; Electrical's is newest).
    """
    try:
        budgets_data = formula_manager.build_uncertainty_budget(str(session_id))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Clear any existing budgets for this session before inserting the
    # freshly-calculated ones - without this, recalculating (e.g.
    # clicking "Recalculate" in CalculationView.jsx) would accumulate
    # duplicate rows every time, since insert_uncertainty_budget has no
    # dedup/upsert logic of its own. Deliberately done only after the
    # calculation above succeeds, so a failed recalculation doesn't wipe
    # out a session's last-known-good budgets.
    database.delete_uncertainty_budgets(str(session_id))

    # insert_uncertainty_budget returns response.data, which - like every
    # other insert_* function in database.py - is always a list even for
    # a single row (Supabase's own return shape). Every other caller of
    # these functions unwraps with [0] (see e.g. create_weighing_
    # repeatability_test's test_record[0]); this one previously didn't,
    # so the response sent to the frontend was doubly-nested
    # (a list of one-element lists instead of a flat list of budget
    # dicts) - CalculationView.jsx's Summary section has no null/undefined
    # filter on its fields (unlike the Components section, which does),
    # so it rendered the literal string "undefined" for every summary
    # value until a subsequent GET (which returns the correctly flat
    # shape) overwrote the broken state.
    return [database.insert_uncertainty_budget(b)[0] for b in budgets_data]


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
        HTTPException: 400 if fewer or more than 10 readings are supplied,
            or if the session's instrument isn't a Weighing instrument.
        HTTPException: 404 if the session/instrument can't be found.
    """
    _require_instrument_type(str(session_id), "Weighing")
    if len(readings) != 10:
        raise HTTPException(
            status_code=400,
            detail=f"Repeatability test requires exactly 10 readings, got {len(readings)}.",
        )

    test_data = payload.model_dump()
    test_data["session_id"] = str(session_id)
    test_record = database.insert_weighing_repeatability_test(test_data)
    # Guards against an empty insert response (e.g. an RLS SELECT policy
    # silently filtering the row back out despite a successful insert -
    # a known Supabase/PostgREST gotcha) turning into an opaque, unhandled
    # IndexError/500 rather than a clear error message. Verified this
    # codebase's insert_* functions have no such guard themselves.
    if not test_record:
        raise HTTPException(
            status_code=500,
            detail="Weighing repeatability test insert returned no data - the row may not have been created, or an RLS policy is hiding it from this response.",
        )
    test_id = test_record[0]["id"]

    reading_rows = []
    for r in readings:
        row = r.model_dump()
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
        HTTPException: 400 if not exactly 5 readings are supplied, or if
            the session's instrument isn't a Weighing instrument.
        HTTPException: 404 if the session/instrument can't be found.
    """
    _require_instrument_type(str(session_id), "Weighing")
    if len(readings) != 5:
        raise HTTPException(
            status_code=400,
            detail=f"Off-center test requires exactly 5 readings, got {len(readings)}.",
        )

    rows = []
    for r in readings:
        row = r.model_dump()
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
        HTTPException: 400 if not exactly 5 readings are supplied, or if
            the session's instrument isn't a Weighing instrument.
        HTTPException: 404 if the session/instrument can't be found.
    """
    _require_instrument_type(str(session_id), "Weighing")
    if len(readings) != 5:
        raise HTTPException(
            status_code=400,
            detail=f"Hysteresis test requires exactly 5 readings, got {len(readings)}.",
        )

    rows = []
    for r in readings:
        row = r.model_dump()
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


# ── Temperature: Repeatability test ──────────────────────────────────────────

@app.post("/api/sessions/{session_id}/temperature/repeatability")
def create_temperature_repeatability_test(
    session_id: UUID,
    payload: TemperatureRepeatabilityTestCreate,
    readings: list[TemperatureRepeatabilityReadingCreate],
    user_id: str = Depends(get_current_user_id),
):
    """Create a temperature repeatability test and its 3 readings together.

    Args:
        session_id: UUID of the calibration session.
        payload: Test-level fields (setpoint_label, nominal_temperature,
            unit, standard_uncertainty, standard_accuracy,
            drift_standard_uncertainty, hysteresis_value,
            bath_stability_value, bath_uniformity_value,
            wire_homogeneity_value).
        readings: The 3 individual readings for this setpoint.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created test record with its readings nested under "readings".

    Raises:
        HTTPException: 400 if fewer or more than 3 readings are supplied,
            or if the session's instrument isn't a Temperature instrument.
        HTTPException: 404 if the session/instrument can't be found.
    """
    _require_instrument_type(str(session_id), "Temperature")
    if len(readings) != 3:
        raise HTTPException(
            status_code=400,
            detail=f"Repeatability test requires exactly 3 readings, got {len(readings)}.",
        )

    test_data = payload.model_dump()
    test_data["session_id"] = str(session_id)
    test_record = database.insert_temperature_repeatability_test(test_data)
    # See the identical guard in create_weighing_repeatability_test above
    # for why this check exists.
    if not test_record:
        raise HTTPException(
            status_code=500,
            detail="Temperature repeatability test insert returned no data - the row may not have been created, or an RLS policy is hiding it from this response.",
        )
    test_id = test_record[0]["id"]

    reading_rows = []
    for r in readings:
        row = r.model_dump()
        row["test_id"] = test_id
        reading_rows.append(row)
    reading_records = database.insert_temperature_repeatability_readings(reading_rows)

    return {**test_record[0], "readings": reading_records}


@app.get("/api/sessions/{session_id}/temperature/repeatability")
def get_temperature_repeatability_tests(
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
    return database.get_temperature_repeatability_tests(str(session_id))


# ── Electrical: Test (one function-type/range) + readings ──────────────────

@app.post("/api/sessions/{session_id}/electrical/tests")
def create_electrical_test(
    session_id: UUID,
    payload: ElectricalTestCreate,
    readings: list[ElectricalReadingCreate],
    user_id: str = Depends(get_current_user_id),
):
    """Create an Electrical test (one function-type/range) and its readings together.

    Args:
        session_id: UUID of the calibration session.
        payload: Test-level fields (function_type, range_label,
            nominal_value, unit, cert_uncertainty_limit,
            calibrator_accuracy_limit, resolution, thermo_electric_limit,
            coil_accuracy_limit).
        readings: The repeated readings for this function-type/range.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created test record with its readings nested under "readings".

    Raises:
        HTTPException: 400 if no readings are supplied, or if the
            session's instrument isn't an Electrical instrument.
        HTTPException: 404 if the session/instrument can't be found.
    """
    _require_instrument_type(str(session_id), "Electrical")
    if not readings:
        raise HTTPException(
            status_code=400,
            detail="An Electrical test requires at least one reading.",
        )

    test_data = payload.model_dump()
    test_data["session_id"] = str(session_id)
    test_record = database.insert_electrical_test(test_data)
    # See the identical guard in create_weighing_repeatability_test above
    # for why this check exists.
    if not test_record:
        raise HTTPException(
            status_code=500,
            detail="Electrical test insert returned no data - the row may not have been created, or an RLS policy is hiding it from this response.",
        )
    test_id = test_record[0]["id"]

    reading_rows = []
    for r in readings:
        row = r.model_dump()
        row["test_id"] = test_id
        reading_rows.append(row)
    reading_records = database.insert_electrical_readings(reading_rows)

    return {**test_record[0], "readings": reading_records}


@app.get("/api/sessions/{session_id}/electrical/tests")
def get_electrical_tests(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch all Electrical tests (with readings) for a session.

    Args:
        session_id: UUID of the calibration session.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Electrical test records with nested readings.
    """
    return database.get_electrical_tests(str(session_id))


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