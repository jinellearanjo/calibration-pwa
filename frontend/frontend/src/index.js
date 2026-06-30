import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

/**
 * Application entry point.
 * Mounts the React app to the root DOM element and registers the service worker.
 */
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register service worker for PWA offline support.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then(reg => console.log("Service worker registered:", reg.scope))
      .catch(err => console.log("Service worker registration failed:", err));
  });
}