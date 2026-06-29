import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

/**
 * Application entry point.
 * Mounts the React app to the root DOM element.
 */
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);