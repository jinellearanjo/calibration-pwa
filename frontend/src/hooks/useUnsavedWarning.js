import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * useUnsavedWarning hook.
 * Tracks whether a form has unsaved changes and warns the user
 * before navigating away. Returns a isDirty setter and a safe
 * navigate function that checks for unsaved changes first.
 *
 * @returns {Object} { isDirty, setIsDirty, safeNavigate }
 */
export function useUnsavedWarning() {
  const [isDirty, setIsDirty] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Warn when user tries to close or refresh the browser tab.
    function handleBeforeUnload(e) {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  function safeNavigate(path) {
    if (isDirty) {
      const confirmed = window.confirm(
        "You have unsaved changes. Are you sure you want to leave?"
      );
      if (!confirmed) return;
    }
    navigate(path);
  }

  return { isDirty, setIsDirty, safeNavigate };
}