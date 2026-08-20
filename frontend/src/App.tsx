import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute, RoleRoute } from './components/auth/ProtectedRoute';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { ForbiddenPage } from './pages/ForbiddenPage';
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
import { PatientPortalPage } from './pages/PatientPortalPage';
import { PatientPortalDashboardPage } from './pages/PatientPortalDashboardPage';
import { ReceptionBillingPage } from './pages/ReceptionBillingPage';

const STAFF_ROLES = [
  'doctor',
  'medical_superintendent',
  'receptionist',
  'ward_admin',
  'receiving_doctor',
  'receiving_admin',
];

const CLINICAL_ROLES = [
  'doctor',
  'receiving_doctor',
];

const RECEPTION_ROLES = [
  'receptionist',
  'medical_superintendent',
  'ward_admin',
];

const SUPERINTENDENT_ROLES = [
  'medical_superintendent',
  'ward_admin',
  'receiving_admin',
];

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public login route */}
          <Route path="/login" element={<LoginPage />} />

          {/* 403 Forbidden Page */}
          <Route path="/forbidden" element={<ForbiddenPage />} />

          {/* Public Patient Care Portal View (Shared by Token / ID) */}
          <Route path="/patient-view/:patientId" element={<PatientPortalPage />} />

          {/* Authenticated Patient Care Portal */}
          <Route
            path="/patient-portal"
            element={
              <ProtectedRoute>
                <RoleRoute allowedRoles={['patient']}>
                  <PatientPortalDashboardPage />
                </RoleRoute>
              </ProtectedRoute>
            }
          />

          {/* Protected Hospital Staff Layout Routes */}
          <Route
            element={
              <ProtectedRoute>
                <RoleRoute allowedRoles={STAFF_ROLES}>
                  <DashboardLayout />
                </RoleRoute>
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />

            {/* Shared Patient Directory and Details */}
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/patients/:patientId" element={<PatientDetailPage />} />

            {/* Receptionist & Billing Management */}
            <Route
              path="/billing/reception"
              element={
                <RoleRoute allowedRoles={RECEPTION_ROLES}>
                  <ReceptionBillingPage />
                </RoleRoute>
              }
            />

            {/* Doctor Only: Clinical Decision & Discharge Review */}
            <Route
              path="/patients/:patientId/decision"
              element={
                <RoleRoute allowedRoles={CLINICAL_ROLES}>
                  <ClinicalDecisionPage />
                </RoleRoute>
              }
            />
            <Route
              path="/patients/:patientId/discharge"
              element={
                <RoleRoute allowedRoles={CLINICAL_ROLES}>
                  <DischargePage />
                </RoleRoute>
              }
            />

            {/* Transfers: Shared Roster & Detail, Doctor Creation */}
            <Route path="/transfers" element={<TransfersPage />} />
            <Route
              path="/transfers/new"
              element={
                <RoleRoute allowedRoles={CLINICAL_ROLES}>
                  <TransferEntryPage />
                </RoleRoute>
              }
            />
            <Route path="/transfers/:transferId" element={<TransferDetailPage />} />

            {/* Medical Superintendent Only: Bed Management */}
            <Route
              path="/beds"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <BedsPage />
                </RoleRoute>
              }
            />
            <Route
              path="/beds/:bedId"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <BedDetailPage />
                </RoleRoute>
              }
            />

            {/* Medical Superintendent Only: Incoming Transfer Queue */}
            <Route
              path="/receiving/transfers"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <IncomingTransfersPage />
                </RoleRoute>
              }
            />
            <Route
              path="/receiving/transfers/:transferId"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <ReceivingTransferDetailPage />
                </RoleRoute>
              }
            />

            {/* Medical Superintendent Only: Hospital Capacity & Ambulance Tracking */}
            <Route
              path="/hospitals"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <HospitalsPage />
                </RoleRoute>
              }
            />
            <Route
              path="/ambulances"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <AmbulancesPage />
                </RoleRoute>
              }
            />
            <Route
              path="/ambulances/:dispatchId"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <AmbulanceDetailPage />
                </RoleRoute>
              }
            />

            {/* Medical Superintendent Only: n8n Orchestration Telemetry & Event Audit */}
            <Route
              path="/operations"
              element={
                <RoleRoute allowedRoles={SUPERINTENDENT_ROLES}>
                  <OperationsPage />
                </RoleRoute>
              }
            />
          </Route>

          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
