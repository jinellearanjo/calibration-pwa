import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import InstrumentForm from "./pages/InstrumentForm";
import SessionForm from "./pages/SessionForm";
import ReadingsForm from "./pages/ReadingsForm";
import MasterForm from "./pages/MasterForm";
import CalculationView from "./pages/CalculationView";
import ResultsView from "./pages/ResultsView";
import ReportPage from "./pages/ReportPage";
import History from "./pages/History";

/**
 * Root application component.
 * Defines all client-side routes and wraps protected pages in ProtectedRoute.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public route */}
        <Route path="/login" element={<Login />} />

        {/* Protected routes */}
        <Route path="/dashboard" element={
          <ProtectedRoute><Dashboard /></ProtectedRoute>
        } />
        <Route path="/instrument" element={
          <ProtectedRoute><InstrumentForm /></ProtectedRoute>
        } />
        <Route path="/master" element={
          <ProtectedRoute><MasterForm /></ProtectedRoute>
        } />
        <Route path="/session" element={
          <ProtectedRoute><SessionForm /></ProtectedRoute>
        } />
        <Route path="/readings" element={
          <ProtectedRoute><ReadingsForm /></ProtectedRoute>
        } />
        <Route path="/calculation" element={
          <ProtectedRoute><CalculationView /></ProtectedRoute>
        } />
        <Route path="/results/:sessionId" element={
          <ProtectedRoute><ResultsView /></ProtectedRoute>
        } />
        <Route path="/report/:sessionId" element={
          <ProtectedRoute><ReportPage /></ProtectedRoute>
        } />
        <Route path="/history" element={
          <ProtectedRoute><History /></ProtectedRoute>
        } />

        {/* Redirect root to dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;