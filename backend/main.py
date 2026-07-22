from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uuid import UUID
import httpx

from config import settings
from auth import get_current_user_id, require_tier
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
    ProfileUpdate,
    RoleChangeRequestCreate,
    RoleChangeReviewDecision,
    SessionReviewDecision,
    REQUESTABLE_TITLES,
)
import database
from modules import validation, reporting, formula_manager

app = FastAPI(title="Calibration Uncertainty Calculator API")

# Exact wording as specified by Instruworks (via Jinelle, July 2026) - the
# standard message shown to whoever owns a session when a QM/TM/MR/MD
# rejects it on review. Do not paraphrase without checking with them first.
SESSION_REJECTED_MESSAGE = (
    "Attention: Some readings or calibration inputs may not be accurate. Please cross-check the data "
    "and consult the concerned HOD for verification and approval."
)

# CORS is configured here and nowhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    # In addition to the exact-match list above (which always includes
    # localhost:3000 - see config.py), allow ANY localhost port during
    # local dev. Create React App silently bumps to 3001, 3002, etc.
    # whenever the previous port is already taken (e.g. another dev
    # server still running), and the hardcoded exact-match fallback only
    # ever covered 3000 - causing a real, reproducible bug where a
    # developer's OWN machine rejects its OWN frontend with a genuine
    # (not masked-crash) CORS 400, purely because of which port happened
    # to be free that day. Safe as a regex here specifically because it's
    # scoped to localhost - an attacker already on the developer's own
    # machine has bigger problems than CORS.
    allow_origin_regex=r"^http://localhost:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(httpx.TransportError)
async def handle_supabase_transport_error(request, exc: httpx.TransportError):
    """Recover from a stale/terminated Supabase connection automatically,
    instead of requiring a manual server restart.

    database.supabase caches one real client (and its one underlying
    HTTP/2 connection pool) for the entire lifetime of the server process
    - see _LazySupabaseClient's docstring. If Supabase's end terminates a
    pooled connection without httpx noticing (idle timeout, load balancer
    recycling, a laptop sleep/wake, a brief network drop), every request
    reusing it fails with an httpx.TransportError subclass (most often
    RemoteProtocolError('ConnectionTerminated')) - previously an
    unhandled exception type that crashed past FastAPI's normal response
    handling and, as a side effect, past CORSMiddleware's header
    injection too - which is why this could look like a CORS error in
    the browser rather than what it actually was.

    Registering a real exception handler means this now goes through the
    normal FastAPI response path (so CORS headers ARE attached correctly),
    and resetting the cached client means the very next request gets a
    fresh connection pool rather than hitting the same dead connection
    again - no restart needed.
    """
    database.supabase.reset()
    return JSONResponse(
        status_code=503,
        content={"detail": "Temporary connection issue reaching the database. Please try again."},
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


@app.get("/api/sessions/flagged")
def list_flagged_sessions(user_id: str = Depends(require_tier("full_edit"))):
    """List every session currently awaiting review, across all users.
    The reviewer's queue - restricted to full_edit tier only.

    Registration order matters here: this must be declared before
    GET /api/sessions/{session_id} below, or FastAPI would try to parse
    "flagged" as a session_id UUID and 422 instead of matching this route.

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Session records with review_status == "pending_review".
    """
    return database.list_flagged_sessions()


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
    user_id: str = Depends(require_tier("full_edit", "cert_creation")),
):
    """Create a new master instrument record.

    Restricted to full_edit and cert_creation tiers (i.e. not Viewer) -
    master instruments are the calibration standards everything else's
    uncertainty is measured against, so letting a read-only account add
    or remove them was a real governance gap, not just a visibility one.

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
    user_id: str = Depends(require_tier("full_edit", "cert_creation")),
):
    """Delete a master instrument. Restricted to full_edit and
    cert_creation tiers (not Viewer) - see create_master_instrument's
    docstring for why."""
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

# ── Profiles / Roles ──────────────────────────────────────────────────────────

@app.get("/api/profile")
def get_my_profile(user_id: str = Depends(get_current_user_id)):
    """Fetch the current user's own profile (name, title).

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The profile record. If none exists yet (e.g. an account
            created before profiles existed), returns a default Viewer
            shape rather than 404 - a missing profile isn't an error
            case here, see auth.get_current_user_title's docstring.
    """
    profile = database.get_profile(user_id)
    if profile is None:
        return {"id": user_id, "full_name": None, "title": "Viewer"}
    return profile


@app.put("/api/profile")
def update_my_profile(payload: ProfileUpdate, user_id: str = Depends(get_current_user_id)):
    """Update the current user's own profile fields.

    Title and is_active are deliberately not editable here - see
    ProfileUpdate's docstring. Title changes only happen via an approved
    role-change request; deactivation only via the dedicated endpoints
    below.

    Args:
        payload: The fields being changed (any subset).
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The updated profile record.
    """
    return database.update_profile(
        user_id,
        full_name=payload.full_name,
        employee_id=payload.employee_id,
        site_location=payload.site_location,
        department=payload.department,
    )


@app.put("/api/profile/deactivate")
def deactivate_my_account(user_id: str = Depends(get_current_user_id)):
    """Self-service "delete account" - actually deactivates rather than
    deletes. Historical data (instruments, sessions, certificates) this
    user created is completely unaffected; only their own ability to log
    in and act is revoked (enforced in auth.get_current_user_id on every
    subsequent request). A full_edit-tier user can reactivate the
    account later via PUT /api/profiles/{user_id}/reactivate.

    A true delete of the auth.users row was deliberately not implemented
    - see the 2026-07-19b migration's docstring for why.

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.update_profile(user_id, is_active=False)
    return {"message": "Your account has been deactivated."}


@app.put("/api/profiles/{target_user_id}/deactivate")
def deactivate_user_account(
    target_user_id: str,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Deactivate another user's account. Restricted to full_edit tier
    only - e.g. for someone who's left the organization and can't
    deactivate themselves.

    Args:
        target_user_id: UUID of the account to deactivate.
        reviewer_id: UUID of the full-edit-tier user doing this, from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.update_profile(target_user_id, is_active=False)
    return {"message": "Account deactivated."}


@app.put("/api/profiles/{target_user_id}/reactivate")
def reactivate_user_account(
    target_user_id: str,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Reactivate a previously deactivated account. Restricted to
    full_edit tier only.

    Args:
        target_user_id: UUID of the account to reactivate.
        reviewer_id: UUID of the full-edit-tier user doing this, from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.update_profile(target_user_id, is_active=True)
    return {"message": "Account reactivated."}


@app.get("/api/profiles")
def list_all_profiles(user_id: str = Depends(require_tier("full_edit"))):
    """List every user's profile - the full-edit tier's "see all activity"
    view. Restricted to full_edit (QM/TM/MR/MD) only.

    Args:
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: All profile records.
    """
    return database.list_profiles()


# ── Role change requests ────────────────────────────────────────────────────

@app.post("/api/role-requests")
def create_role_change_request(
    payload: RoleChangeRequestCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Submit a request to be granted a different job title.

    Any authenticated user may submit one - this is the self-service path
    for a Viewer to request Cal Tech/Engineer/etc. access (or any title
    requesting any other; not restricted to "upward" requests only). Only
    one pending request per user at a time - a denied request can always
    be resubmitted, this only blocks a second SIMULTANEOUS pending one.

    Args:
        payload: The requested title and an optional reason.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        dict: The created request record.

    Raises:
        HTTPException: 400 if requested_title isn't a valid title, or if
            the user already has a pending request.
    """
    if payload.requested_title not in REQUESTABLE_TITLES:
        raise HTTPException(
            status_code=400,
            detail=f"'{payload.requested_title}' is not a requestable title. Must be one of: {', '.join(REQUESTABLE_TITLES)}.",
        )
    existing = database.get_pending_role_change_request_for_user(user_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending role-change request. Wait for it to be reviewed before submitting another.",
        )
    return database.insert_role_change_request({
        "user_id": user_id,
        "requested_title": payload.requested_title,
        "reason": payload.reason,
    })


@app.get("/api/role-requests")
def list_role_change_requests(
    status: str = None,
    user_id: str = Depends(require_tier("full_edit")),
):
    """List role-change requests. Restricted to full_edit tier only.

    Args:
        status: Optional filter ("pending", "approved", "denied"). If
            omitted, returns all requests regardless of status.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        list: Matching request records.
    """
    return database.list_role_change_requests(status)


@app.put("/api/role-requests/{request_id}/approve")
def approve_role_change_request(
    request_id: UUID,
    payload: RoleChangeReviewDecision,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Approve a pending role-change request, applying the new title to
    the requester's profile. Restricted to full_edit tier only.

    Args:
        request_id: UUID of the role_change_requests row.
        payload: Optional reviewer note.
        reviewer_id: UUID of the full-edit-tier user approving this,
            from JWT.

    Returns:
        dict: A confirmation message.

    Raises:
        HTTPException: 404 if the request doesn't exist.
    """
    requests = database.list_role_change_requests()
    match = next((r for r in requests if r["id"] == str(request_id)), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Role change request not found.")
    database.update_role_change_request(str(request_id), "approved", reviewer_id)
    database.update_profile(match["user_id"], title=match["requested_title"])
    return {"message": f"Approved. User's title is now {match['requested_title']}."}


@app.put("/api/role-requests/{request_id}/deny")
def deny_role_change_request(
    request_id: UUID,
    payload: RoleChangeReviewDecision,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Deny a pending role-change request. The requester's profile is
    unaffected, and they may submit a new request afterward (denial isn't
    permanent). Restricted to full_edit tier only.

    Args:
        request_id: UUID of the role_change_requests row.
        payload: Optional reviewer note explaining the denial.
        reviewer_id: UUID of the full-edit-tier user denying this, from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.update_role_change_request(str(request_id), "denied", reviewer_id)
    return {"message": "Request denied."}


# ── Session review workflow ──────────────────────────────────────────────────

@app.put("/api/sessions/{session_id}/review/approve")
def approve_session_review(
    session_id: UUID,
    payload: SessionReviewDecision,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Approve a session that was flagged by check_master_instrument_validity,
    unblocking certificate generation. Restricted to full_edit tier only.

    Args:
        session_id: UUID of the calibration session.
        payload: Optional replacement review note.
        reviewer_id: UUID of the full-edit-tier user approving, from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.resolve_session_review(str(session_id), approved=True, reviewed_by=reviewer_id, review_note=payload.review_note)
    return {"message": "Session approved. Certificate generation is unblocked."}


@app.put("/api/sessions/{session_id}/review/reject")
def reject_session_review(
    session_id: UUID,
    payload: SessionReviewDecision,
    reviewer_id: str = Depends(require_tier("full_edit")),
):
    """Reject a flagged session. Certificate generation stays blocked;
    review_note (if provided) tells the original technician what to fix.
    Restricted to full_edit tier only.

    Args:
        session_id: UUID of the calibration session.
        payload: Optional rejection reason.
        reviewer_id: UUID of the full-edit-tier user rejecting, from JWT.

    Returns:
        dict: A confirmation message.
    """
    database.resolve_session_review(str(session_id), approved=False, reviewed_by=reviewer_id, review_note=payload.review_note)
    return {"message": "Session rejected."}


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
    # Clear any existing test for this exact (session, test_point) before
    # inserting the fresh one - without this, resubmitting the same test
    # point (e.g. correcting a typo and re-saving) stacked a second full
    # test+readings set on top of the first every time, rather than
    # replacing it. Only this test_point is cleared, not the whole
    # session's repeatability tests, since other test points must survive.
    database.delete_weighing_repeatability_test_by_key(str(session_id), test_data["test_point"])
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
    # Clear any existing off-center readings for this session before
    # re-inserting - without this, resubmitting stacked a duplicate set
    # of 5 rows on top of the existing ones every time (the same root
    # cause originally fixed for Pressure's ReadingsForm.jsx).
    database.delete_weighing_off_center_readings(str(session_id))
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
    # Same fix as off-center, above.
    database.delete_weighing_hysteresis_readings(str(session_id))
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
    # Same fix as create_weighing_repeatability_test above - clear only
    # this setpoint before inserting, so other setpoints already on
    # record for this session survive.
    database.delete_temperature_repeatability_test_by_key(str(session_id), test_data["setpoint_label"])
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
    # Same fix as the Weighing/Temperature endpoints above - clear only
    # this (function_type, range_label) combination before inserting, so
    # other function-type/range tests already on record survive.
    database.delete_electrical_test_by_key(str(session_id), test_data["function_type"], test_data["range_label"])
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

    Exception-based review gate: the master instrument used for this
    session is checked for validity (see
    validation.check_master_instrument_validity) the first time a report
    is requested for a session that hasn't been checked yet. A clean
    result generates the certificate immediately, exactly as before this
    workflow existed - most sessions never touch review_status beyond its
    "clean" default. A failing check flags the session (review_status
    becomes "pending_review") and blocks generation until a full_edit-tier
    user approves or rejects it via /api/sessions/{id}/review/approve or
    /reject - see main.py's Session review workflow section.

    Args:
        session_id: UUID of the calibration session.
        format: Report format, either pdf or excel.
        user_id: UUID of the authenticated user from JWT.

    Returns:
        FileResponse: The generated report file.

    Raises:
        HTTPException: 400 if the session is rejected or format is invalid.
        HTTPException: 403 if the session is flagged and awaiting
            full-edit-tier review, or was reviewed and rejected.
        HTTPException: 404 if required data is missing.
    """
    session_record = database.get_session(str(session_id))
    if session_record is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    review_status = session_record.get("review_status", "clean")

    if review_status == "clean":
        issues = validation.check_master_instrument_validity(str(session_id))
        if issues:
            database.flag_session_for_review(str(session_id), review_note=" ".join(issues))
            raise HTTPException(
                status_code=403,
                detail=(
                    "This session has been flagged for review before a certificate can be "
                    f"generated: {' '.join(issues)} A QM/TM/MR/MD needs to approve it first."
                ),
            )
    elif review_status == "pending_review":
        raise HTTPException(
            status_code=403,
            detail=f"This session is awaiting review before a certificate can be generated: {session_record.get('review_note', '')}",
        )
    elif review_status == "rejected":
        detail = SESSION_REJECTED_MESSAGE
        if session_record.get("review_note"):
            detail += f" (Reviewer note: {session_record['review_note']})"
        raise HTTPException(status_code=403, detail=detail)
    # review_status == "approved" falls through and generates normally.

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