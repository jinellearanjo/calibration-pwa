/**
 * Sanitizes free-typed input for a decimal numeric field.
 *
 * Native <input type="number"> is locale-dependent in the browser: if the
 * OS/browser locale expects "," as the decimal separator, typing "." is
 * silently rejected as an invalid character, even though nothing in this
 * app's own code is wrong - every numeric field on the backend (models.py)
 * is a plain `float` and accepts a normal "12.5"-style value fine. This
 * util sidesteps the locale problem entirely by using <input type="text">
 * with inputMode="decimal" (still brings up a numeric keyboard on mobile)
 * and filtering keystrokes ourselves, so "." always works regardless of
 * the browser's locale settings.
 *
 * Allows: an optional leading "-", digits, and at most one ".".
 * Rejects everything else (letters, "e" scientific notation, a second
 * ".", etc.) by simply not calling onChange for that keystroke - so the
 * input never shows an invalid character, same UX as native number
 * inputs blocking bad keystrokes, just without the locale bug.
 *
 * @param {string} rawValue - The input's current value (e.target.value).
 * @returns {boolean} True if rawValue is a valid (possibly incomplete,
 *   e.g. "12." or "-" or "") decimal-in-progress string.
 */
export function isValidDecimalInProgress(rawValue) {
  return /^-?\d*\.?\d*$/.test(rawValue);
}

/**
 * Wraps a field's onChange so only valid decimal-in-progress keystrokes
 * are applied. Use in place of a bare `onChange={e => onChange(e.target.value)}`
 * for any numeric field.
 *
 * @param {(value: string) => void} onChange - The field's real onChange.
 * @returns {(e: React.ChangeEvent<HTMLInputElement>) => void}
 */
export function decimalInputHandler(onChange) {
  return (e) => {
    const value = e.target.value;
    if (isValidDecimalInProgress(value)) {
      onChange(value);
    }
  };
}
