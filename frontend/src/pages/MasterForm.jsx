import { useMemo, useRef, useState, useEffect } from "react"
import { saveMaster, deleteMaster, selectMaster, listMasterInstruments } from "../api"
import Navbar from "../components/Navbar"

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
  colorDanger: "#dc2626",
  radius: "6px",
  gap: "16px",
}

const EMPTY_MASTER = {
  name: "", make: "", model: "", serial_number: "", asset_number: "",
  traceability_chain: "", uncertainty_u: "", accuracy: "", resolution: "",
  cal_due_date: "", claimed_cmc: "", instrument_type: "",
}

function validateField(fieldName, value) {
  const numericFields = ["uncertainty_u", "accuracy", "resolution", "claimed_cmc"]
  if (fieldName === "name" && !value.trim()) return "Master instrument name is required."
  if (numericFields.includes(fieldName) && value !== "" && isNaN(Number(value))) return "Must be a number."
  if (fieldName === "cal_due_date" && value) {
    const parsed = new Date(value)
    if (isNaN(parsed.getTime())) return "Enter a valid date."
  }
  return ""
}

/**
 * MasterForm component.
 * Provides search-and-select for existing master instruments, field editing,
 * and save / delete actions. All mutations go through api.js.
 */
export default function MasterForm({
  budgetFormatStatus = "No budget format loaded.",
  reportFormatStatus = "No report format loaded.",
  onUploadTemplate,
  onMasterSaved,
  onMasterDeleted,
}) {
  const [masters, setMasters] = useState([])
  const [formData, setFormData] = useState(EMPTY_MASTER)
  const [errors, setErrors] = useState({})
  const [searchQuery, setSearchQuery] = useState("")
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [selectedMasterId, setSelectedMasterId] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    listMasterInstruments()
      .then(data => setMasters(data.map(m => ({ id: m.id, label: m.name, data: m }))))
      .catch(err => console.error("Failed to load master instruments:", err))
  }, [])

  const filteredMasters = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return masters
    return masters.filter((master) => master.label.toLowerCase().includes(query))
  }, [masters, searchQuery])

  const hasValidationErrors = Object.values(errors).some(Boolean)

  function updateField(columnName, value) {
    setFormData((prev) => ({ ...prev, [columnName]: value }))
    setErrors((prev) => ({ ...prev, [columnName]: validateField(columnName, value) }))
  }

  async function handleSelectMaster(masterOption) {
    setSearchQuery(masterOption.label)
    setDropdownOpen(false)
    setSelectedMasterId(masterOption.id)
    const masterRecord = await selectMaster(masterOption.id)
    if (masterRecord) {
      const sanitised = Object.fromEntries(Object.keys(EMPTY_MASTER).map((key) => [key, masterRecord[key] ?? ""]))
      setFormData(sanitised)
      setErrors({})
    }
  }

  async function handleSave() {
    const freshErrors = Object.fromEntries(Object.entries(formData).map(([key, value]) => [key, validateField(key, value)]))
    setErrors(freshErrors)
    if (Object.values(freshErrors).some(Boolean)) return
    setIsSaving(true)
    try {
      await saveMaster(formData)
      const data = await listMasterInstruments()
      setMasters(data.map(m => ({ id: m.id, label: m.name, data: m })))
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
      setFormData(EMPTY_MASTER)
      setSearchQuery("")
      setSelectedMasterId(null)
      setErrors({})
      const data = await listMasterInstruments()
      setMasters(data.map(m => ({ id: m.id, label: m.name, data: m })))
      onMasterDeleted?.()
    } finally {
      setIsDeleting(false)
    }
  }

  function handleUploadClick() { fileInputRef.current?.click() }

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (file) onUploadTemplate?.(file)
    event.target.value = ""
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <Navbar />
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 32px" }}>
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-accent)", marginBottom: 8 }}>Step 02</p>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "var(--color-primary)", marginBottom: 8 }}>Master Instrument</h1>
          <p style={{ color: "var(--color-muted)", fontSize: 14 }}>Search, select, or register the reference standard used for this calibration.</p>
        </div>

        <section aria-labelledby="master-form-heading" style={{ fontFamily: TOKEN.fontFamily, fontSize: TOKEN.fontSize, color: TOKEN.colorText, background: TOKEN.colorBg, borderRadius: TOKEN.radius, border: `1px solid ${TOKEN.colorBorder}`, padding: "24px" }}>
          <h2 id="master-form-heading" style={{ margin: "0 0 20px", fontSize: "1.125rem", fontWeight: 600 }}>Master Traceability Details</h2>

          <div style={{ display: "flex", gap: TOKEN.gap, alignItems: "flex-start", marginBottom: TOKEN.gap }}>
            <div style={{ position: "relative", flex: 1 }}>
              <FloatingLabelField
                id="master-search" label="Search or Select Master" value={searchQuery}
                onChange={(value) => { setSearchQuery(value); setDropdownOpen(true) }}
                onFocus={() => setDropdownOpen(true)}
                onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
                inputProps={{ role: "combobox", "aria-expanded": dropdownOpen, "aria-controls": "master-search-list", autoComplete: "off" }}
              />
              {dropdownOpen && (
                <div id="master-search-list" role="listbox" style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 20, background: TOKEN.colorBg, border: `1px solid ${TOKEN.colorBorder}`, borderTop: "none", borderRadius: `0 0 ${TOKEN.radius} ${TOKEN.radius}`, maxHeight: "220px", overflowY: "auto", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}>
                  {filteredMasters.length === 0 ? (
                    <div style={{ padding: "10px 14px", color: TOKEN.colorMuted, fontSize: TOKEN.fontSizeLabel }}>No masters found</div>
                  ) : filteredMasters.map((masterOption) => (
                    <button key={masterOption.id} type="button" role="option" aria-selected={masterOption.id === selectedMasterId} onMouseDown={(e) => e.preventDefault()} onClick={() => handleSelectMaster(masterOption)}
                      style={{ display: "block", width: "100%", textAlign: "left", padding: "9px 14px", background: masterOption.id === selectedMasterId ? "#eff6ff" : "transparent", border: "none", cursor: "pointer", fontSize: TOKEN.fontSize, color: TOKEN.colorText }}>
                      {masterOption.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="button" disabled={hasValidationErrors || isSaving} onClick={handleSave} style={primaryButtonStyle(hasValidationErrors || isSaving)}>
              {isSaving ? "Saving…" : "Save Current"}
            </button>
          </div>

          <div style={{ display: "flex", gap: TOKEN.gap, flexWrap: "wrap", marginBottom: TOKEN.gap }}>
            <button type="button" disabled={!selectedMasterId || isDeleting} onClick={handleDelete} style={outlineButtonStyle(TOKEN.colorDanger, !selectedMasterId || isDeleting)}>
              <TrashIcon />{isDeleting ? "Deleting…" : "Delete Selected Master"}
            </button>
            <button type="button" onClick={handleUploadClick} style={outlineButtonStyle(TOKEN.colorPrimary, false)}>
              <UploadIcon />Upload Reference Format Template (.pdf / .txt)
            </button>
            <input ref={fileInputRef} type="file" accept=".pdf,.txt" style={{ display: "none" }} onChange={handleFileChange} />
          </div>

          <div style={{ marginBottom: "20px" }}>
            <StatusLine text={budgetFormatStatus} />
            <StatusLine text={reportFormatStatus} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: TOKEN.gap }}>
            <FloatingLabelField id="name" label="Master Instrument Name / Tag *" value={formData.name} onChange={(v) => updateField("name", v)} error={errors.name} />
            <FloatingLabelField id="make" label="Make" value={formData.make} onChange={(v) => updateField("make", v)} error={errors.make} />
            <FloatingLabelField id="model" label="Model" value={formData.model} onChange={(v) => updateField("model", v)} error={errors.model} />
            <FloatingLabelField id="serial_number" label="Serial No." value={formData.serial_number} onChange={(v) => updateField("serial_number", v)} error={errors.serial_number} />
            <FloatingLabelField id="asset_number" label="Asset No." value={formData.asset_number} onChange={(v) => updateField("asset_number", v)} error={errors.asset_number} />
            <FloatingLabelField id="instrument_type" label="Instrument Type" value={formData.instrument_type} onChange={(v) => updateField("instrument_type", v)} error={errors.instrument_type} />
            <div style={{ gridColumn: "1 / -1" }}>
              <FloatingLabelField id="traceability_chain" label="Traceability / Agency Reference Chain" value={formData.traceability_chain} onChange={(v) => updateField("traceability_chain", v)} error={errors.traceability_chain} />
            </div>
            <FloatingLabelField id="uncertainty_u" label="Uncertainty (u)" type="number" value={formData.uncertainty_u} onChange={(v) => updateField("uncertainty_u", v)} error={errors.uncertainty_u} />
            <FloatingLabelField id="accuracy" label="Accuracy" type="number" value={formData.accuracy} onChange={(v) => updateField("accuracy", v)} error={errors.accuracy} />
            <FloatingLabelField id="resolution" label="Resolution" type="number" value={formData.resolution} onChange={(v) => updateField("resolution", v)} error={errors.resolution} />
            <FloatingLabelField id="cal_due_date" label="Cal Due Date" type="date" value={formData.cal_due_date} onChange={(v) => updateField("cal_due_date", v)} error={errors.cal_due_date} />
            <FloatingLabelField id="claimed_cmc" label="Claimed CMC" type="number" value={formData.claimed_cmc} onChange={(v) => updateField("claimed_cmc", v)} error={errors.claimed_cmc} />
          </div>

          <div style={{ marginTop: 24, paddingTop: 16, borderTop: `1px solid ${TOKEN.colorBorder}` }}>
            <button type="button" onClick={() => window.history.back()} style={{ background: "none", border: "none", color: TOKEN.colorMuted, fontSize: TOKEN.fontSize, cursor: "pointer", padding: 0, fontFamily: TOKEN.fontFamily }}>
              ← Back
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}

function FloatingLabelField({ id, label, value, onChange, type = "text", error = "", onFocus, onBlur, inputProps = {} }) {
  const isDateField = type === "date"
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <div style={{ position: "relative" }}>
        <input id={id} type={type} value={value} placeholder=" " onChange={(e) => onChange(e.target.value)} onFocus={onFocus} onBlur={onBlur} aria-describedby={error ? `${id}-error` : undefined} aria-invalid={!!error} {...inputProps}
          style={{ width: "100%", boxSizing: "border-box", padding: "20px 12px 6px", fontSize: TOKEN.fontSize, fontFamily: TOKEN.fontFamily, color: TOKEN.colorText, background: TOKEN.colorSurface, border: `1px solid ${error ? TOKEN.colorError : TOKEN.colorBorder}`, borderRadius: TOKEN.radius, outline: "none", transition: "border-color 0.15s" }}
          onFocusCapture={(e) => { e.currentTarget.style.borderColor = error ? TOKEN.colorError : TOKEN.colorBorderFocus }}
          onBlurCapture={(e) => { e.currentTarget.style.borderColor = error ? TOKEN.colorError : TOKEN.colorBorder }}
        />
        <label htmlFor={id} style={{ position: "absolute", left: "12px", top: isDateField ? "4px" : undefined, fontSize: isDateField ? TOKEN.fontSizeLabel : undefined, color: TOKEN.colorMuted, pointerEvents: "none", transition: "all 0.15s" }}>
          {label}
        </label>
      </div>
      {error && <span id={`${id}-error`} role="alert" style={{ fontSize: TOKEN.fontSizeLabel, color: TOKEN.colorError, paddingLeft: "2px" }}>{error}</span>}
      <style>{`
        #${id}:not(:placeholder-shown) + label, #${id}:focus + label { top: 4px; font-size: ${TOKEN.fontSizeLabel}; }
        #${id}:placeholder-shown + label { top: 50%; transform: translateY(-50%); font-size: ${TOKEN.fontSize}; }
        #${id}:focus { outline: none; }
      `}</style>
    </div>
  )
}

function StatusLine({ text }) {
  return <p style={{ margin: "2px 0", fontSize: TOKEN.fontSizeLabel, color: TOKEN.colorMuted }}>{text}</p>
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: "14px", height: "14px", marginRight: "6px", flexShrink: 0 }}>
      <path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: "14px", height: "14px", marginRight: "6px", flexShrink: 0 }}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

function primaryButtonStyle(disabled) {
  return { padding: "10px 18px", fontSize: TOKEN.fontSize, fontFamily: TOKEN.fontFamily, fontWeight: 500, color: "#ffffff", background: disabled ? TOKEN.colorBorder : TOKEN.colorPrimary, border: "none", borderRadius: TOKEN.radius, cursor: disabled ? "not-allowed" : "pointer", whiteSpace: "nowrap", alignSelf: "flex-start", marginTop: "2px" }
}

function outlineButtonStyle(accentColor, disabled) {
  return { display: "inline-flex", alignItems: "center", padding: "8px 14px", fontSize: TOKEN.fontSize, fontFamily: TOKEN.fontFamily, fontWeight: 500, color: disabled ? TOKEN.colorBorder : accentColor, background: "transparent", border: `1px solid ${disabled ? TOKEN.colorBorder : accentColor}`, borderRadius: TOKEN.radius, cursor: disabled ? "not-allowed" : "pointer", whiteSpace: "nowrap" }
}