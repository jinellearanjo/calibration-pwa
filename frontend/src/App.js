import { BrowserRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Splash from "./pages/Splash";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import InstrumentForm from "./pages/InstrumentForm";
import SessionForm from "./pages/SessionForm";
import ReadingsForm from "./pages/ReadingsForm";
import WeighingReadingsForm from "./pages/WeighingReadingsForm";
import TemperatureReadingsForm from "./pages/TemperatureReadingsForm";
import ElectricalReadingsForm from "./pages/ElectricalReadingsForm";
import MasterForm from "./pages/MasterForm";
import CalculationView from "./pages/CalculationView";
import ResultsView from "./pages/ResultsView";
import ReportPage from "./pages/ReportPage";
import History from "./pages/History";
import EditSession from "./pages/EditSession";
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
        <Route path="/readings/:sessionId" element={<ProtectedRoute><ReadingsForm /></ProtectedRoute>} />
        <Route path="/readings/weighing/:sessionId" element={<ProtectedRoute><WeighingReadingsForm /></ProtectedRoute>} />
        <Route path="/readings/temperature" element={<ProtectedRoute><TemperatureReadingsForm /></ProtectedRoute>} />
        <Route path="/readings/temperature/:sessionId" element={<ProtectedRoute><TemperatureReadingsForm /></ProtectedRoute>} />
        <Route path="/readings/electrical" element={<ProtectedRoute><ElectricalReadingsForm /></ProtectedRoute>} />
        <Route path="/readings/electrical/:sessionId" element={<ProtectedRoute><ElectricalReadingsForm /></ProtectedRoute>} />
        <Route path="/calculation" element={<ProtectedRoute><CalculationView /></ProtectedRoute>} />
        <Route path="/calculation/:sessionId" element={<ProtectedRoute><CalculationView /></ProtectedRoute>} />
        <Route path="/results" element={<ProtectedRoute><ResultsView /></ProtectedRoute>} />
        <Route path="/results/:sessionId" element={<ProtectedRoute><ResultsView /></ProtectedRoute>} />
        <Route path="/report" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
        <Route path="/report/:sessionId" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
        <Route path="/edit-session" element={<ProtectedRoute><EditSession /></ProtectedRoute>} />
        <Route path="/" element={<Splash />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;