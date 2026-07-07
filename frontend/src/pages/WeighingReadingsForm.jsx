import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useUnsavedWarning } from "../hooks/useUnsavedWarning";
import {
  createWeighingRepeatabilityTest,
  createWeighingOffCenterReadings,
  createWeighingHysteresisReadings,
} from "../api";

const TEST_POINTS = [
  { key: "near_zero", label: "Near Zero" },
  { key: "fifty_percent", label: "50% of Range" },
  { key: "hundred_percent", label: "100% of Range" },
];

const OFF_CENTER_POSITIONS = [
  { key: "center", label: "Center" },
  { key: "front", label: "Front" },
  { key: "back", label: "Back" },
  { key: "left", label: "Left" },
  { key: "right", label: "Right" },
];

const HYSTERESIS_PHASES = [
  { key: "zero_before", label: "Zero (before load)" },
  { key: "half_load_ascending", label: "Half Load (ascending)" },
  { key: "full_load", label: "Full Load" },
  { key: "half_load_descending", label: "Half Load (descending)" },
  { key: "zero_after", label: "Zero (after load)" },
];

function emptyRepeatabilityReading() {
  return { reading_before: "", reading_with_load: "", reading_after: "" };
}

function initialRepeatabilityState() {
  const state = {};
  TEST_POINTS.forEach(tp => {
    state[tp.key] = {
      nominal_load: "",
      unit: "kg",
      standard_weights_uncertainty: "",
      readings: Array.from({ length: 10 }, emptyRepeatabilityReading),
    };
  });
  return state;
}

function initialOffCenterState() {
  const state = {};
  OFF_CENTER_POSITIONS.forEach(p => {
    state[p.key] = { nominal_load: "", unit: "kg", reading_before: "", reading_with_load: "", reading_after: "" };
  });
  return state;
}

function initialHysteresisState() {
  const state = {};
  HYSTERESIS_PHASES.forEach(p => {
    state[p.key] = { reading_value: "", unit: "kg" };
  });
  return state;
}

/**
 * WeighingReadingsForm component.
 * Data entry for the three raw-data tests a Weighing calibration requires:
 * repeatability (3 load points x 10 readings), off-center / eccentricity
 * (5 positions), and hysteresis (5-step sequence). Unlike ReadingsForm.jsx,
 * this does not follow the single ascending/descending-per-point pattern —
 * see the reference doc for why weighing's uncertainty budget needs raw
 * data from all three tests rather than one set of per-point readings.
 */
function WeighingReadingsForm() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const { setIsDirty, safeNavigate } = useUnsavedWarning();

  const [repeatability, setRepeatability] = useState(initialRepeatabilityState());
  const [offCenter, setOffCenter] = useState(initialOffCenterState());
  const [hysteresis, setHysteresis] = useState(initialHysteresisState());

  const [activeSection, setActiveSection] = useState("repeatability");
  const [sectionStatus, setSectionStatus] = useState({ repeatability: "pending", offCenter: "pending", hysteresis: "pending" });
  const [submitError, setSubmitError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateRepeatabilityField(testPoint, field, value) {
    setRepeatability(prev => ({
      ...prev,
      [testPoint]: { ...prev[testPoint], [field]: value },
    }));
    setIsDirty(true);
  }

  function updateRepeatabilityReading(testPoint, index, field, value) {
    setRepeatability(prev => {
      const readings = [...prev[testPoint].readings];
      readings[index] = { ...readings[index], [field]: value };
      return { ...prev, [testPoint]: { ...prev[testPoint], readings } };
    });
    setIsDirty(true);
  }

  function updateOffCenterField(position, field, value) {
    setOffCenter(prev => ({ ...prev, [position]: { ...prev[position], [field]: value } }));
    setIsDirty(true);
  }

  function updateHysteresisField(phase, field, value) {
    setHysteresis(prev => ({ ...prev, [phase]: { ...prev[phase], [field]: value } }));
    setIsDirty(true);
  }

  function repeatabilityComplete(testPoint) {
    const t = repeatability[testPoint];
    if (!t.nominal_load) return false;
    return t.readings.every(r => r.reading_before !== "" && r.reading_with_load !== "" && r.reading_after !== "");
  }

  const allRepeatabilityComplete = TEST_POINTS.every(tp => repeatabilityComplete(tp.key));
  const allOffCenterComplete = OFF_CENTER_POSITIONS.every(p => {
    const r = offCenter[p.key];
    return r.nominal_load !== "" && r.reading_before !== "" && r.reading_with_load !== "" && r.reading_after !== "";
  });
  const allHysteresisComplete = HYSTERESIS_PHASES.every(p => hysteresis[p.key].reading_value !== "");

  async function submitRepeatability() {
    setSubmitError("");
    setIsSubmitting(true);
    try {
      for (const tp of TEST_POINTS) {
        const t = repeatability[tp.key];
        const testPayload = {
          // session_id is required by WeighingRepeatabilityTestCreate and is
          // validated by FastAPI before the endpoint's own session_id-from-URL
          // override ever runs - omitting it here causes a 422, even though
          // the backend technically re-sets it afterward. Verified empirically.
          session_id: sessionId,
          test_point: tp.key,
          nominal_load: Number(t.nominal_load),
          unit: t.unit,
          standard_weights_uncertainty: t.standard_weights_uncertainty === "" ? null : Number(t.standard_weights_uncertainty),
        };
        const readingsPayload = t.readings.map((r, i) => ({
          reading_number: i + 1,
          reading_before: Number(r.reading_before),
          reading_with_load: Number(r.reading_with_load),
          reading_after: Number(r.reading_after),
        }));
        await createWeighingRepeatabilityTest(sessionId, testPayload, readingsPayload);
      }
      setSectionStatus(prev => ({ ...prev, repeatability: "saved" }));
      setActiveSection("offCenter");
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitOffCenter() {
    setSubmitError("");
    setIsSubmitting(true);
    try {
      const payload = OFF_CENTER_POSITIONS.map(p => {
        const r = offCenter[p.key];
        return {
          position: p.key,
          nominal_load: Number(r.nominal_load),
          unit: r.unit,
          reading_before: Number(r.reading_before),
          reading_with_load: Number(r.reading_with_load),
          reading_after: Number(r.reading_after),
        };
      });
      await createWeighingOffCenterReadings(sessionId, payload);
      setSectionStatus(prev => ({ ...prev, offCenter: "saved" }));
      setActiveSection("hysteresis");
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitHysteresis() {
    setSubmitError("");
    setIsSubmitting(true);
    try {
      const payload = HYSTERESIS_PHASES.map((p, i) => {
        const r = hysteresis[p.key];
        return {
          sequence_order: i + 1,
          phase: p.key,
          reading_value: Number(r.reading_value),
          unit: r.unit,
        };
      });
      await createWeighingHysteresisReadings(sessionId, payload);
      setSectionStatus(prev => ({ ...prev, hysteresis: "saved" }));
      setIsDirty(false);
      navigate(`/calculation/${sessionId}`);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!sessionId) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
        <Navbar />
        <div style={{ maxWidth: 600, margin: "0 auto", padding: "48px 32px" }}>
          <p style={{ color: "var(--color-error)" }}>
            No session selected. Please start from the calibration session step.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "48px 32px" }}>

        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>
            Step 04 — Weighing
          </p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>
            Weighing Test Data
          </h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>
            Enter repeatability, off-center, and hysteresis test readings for this session.
          </p>
        </div>

        <SectionTabs activeSection={activeSection} setActiveSection={setActiveSection} sectionStatus={sectionStatus} />

        {submitError && (
          <p style={{ color: "var(--color-error)", fontSize: 13, marginBottom: 16 }}>
            {submitError}
          </p>
        )}

        {activeSection === "repeatability" && (
          <RepeatabilitySection
            repeatability={repeatability}
            updateField={updateRepeatabilityField}
            updateReading={updateRepeatabilityReading}
            onSubmit={submitRepeatability}
            canSubmit={allRepeatabilityComplete && !isSubmitting}
            isSubmitting={isSubmitting}
          />
        )}

        {activeSection === "offCenter" && (
          <OffCenterSection
            offCenter={offCenter}
            updateField={updateOffCenterField}
            onSubmit={submitOffCenter}
            canSubmit={allOffCenterComplete && !isSubmitting}
            isSubmitting={isSubmitting}
          />
        )}

        {activeSection === "hysteresis" && (
          <HysteresisSection
            hysteresis={hysteresis}
            updateField={updateHysteresisField}
            onSubmit={submitHysteresis}
            canSubmit={allHysteresisComplete && !isSubmitting}
            isSubmitting={isSubmitting}
          />
        )}

        <div style={{ marginTop: 24 }}>
          <button
            onClick={() => safeNavigate("/dashboard")}
            style={{
              padding: "11px 20px",
              background: "white",
              color: "var(--color-text)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Save &amp; Exit
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionTabs({ activeSection, setActiveSection, sectionStatus }) {
  const tabs = [
    { key: "repeatability", label: "1. Repeatability" },
    { key: "offCenter", label: "2. Off-Center" },
    { key: "hysteresis", label: "3. Hysteresis" },
  ];
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 24, borderBottom: "1px solid var(--color-border)" }}>
      {tabs.map(tab => (
        <button
          key={tab.key}
          onClick={() => setActiveSection(tab.key)}
          style={{
            padding: "10px 16px",
            background: "none",
            border: "none",
            borderBottom: activeSection === tab.key ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: activeSection === tab.key ? "var(--color-primary)" : "var(--color-muted)",
            fontWeight: activeSection === tab.key ? 600 : 500,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          {tab.label}
          {sectionStatus[tab.key] === "saved" && <span style={{ color: "var(--color-accent)", marginLeft: 6 }}>✓</span>}
        </button>
      ))}
    </div>
  );
}

function RepeatabilitySection({ repeatability, updateField, updateReading, onSubmit, canSubmit, isSubmitting }) {
  return (
    <div>
      <p style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 20 }}>
        For each of the three load points, enter the nominal load and 10 successive readings
        (before / with load / after).
      </p>
      {TEST_POINTS.map(tp => (
        <div
          key={tp.key}
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius)",
            padding: "24px",
            marginBottom: 20,
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--color-primary)", marginBottom: 16 }}>
            {tp.label}
          </h3>

          <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
            <SmallField
              label="Nominal Load"
              value={repeatability[tp.key].nominal_load}
              onChange={v => updateField(tp.key, "nominal_load", v)}
              type="number"
            />
            <SmallField
              label="Unit"
              value={repeatability[tp.key].unit}
              onChange={v => updateField(tp.key, "unit", v)}
            />
            <SmallField
              label="Standard Weights Uncertainty"
              value={repeatability[tp.key].standard_weights_uncertainty}
              onChange={v => updateField(tp.key, "standard_weights_uncertainty", v)}
              type="number"
            />
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--color-muted)" }}>
                <th style={{ padding: "4px 8px" }}>#</th>
                <th style={{ padding: "4px 8px" }}>Before</th>
                <th style={{ padding: "4px 8px" }}>With Load</th>
                <th style={{ padding: "4px 8px" }}>After</th>
              </tr>
            </thead>
            <tbody>
              {repeatability[tp.key].readings.map((r, i) => (
                <tr key={i}>
                  <td style={{ padding: "4px 8px", color: "var(--color-muted)" }}>{i + 1}</td>
                  <td style={{ padding: "4px 8px" }}>
                    <input
                      type="number"
                      value={r.reading_before}
                      onChange={e => updateReading(tp.key, i, "reading_before", e.target.value)}
                      style={{ width: "100%" }}
                    />
                  </td>
                  <td style={{ padding: "4px 8px" }}>
                    <input
                      type="number"
                      value={r.reading_with_load}
                      onChange={e => updateReading(tp.key, i, "reading_with_load", e.target.value)}
                      style={{ width: "100%" }}
                    />
                  </td>
                  <td style={{ padding: "4px 8px" }}>
                    <input
                      type="number"
                      value={r.reading_after}
                      onChange={e => updateReading(tp.key, i, "reading_after", e.target.value)}
                      style={{ width: "100%" }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <SubmitButton onClick={onSubmit} disabled={!canSubmit} label={isSubmitting ? "Saving..." : "Save Repeatability & Continue"} />
    </div>
  );
}

function OffCenterSection({ offCenter, updateField, onSubmit, canSubmit, isSubmitting }) {
  return (
    <div>
      <p style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 20 }}>
        Enter readings at each of the five fixed positions, typically at 50% of range.
      </p>
      <div style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        padding: "24px",
        marginBottom: 20,
        boxShadow: "var(--shadow-sm)",
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--color-muted)" }}>
              <th style={{ padding: "4px 8px" }}>Position</th>
              <th style={{ padding: "4px 8px" }}>Nominal Load</th>
              <th style={{ padding: "4px 8px" }}>Unit</th>
              <th style={{ padding: "4px 8px" }}>Before</th>
              <th style={{ padding: "4px 8px" }}>With Load</th>
              <th style={{ padding: "4px 8px" }}>After</th>
            </tr>
          </thead>
          <tbody>
            {OFF_CENTER_POSITIONS.map(p => (
              <tr key={p.key}>
                <td style={{ padding: "4px 8px", fontWeight: 500 }}>{p.label}</td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="number" value={offCenter[p.key].nominal_load} onChange={e => updateField(p.key, "nominal_load", e.target.value)} style={{ width: "100%" }} />
                </td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="text" value={offCenter[p.key].unit} onChange={e => updateField(p.key, "unit", e.target.value)} style={{ width: "100%" }} />
                </td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="number" value={offCenter[p.key].reading_before} onChange={e => updateField(p.key, "reading_before", e.target.value)} style={{ width: "100%" }} />
                </td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="number" value={offCenter[p.key].reading_with_load} onChange={e => updateField(p.key, "reading_with_load", e.target.value)} style={{ width: "100%" }} />
                </td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="number" value={offCenter[p.key].reading_after} onChange={e => updateField(p.key, "reading_after", e.target.value)} style={{ width: "100%" }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SubmitButton onClick={onSubmit} disabled={!canSubmit} label={isSubmitting ? "Saving..." : "Save Off-Center & Continue"} />
    </div>
  );
}

function HysteresisSection({ hysteresis, updateField, onSubmit, canSubmit, isSubmitting }) {
  return (
    <div>
      <p style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 20 }}>
        Enter the reading at each of the five steps in sequence: zero, half load ascending,
        full load, half load descending, zero.
      </p>
      <div style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        padding: "24px",
        marginBottom: 20,
        boxShadow: "var(--shadow-sm)",
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--color-muted)" }}>
              <th style={{ padding: "4px 8px" }}>Step</th>
              <th style={{ padding: "4px 8px" }}>Reading</th>
              <th style={{ padding: "4px 8px" }}>Unit</th>
            </tr>
          </thead>
          <tbody>
            {HYSTERESIS_PHASES.map((p, i) => (
              <tr key={p.key}>
                <td style={{ padding: "4px 8px", fontWeight: 500 }}>{i + 1}. {p.label}</td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="number" value={hysteresis[p.key].reading_value} onChange={e => updateField(p.key, "reading_value", e.target.value)} style={{ width: "100%" }} />
                </td>
                <td style={{ padding: "4px 8px" }}>
                  <input type="text" value={hysteresis[p.key].unit} onChange={e => updateField(p.key, "unit", e.target.value)} style={{ width: "100%" }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SubmitButton onClick={onSubmit} disabled={!canSubmit} label={isSubmitting ? "Saving..." : "Save Hysteresis & Continue to Calculation"} />
    </div>
  );
}

function SmallField({ label, value, onChange, type = "text" }) {
  return (
    <div style={{ flex: 1 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4, color: "var(--color-text)" }}>
        {label}
      </label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} style={{ width: "100%" }} />
    </div>
  );
}

function SubmitButton({ onClick, disabled, label }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "11px 24px",
        background: disabled ? "var(--color-border)" : "var(--color-primary)",
        color: "white",
        border: "none",
        borderRadius: "var(--radius)",
        fontWeight: 600,
        fontSize: 14,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {label}
    </button>
  );
}

export default WeighingReadingsForm;