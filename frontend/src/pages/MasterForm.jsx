import { useMemo, useRef, useState } from "react"
import { saveMaster, deleteMaster, selectMaster } from "../api"

// ─── Design tokens ────────────────────────────────────────────────────────────
// Centralised here so every inline style references the same values rather than
// scattering magic strings across the JSX.
const TOKEN = {
  fontFamily: "'Inter', 'Segoe UI', sans-serif",
  fontSize: "0.875rem",
  fontSizeLabel: "0.75rem",
  colorBg: "#ffffff",
  colorSurface: "#f8f9fa",
  colorBorder: "#d1d5db",
  colorBorderFocus: "#2563eb",
  colorText: "#111827",
  colorMuted: "#6b7280",
  colorError: "#dc2626",
  colorPrimary: "#2563eb",
  colorPrimaryHover: "#1d4ed8",
  colorDanger: "#dc2626",
  colorDangerHover: "#b91c1c",
  radius: "6px",
  gap: "16px",
}

// ─── Empty form state ─────────────────────────────────────────────────────────
// Keys mirror Supabase column names exactly so the object can be sent to the
// backend without any key remapping step.
const EMPTY_MASTER = {
  name: "",
  make: "",
  model: "",
  serial_number: "",
  asset_number: "",
  traceability_chain: "",
  uncertainty_u: "",
  accuracy: "",
  resolution: "",
  cal_due_date: "",
  claimed_cmc: "",
  instrument_type: "",
}

// ─── Validation rules ─────────────────────────────────────────────────────────
// Returns an error string when the field is invalid, or "" when it is fine.
// Keeping rules here avoids scattering them across the JSX and makes future
// changes easy to find.
function validateField(fieldName, value) {
  const numericFields = [
    "uncertainty_u",
    "accuracy",
    "resolution",
    "claimed_cmc",
  ]

  if (fieldName === "name" && !value.trim()) {
    return "Master instrument name is required."
  }
  if (numericFields.includes(fieldName) && value !== "" && isNaN(Number(value))) {
    return "Must be a number."
  }
  if (fieldName === "cal_due_date" && value) {
    // Validate DD.MM.YYYY format (display format for the label; actual value is
    // a date-input string YYYY-MM-DD — verify it parses to a real date).
    const parsed = new Date(value)
    if (isNaN(parsed.getTime())) return "Enter a valid date."
  }
  return ""
}

/**
 * MasterForm
 *
 * Provides search-and-select for existing master instruments, field editing,
 * and save / delete actions.  All mutations go through api.js; this component
 * owns only UI state.
 *
 * Props:
 *   masters              {Array<{id: string|number, label: string, data: object}>}
 *                        List of master instruments for the search dropdown.
 *   budgetFormatStatus   {string}  Status line for the budget format template.
 *   reportFormatStatus   {string}  Status line for the report format template.
 *   onUploadTemplate     {function(File)}  Called when a template file is picked.
 *   onMasterSaved        {function}  Optional callback after a successful save.
 *   onMasterDeleted      {function}  Optional callback after a successful delete.
 */
export default function MasterForm({
  masters = [],
  budgetFormatStatus = "No budget format loaded.",
  reportFormatStatus = "No report format loaded.",
  onUploadTemplate,
  onMasterSaved,
  onMasterDeleted,
}) {
  const [formData, setFormData] = useState(EMPTY_MASTER)
  const [errors, setErrors] = useState({})
  const [searchQuery, setSearchQuery] = useState("")
  const [dropdownOpen, setDropdownOpen] = useState(false)
  // Track which master is currently selected so we can pass its id to deleteMaster.
  const [selectedMasterId, setSelectedMasterId] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const fileInputRef = useRef(null)

  // ── Derived state ────────────────────────────────────────────────────────────

  const filteredMasters = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return masters
    return masters.filter((master) =>
      master.label.toLowerCase().includes(query)
    )
  }, [masters, searchQuery])

  // Disable submit while any required field has an error.
  const hasValidationErrors = Object.values(errors).some(Boolean)

  // ── Handlers ─────────────────────────────────────────────────────────────────

  function updateField(columnName, value) {
    setFormData((prev) => ({ ...prev, [columnName]: value }))
    // Run validation immediately so the user gets real-time feedback.
    const errorMessage = validateField(columnName, value)
    setErrors((prev) => ({ ...prev, [columnName]: errorMessage }))
  }

  async function handleSelectMaster(masterOption) {
    setSearchQuery(masterOption.label)
    setDropdownOpen(false)
    setSelectedMasterId(masterOption.id)

    // Fetch or receive the full record via api.js so the form can be populated.
    const masterRecord = await selectMaster(masterOption.id)
    if (masterRecord) {
      // Only spread keys that exist in EMPTY_MASTER to avoid polluting formData
      // with server-side-only columns (e.g. created_at, updated_at).
      const sanitised = Object.fromEntries(
        Object.keys(EMPTY_MASTER).map((key) => [
          key,
          masterRecord[key] ?? "",
        ])
      )
      setFormData(sanitised)
      // Clear all validation errors when loading an existing record; it was
      // already valid when it was saved.
      setErrors({})
    }
  }

  async function handleSave() {
    // Run full validation before submitting in case a field was never touched.
    const freshErrors = Object.fromEntries(
      Object.entries(formData).map(([key, value]) => [
        key,
        validateField(key, value),
      ])
    )
    setErrors(freshErrors)
    if (Object.values(freshErrors).some(Boolean)) return

    setIsSaving(true)
    try {
      await saveMaster(formData)
      onMasterSaved?.()
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedMasterId) return
    setIsDeleting(true)
    try {
      await deleteMaster(selectedMasterId)
      // Reset the form to blank after a successful delete.
      setFormData(EMPTY_MASTER)
      setSearchQuery("")
      setSelectedMasterId(null)
      setErrors({})
      onMasterDeleted?.()
    } finally {
      setIsDeleting(false)
    }
  }

  function handleUploadClick() {
    fileInputRef.current?.click()
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (file) onUploadTemplate?.(file)
    // Reset so the same file can be re-uploaded if the user corrects a mistake.
    event.target.value = ""
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <section
      aria-labelledby="master-form-heading"
      style={{
        fontFamily: TOKEN.fontFamily,
        fontSize: TOKEN.fontSize,
        color: TOKEN.colorText,
        background: TOKEN.colorBg,
        borderRadius: TOKEN.radius,
        border: `1px solid ${TOKEN.colorBorder}`,
        padding: "24px",
        maxWidth: "860px",
      }}
    >
      <h2
        id="master-form-heading"
        style={{ margin: "0 0 20px", fontSize: "1.125rem", fontWeight: 600 }}
      >
        Master Traceability Details
      </h2>

      {/* ── Search + Save row ──────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: TOKEN.gap,
          alignItems: "flex-start",
          marginBottom: TOKEN.gap,
        }}
      >
        {/* Combobox wrapper needs position:relative so the dropdown can anchor. */}
        <div style={{ position: "relative", flex: 1 }}>
          <FloatingLabelField
            id="master-search"
            label="Search or Select Master"
            value={searchQuery}
            onChange={(value) => {
              setSearchQuery(value)
              setDropdownOpen(true)
            }}
            onFocus={() => setDropdownOpen(true)}
            onBlur={() =>
              // Delay lets a click on a dropdown option register before we close.
              setTimeout(() => setDropdownOpen(false), 150)
            }
            inputProps={{
              role: "combobox",
              "aria-expanded": dropdownOpen,
              "aria-controls": "master-search-list",
              autoComplete: "off",
            }}
          />

          {dropdownOpen && (
            <div
              id="master-search-list"
              role="listbox"
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                zIndex: 20,
                background: TOKEN.colorBg,
                border: `1px solid ${TOKEN.colorBorder}`,
                borderTop: "none",
                borderRadius: `0 0 ${TOKEN.radius} ${TOKEN.radius}`,
                maxHeight: "220px",
                overflowY: "auto",
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
              }}
            >
              {filteredMasters.length === 0 ? (
                <div
                  style={{
                    padding: "10px 14px",
                    color: TOKEN.colorMuted,
                    fontSize: TOKEN.fontSizeLabel,
                  }}
                >
                  No masters found
                </div>
              ) : (
                filteredMasters.map((masterOption) => (
                  <button
                    key={masterOption.id}
                    type="button"
                    role="option"
                    aria-selected={masterOption.id === selectedMasterId}
                    onMouseDown={(e) =>
                      // Prevent the input's onBlur from firing before onClick.
                      e.preventDefault()
                    }
                    onClick={() => handleSelectMaster(masterOption)}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "9px 14px",
                      background:
                        masterOption.id === selectedMasterId
                          ? "#eff6ff"
                          : "transparent",
                      border: "none",
                      cursor: "pointer",
                      fontSize: TOKEN.fontSize,
                      color: TOKEN.colorText,
                    }}
                  >
                    {masterOption.label}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button
          type="button"
          disabled={hasValidationErrors || isSaving}
          onClick={handleSave}
          style={primaryButtonStyle(hasValidationErrors || isSaving)}
        >
          {isSaving ? "Saving…" : "Save Current"}
        </button>
      </div>

      {/* ── Action buttons ─────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: TOKEN.gap,
          flexWrap: "wrap",
          marginBottom: TOKEN.gap,
        }}
      >
        <button
          type="button"
          disabled={!selectedMasterId || isDeleting}
          onClick={handleDelete}
          style={outlineButtonStyle(TOKEN.colorDanger, !selectedMasterId || isDeleting)}
        >
          <TrashIcon />
          {isDeleting ? "Deleting…" : "Delete Selected Master"}
        </button>

        <button
          type="button"
          onClick={handleUploadClick}
          style={outlineButtonStyle(TOKEN.colorPrimary, false)}
        >
          <UploadIcon />
          Upload Reference Format Template (.pdf / .txt)
        </button>

        {/* Hidden; triggered programmatically to style the visible button freely. */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
      </div>

      {/* ── Template status lines ──────────────────────────────────────────── */}
      <div style={{ marginBottom: "20px" }}>
        <StatusLine text={budgetFormatStatus} />
        <StatusLine text={reportFormatStatus} />
      </div>

      {/* ── Master instrument fields ───────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: TOKEN.gap,
        }}
      >
        {/* name is required; all others are optional but type-validated. */}
        <FloatingLabelField
          id="name"
          label="Master Instrument Name / Tag *"
          value={formData.name}
          onChange={(v) => updateField("name", v)}
          error={errors.name}
        />
        <FloatingLabelField
          id="make"
          label="Make"
          value={formData.make}
          onChange={(v) => updateField("make", v)}
          error={errors.make}
        />
        <FloatingLabelField
          id="model"
          label="Model"
          value={formData.model}
          onChange={(v) => updateField("model", v)}
          error={errors.model}
        />
        <FloatingLabelField
          id="serial_number"
          label="Serial No."
          value={formData.serial_number}
          onChange={(v) => updateField("serial_number", v)}
          error={errors.serial_number}
        />
        <FloatingLabelField
          id="asset_number"
          label="Asset No."
          value={formData.asset_number}
          onChange={(v) => updateField("asset_number", v)}
          error={errors.asset_number}
        />
        <FloatingLabelField
          id="instrument_type"
          label="Instrument Type"
          value={formData.instrument_type}
          onChange={(v) => updateField("instrument_type", v)}
          error={errors.instrument_type}
        />

        {/* traceability_chain spans the full row because it is free-form text
            that can be quite long (agency chain descriptions). */}
        <div style={{ gridColumn: "1 / -1" }}>
          <FloatingLabelField
            id="traceability_chain"
            label="Traceability / Agency Reference Chain"
            value={formData.traceability_chain}
            onChange={(v) => updateField("traceability_chain", v)}
            error={errors.traceability_chain}
          />
        </div>

        <FloatingLabelField
          id="uncertainty_u"
          label="Uncertainty (u)"
          type="number"
          value={formData.uncertainty_u}
          onChange={(v) => updateField("uncertainty_u", v)}
          error={errors.uncertainty_u}
        />
        <FloatingLabelField
          id="accuracy"
          label="Accuracy"
          type="number"
          value={formData.accuracy}
          onChange={(v) => updateField("accuracy", v)}
          error={errors.accuracy}
        />
        <FloatingLabelField
          id="resolution"
          label="Resolution"
          type="number"
          value={formData.resolution}
          onChange={(v) => updateField("resolution", v)}
          error={errors.resolution}
        />
        <FloatingLabelField
          id="cal_due_date"
          label="Cal Due Date"
          type="date"
          value={formData.cal_due_date}
          onChange={(v) => updateField("cal_due_date", v)}
          error={errors.cal_due_date}
        />
        <FloatingLabelField
          id="claimed_cmc"
          label="Claimed CMC"
          type="number"
          value={formData.claimed_cmc}
          onChange={(v) => updateField("claimed_cmc", v)}
          error={errors.claimed_cmc}
        />
      </div>
    </section>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/**
 * FloatingLabelField
 *
 * Single text / number / date input with a floating label and optional inline
 * error message.  Uses the CSS :placeholder-shown trick to detect when the
 * input is empty so the label can float down into the field as a placeholder.
 * Date inputs always have a value (the browser shows "dd/mm/yyyy"), so their
 * label is pre-floated to avoid overlapping the date picker chrome.
 */
function FloatingLabelField({
  id,
  label,
  value,
  onChange,
  type = "text",
  error = "",
  onFocus,
  onBlur,
  inputProps = {},
}) {
  const isDateField = type === "date"

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      {/* Wrapper needs position:relative so the label can be absolutely placed. */}
      <div style={{ position: "relative" }}>
        <input
          id={id}
          type={type}
          value={value}
          placeholder=" "
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          aria-describedby={error ? `${id}-error` : undefined}
          aria-invalid={!!error}
          {...inputProps}
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "20px 12px 6px",
            fontSize: TOKEN.fontSize,
            fontFamily: TOKEN.fontFamily,
            color: TOKEN.colorText,
            background: TOKEN.colorSurface,
            border: `1px solid ${error ? TOKEN.colorError : TOKEN.colorBorder}`,
            borderRadius: TOKEN.radius,
            outline: "none",
            transition: "border-color 0.15s",
          }}
          onFocusCapture={(e) => {
            e.currentTarget.style.borderColor = error
              ? TOKEN.colorError
              : TOKEN.colorBorderFocus
          }}
          onBlurCapture={(e) => {
            e.currentTarget.style.borderColor = error
              ? TOKEN.colorError
              : TOKEN.colorBorder
          }}
        />
        <label
          htmlFor={id}
          style={{
            position: "absolute",
            left: "12px",
            // Date inputs always show chrome; keep label small and out of the way.
            top: isDateField ? "4px" : undefined,
            fontSize: isDateField ? TOKEN.fontSizeLabel : undefined,
            color: TOKEN.colorMuted,
            pointerEvents: "none",
            transition: "all 0.15s",
            // When input is empty (:placeholder-shown), drop label to centre;
            // when filled or focused, it rides to the top.  Implemented with a
            // CSS custom property so we don't have to attach a JS focus listener.
            // The `not(:placeholder-shown)` selector handles the filled state.
          }}
        >
          {label}
        </label>
      </div>

      {/* Inline error — screen readers associate it via aria-describedby. */}
      {error && (
        <span
          id={`${id}-error`}
          role="alert"
          style={{
            fontSize: TOKEN.fontSizeLabel,
            color: TOKEN.colorError,
            paddingLeft: "2px",
          }}
        >
          {error}
        </span>
      )}

      {/*
        Floating-label behaviour via a scoped <style> block.
        We scope by id so multiple instances on the page don't collide.
      */}
      <style>{`
        #${id}:not(:placeholder-shown) + label,
        #${id}:focus + label {
          top: 4px;
          font-size: ${TOKEN.fontSizeLabel};
        }
        #${id}:placeholder-shown + label {
          top: 50%;
          transform: translateY(-50%);
          font-size: ${TOKEN.fontSize};
        }
        #${id}:focus {
          outline: none;
        }
      `}</style>
    </div>
  )
}

/**
 * StatusLine
 *
 * Single line of muted status text for template upload feedback.
 */
function StatusLine({ text }) {
  return (
    <p
      style={{
        margin: "2px 0",
        fontSize: TOKEN.fontSizeLabel,
        color: TOKEN.colorMuted,
      }}
    >
      {text}
    </p>
  )
}

// ─── Icon components ──────────────────────────────────────────────────────────

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ width: "14px", height: "14px", marginRight: "6px", flexShrink: 0 }}
    >
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ width: "14px", height: "14px", marginRight: "6px", flexShrink: 0 }}
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

// ─── Button style helpers ─────────────────────────────────────────────────────
// Functions rather than objects because `disabled` affects colour, and we want
// the style to stay co-located with the logic that computes it.

function primaryButtonStyle(disabled) {
  return {
    padding: "10px 18px",
    fontSize: TOKEN.fontSize,
    fontFamily: TOKEN.fontFamily,
    fontWeight: 500,
    color: "#ffffff",
    background: disabled ? TOKEN.colorBorder : TOKEN.colorPrimary,
    border: "none",
    borderRadius: TOKEN.radius,
    cursor: disabled ? "not-allowed" : "pointer",
    whiteSpace: "nowrap",
    alignSelf: "flex-start",
    marginTop: "2px",
  }
}

function outlineButtonStyle(accentColor, disabled) {
  return {
    display: "inline-flex",
    alignItems: "center",
    padding: "8px 14px",
    fontSize: TOKEN.fontSize,
    fontFamily: TOKEN.fontFamily,
    fontWeight: 500,
    color: disabled ? TOKEN.colorBorder : accentColor,
    background: "transparent",
    border: `1px solid ${disabled ? TOKEN.colorBorder : accentColor}`,
    borderRadius: TOKEN.radius,
    cursor: disabled ? "not-allowed" : "pointer",
    whiteSpace: "nowrap",
  }
}