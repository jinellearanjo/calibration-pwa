import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Splash from "./pages/Splash";
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
import NotFound from "./pages/NotFound";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/instrument" element={<ProtectedRoute><InstrumentForm /></ProtectedRoute>} />
        <Route path="/master" element={<ProtectedRoute><MasterForm /></ProtectedRoute>} />
        <Route path="/session" element={<ProtectedRoute><SessionForm /></ProtectedRoute>} />
        <Route path="/readings" element={<ProtectedRoute><ReadingsForm /></ProtectedRoute>} />
        <Route path="/calculation" element={<ProtectedRoute><CalculationView /></ProtectedRoute>} />
        <Route path="/results/:sessionId" element={<ProtectedRoute><ResultsView /></ProtectedRoute>} />
        <Route path="/report/:sessionId" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
        <Route path="/" element={<Splash />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;