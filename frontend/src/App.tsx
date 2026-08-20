import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { PatientsPage } from './pages/PatientsPage';
import { PatientDetailPage } from './pages/PatientDetailPage';
import { DischargePage } from './pages/DischargePage';
import { BedsPage } from './pages/BedsPage';
import { BedDetailPage } from './pages/BedDetailPage';
import { TransfersPage } from './pages/TransfersPage';
import { TransferDetailPage } from './pages/TransferDetailPage';
import { HospitalsPage } from './pages/HospitalsPage';
import { AmbulancesPage } from './pages/AmbulancesPage';
import { AmbulanceDetailPage } from './pages/AmbulanceDetailPage';
import { ClinicalDecisionPage } from './pages/ClinicalDecisionPage';
import { TransferEntryPage } from './pages/TransferEntryPage';
import { IncomingTransfersPage } from './pages/IncomingTransfersPage';
import { ReceivingTransferDetailPage } from './pages/ReceivingTransferDetailPage';
import { OperationsPage } from './pages/OperationsPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public login route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected Dashboard layout routes */}
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          
          {/* Patient and discharge routes */}
          <Route path="/patients" element={<PatientsPage />} />
          <Route path="/patients/:patientId" element={<PatientDetailPage />} />
          <Route path="/patients/:patientId/decision" element={<ClinicalDecisionPage />} />
          <Route path="/patients/:patientId/discharge" element={<DischargePage />} />
          
          {/* Bed management */}
          <Route path="/beds" element={<BedsPage />} />
          <Route path="/beds/:bedId" element={<BedDetailPage />} />
          
          {/* Inter-hospital transfers (Sending Side) */}
          <Route path="/transfers" element={<TransfersPage />} />
          <Route path="/transfers/new" element={<TransferEntryPage />} />
          <Route path="/transfers/:transferId" element={<TransferDetailPage />} />
          
          {/* Receiving Hospital Operations */}
          <Route path="/receiving/transfers" element={<IncomingTransfersPage />} />
          <Route path="/receiving/transfers/:transferId" element={<ReceivingTransferDetailPage />} />
          
          {/* Hospital capacity & ambulance tracking */}
          <Route path="/hospitals" element={<HospitalsPage />} />
          <Route path="/ambulances" element={<AmbulancesPage />} />
          <Route path="/ambulances/:dispatchId" element={<AmbulanceDetailPage />} />

          {/* n8n Orchestration Telemetry & Event Audit */}
          <Route path="/operations" element={<OperationsPage />} />
        </Route>

        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
