const BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

/**
 * Get the auth token from Supabase session for API requests.
 * @returns {Promise<string|null>} The JWT token or null if not logged in.
 */
async function getToken() {
  const { supabase } = await import("./auth");
  const { data } = await supabase.auth.getSession();
  return data?.session?.access_token || null;
}

/**
 * Make an authenticated request to the backend API.
 * @param {string} path - API path e.g. /api/sessions
 * @param {Object} options - Fetch options
 * @returns {Promise<any>} Parsed JSON response
 */
async function request(path, options = {}) {
  const token = await getToken();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(error.detail || "Request failed.");
  }
  return response.json();
}

// ── Instruments ───────────────────────────────────────────────────────────────

/**
 * Create a new instrument record.
 * @param {Object} data - Instrument fields matching the instruments table.
 * @returns {Promise<Object>} The created instrument record.
 */
export async function createInstrument(data) {
  return request("/api/instruments", { method: "POST", body: JSON.stringify(data) });
}

/**
 * Fetch a single instrument by ID.
 * @param {string} instrumentId - UUID of the instrument.
 * @returns {Promise<Object>} The instrument record.
 */
export async function getInstrument(instrumentId) {
  return request(`/api/instruments/${instrumentId}`);
}

/**
 * Delete an instrument, and (when cascade is true) every calibration
 * session referencing it along with all of that session's nested test
 * data. Without cascade, the backend returns a 400 if any session still
 * references this instrument.
 * @param {string} instrumentId - UUID of the instrument to delete.
 * @param {boolean} [cascade=true] - Also delete referencing sessions.
 * @returns {Promise<Object>} Confirmation message.
 */
export async function deleteInstrument(instrumentId, cascade = true) {
  return request(`/api/instruments/${instrumentId}?cascade=${cascade}`, { method: "DELETE" });
}

/**
 * Delete a calibration session and all of its nested data (readings,
 * tests, uncertainty budgets, calibration reference), across every
 * instrument category. Does not delete the instrument itself.
 * @param {string} sessionId - UUID of the session to delete.
 * @returns {Promise<Object>} Confirmation message.
 */
export async function deleteSession(sessionId) {
  return request(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

// ── Calibration Reference ─────────────────────────────────────────────────────

/**
 * Create a calibration reference record for a session.
 * @param {Object} data - Calibration reference fields.
 * @returns {Promise<Object>} The created record.
 */
export async function createCalibrationReference(data) {
  return request("/api/calibration-reference", { method: "POST", body: JSON.stringify(data) });
}

// ── Sessions ──────────────────────────────────────────────────────────────────

/**
 * Create a new calibration session.
 * @param {Object} data - Session fields matching the calibration_sessions table.
 * @returns {Promise<Object>} The created session record.
 */
export async function createSession(data) {
  return request("/api/sessions", { method: "POST", body: JSON.stringify(data) });
}

/**
 * List all calibration sessions for the current user.
 * @returns {Promise<Array>} List of session records.
 */
export async function listSessions() {
  return request("/api/sessions");
}

/**
 * Fetch a single calibration session by ID.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Object>} The session record.
 */
export async function getSession(sessionId) {
  return request(`/api/sessions/${sessionId}`);
}

// ── Readings ──────────────────────────────────────────────────────────────────

/**
 * Create a single calibration reading record.
 * @param {Object} data - Reading fields matching the readings table.
 * @returns {Promise<Object>} The created reading record.
 */
export async function createReading(data) {
  return request("/api/readings", { method: "POST", body: JSON.stringify(data) });
}

/**
 * Fetch all readings for a calibration session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} List of reading records.
 */
export async function getReadings(sessionId) {
  return request(`/api/sessions/${sessionId}/readings`);
}

// ── Master Instruments ────────────────────────────────────────────────────────

/**
 * List all master instruments for the current user.
 * @returns {Promise<Array>} List of master instrument records.
 */
export async function listMasterInstruments() {
  return request("/api/master-instruments");
}

/**
 * Fetch a single master instrument by ID.
 * @param {string} masterId - UUID of the master instrument.
 * @returns {Promise<Object>} The master instrument record.
 */
export async function selectMaster(masterId) {
  return request(`/api/master-instruments/${masterId}`);
}

/**
 * Save a new master instrument record.
 * @param {Object} data - Master instrument fields.
 * @returns {Promise<Object>} The created master instrument record.
 */
export async function saveMaster(data) {
  return request("/api/master-instruments", { method: "POST", body: JSON.stringify(data) });
}

/**
 * Delete a master instrument record.
 * @param {string} masterId - UUID of the master instrument to delete.
 * @returns {Promise<Object>} Confirmation message.
 */
export async function deleteMaster(masterId) {
  return request(`/api/master-instruments/${masterId}`, { method: "DELETE" });
}

// ── Uncertainty Budget ────────────────────────────────────────────────────────

/**
 * Fetch the uncertainty budget for a session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Object>} The uncertainty budget record.
 */
/**
 * Fetch ALL uncertainty budgets calculated for a session.
 * Pressure/Weighing sessions always have exactly one; Temperature (one
 * per setpoint) and Electrical (one per function-type/range) can have
 * several. Returns an empty array if none have been calculated yet -
 * that's a normal state, not an error, so no try/catch is needed just to
 * detect "not calculated yet" the way the old singular version required.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} All uncertainty budget records for this session.
 */
export async function getUncertaintyBudgets(sessionId) {
  return request(`/api/sessions/${sessionId}/budget`);
}

/**
 * Calculate and store the uncertainty budget(s) for a session.
 * Implemented for Pressure, Weighing, Temperature, and Electrical.
 * Always returns a list now - one item for Pressure/Weighing, one item
 * per setpoint for Temperature, one item per function-type/range for Electrical.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} The calculated uncertainty budget records.
 */
export async function calculateUncertainty(sessionId) {
  return request(`/api/sessions/${sessionId}/calculate`, { method: "POST" });
}

// ── Validation ────────────────────────────────────────────────────────────────

/**
 * Validate a calibration session and get the compliance result.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Object>} Validation result with status and flags.
 */
export async function getResults(sessionId) {
  return request(`/api/sessions/${sessionId}/validate`);
}

// ── Weighing tests ────────────────────────────────────────────────────────────
// Weighing and Temperature sessions each use their own dedicated
// repeatability endpoints (see further below) instead of the single
// createReading/getReadings pair used by Pressure/Electrical.

/**
 * Create a weighing repeatability test and its 10 readings together.
 * @param {string} sessionId - UUID of the session.
 * @param {Object} test - Test-level fields: test_point, nominal_load, unit,
 *   standard_weights_uncertainty.
 * @param {Array} readings - Exactly 10 reading objects: reading_number,
 *   reading_before, reading_with_load, reading_after.
 * @returns {Promise<Object>} The created test record with nested readings.
 */
export async function createWeighingRepeatabilityTest(sessionId, test, readings) {
  // IMPORTANT: the backend endpoint declares two separate body parameters
  // (payload: WeighingRepeatabilityTestCreate, readings: list[...]). FastAPI
  // auto-embeds each under its own key when there's more than one body
  // parameter, so the wire shape MUST be {"payload": {...}, "readings": [...]}
  // - a flattened {...test, readings} body fails with a 422 "payload field
  // required" error. Verified empirically against a live FastAPI TestClient,
  // not assumed - see the same class of bug in the handover's Section 6.4.
  return request(`/api/sessions/${sessionId}/weighing/repeatability`, {
    method: "POST",
    body: JSON.stringify({ payload: test, readings }),
  });
}

/**
 * Fetch all repeatability tests (with readings) for a session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} Repeatability test records with nested readings.
 */
export async function getWeighingRepeatabilityTests(sessionId) {
  return request(`/api/sessions/${sessionId}/weighing/repeatability`);
}

/**
 * Create the 5 off-center position readings for a session.
 * @param {string} sessionId - UUID of the session.
 * @param {Array} readings - Exactly 5 reading objects, one per position
 *   (center/front/back/left/right).
 * @returns {Promise<Array>} The created off-center reading records.
 */
export async function createWeighingOffCenterReadings(sessionId, readings) {
  return request(`/api/sessions/${sessionId}/weighing/off-center`, {
    method: "POST",
    body: JSON.stringify(readings),
  });
}

/**
 * Fetch all off-center readings for a session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} Off-center reading records.
 */
export async function getWeighingOffCenterReadings(sessionId) {
  return request(`/api/sessions/${sessionId}/weighing/off-center`);
}

/**
 * Create the 5-step hysteresis sequence readings for a session.
 * @param {string} sessionId - UUID of the session.
 * @param {Array} readings - Exactly 5 reading objects in sequence order 1-5.
 * @returns {Promise<Array>} The created hysteresis reading records.
 */
export async function createWeighingHysteresisReadings(sessionId, readings) {
  return request(`/api/sessions/${sessionId}/weighing/hysteresis`, {
    method: "POST",
    body: JSON.stringify(readings),
  });
}

/**
 * Fetch all hysteresis sequence readings for a session, in order.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} Hysteresis reading records ordered by sequence_order.
 */
export async function getWeighingHysteresisReadings(sessionId) {
  return request(`/api/sessions/${sessionId}/weighing/hysteresis`);
}

// ── Temperature tests ──────────────────────────────────────────────────────

/**
 * Create a temperature repeatability test and its 3 readings together.
 * @param {string} sessionId - UUID of the session.
 * @param {Object} test - Test-level fields: setpoint_label, nominal_temperature,
 *   unit, standard_uncertainty, standard_accuracy, drift_standard_uncertainty,
 *   hysteresis_value, bath_stability_value, bath_uniformity_value,
 *   wire_homogeneity_value (TCK sub-type only).
 * @param {Array} readings - Exactly 3 reading objects: reading_number, reading_value.
 * @returns {Promise<Object>} The created test record with nested readings.
 */
export async function createTemperatureRepeatabilityTest(sessionId, test, readings) {
  // See createWeighingRepeatabilityTest's comment above: this endpoint also
  // declares two separate body params (payload + readings), so the body
  // must be embedded as {"payload": {...}, "readings": [...]}, not flattened.
  return request(`/api/sessions/${sessionId}/temperature/repeatability`, {
    method: "POST",
    body: JSON.stringify({ payload: test, readings }),
  });
}

/**
 * Fetch all repeatability tests (with readings) for a session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} Repeatability test records with nested readings.
 */
export async function getTemperatureRepeatabilityTests(sessionId) {
  return request(`/api/sessions/${sessionId}/temperature/repeatability`);
}

// ── Electrical tests ─────────────────────────────────────────────────────────

/**
 * Create an Electrical test (one function-type/range) and its readings together.
 * @param {string} sessionId - UUID of the session.
 * @param {Object} test - Test-level fields (function_type, range_label,
 *   nominal_value, unit, cert_uncertainty_limit, calibrator_accuracy_limit,
 *   resolution, thermo_electric_limit, coil_accuracy_limit).
 * @param {Array} readings - The repeated readings for this function-type/range.
 * @returns {Promise<Object>} The created test record with nested readings.
 */
export async function createElectricalTest(sessionId, test, readings) {
  // Same embedded-body requirement as create(Weighing|Temperature)RepeatabilityTest.
  return request(`/api/sessions/${sessionId}/electrical/tests`, {
    method: "POST",
    body: JSON.stringify({ payload: test, readings }),
  });
}

/**
 * Fetch all Electrical tests (with readings) for a session.
 * @param {string} sessionId - UUID of the session.
 * @returns {Promise<Array>} Electrical test records with nested readings.
 */
export async function getElectricalTests(sessionId) {
  return request(`/api/sessions/${sessionId}/electrical/tests`);
}

// ── Reports ───────────────────────────────────────────────────────────────────

/**
 * Download a calibration certificate as PDF or Excel.
 * @param {string} sessionId - UUID of the session.
 * @param {string} format - Either "pdf" or "excel".
 */
export async function downloadReport(sessionId, format) {
  const token = await getToken();
  const response = await fetch(
    `${BASE_URL}/api/sessions/${sessionId}/report?format=${format}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  if (!response.ok) throw new Error("Failed to generate report.");

  // Trigger browser download from the streamed file response.
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `calibration_certificate.${format === "excel" ? "xlsx" : "pdf"}`;
  link.click();
  window.URL.revokeObjectURL(url);
}