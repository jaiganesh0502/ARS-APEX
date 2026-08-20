import React, { useEffect, useState } from 'react';
import {
  ActivitySquare,
  FileText,
  Download,
  AlertTriangle,
  Pill,
  Calendar,
  Phone,
  CheckCircle2,
  Clock,
  LogOut,
  UserCheck,
  Stethoscope,
  ShieldCheck,
  CreditCard,
  QrCode,
} from 'lucide-react';
import { authApi, PatientPortalProfileResponse } from '../api/auth';
import { billingApi } from '../api/billing';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';

export const PatientPortalDashboardPage: React.FC = () => {
  const { logout } = useAuth();
  const [data, setData] = useState<PatientPortalProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const res = await authApi.getPatientProfile();
      setData(res);
      setError(null);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        'Unable to load your patient profile.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleDownloadPdf = () => {
    const token = localStorage.getItem('auth_token');
    const url = `/api/patient-portal/pdf`;
    
    // Create an authenticated download fetch
    fetch(url, {
      headers: {
        Authorization: token ? `Bearer ${token}` : '',
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error('PDF download failed');
        return res.blob();
      })
      .then((blob) => {
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `discharge_summary_${data?.patient.patient_code || 'care_plan'}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(blobUrl);
      })
      .catch(() => {
        alert('Unable to download PDF. Please verify your care plan is finalized.');
      });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <div className="w-10 h-10 border-4 border-green-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-slate-300 text-sm font-medium">Loading your personalized care plan...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-800 border border-slate-700 rounded-xl p-6 text-center text-white">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold">Unable to Load Care Record</h2>
          <p className="text-sm text-slate-400 mt-2 mb-6">{error || 'No record linked.'}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="secondary" onClick={fetchProfile}>
              Retry
            </Button>
            <Button variant="danger" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const { patient, admission, discharge_package } = data;
  const summary = discharge_package?.patient_summary;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10 shadow-md">
        <div className="flex items-center gap-3">
          <img src="/logo.jpg" alt="Alta" className="w-10 h-10 rounded-xl shadow-sm" />
          <div>
            <span className="font-bold text-white text-lg tracking-tight leading-none block">
              Patient Care Portal
            </span>
            <span className="text-xs text-green-400 font-medium">
              Metro General Hospital Care Network
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <span className="text-sm font-semibold text-white block">
              {patient.first_name} {patient.last_name}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              MRN: {patient.patient_code}
            </span>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={logout}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sign Out</span>
          </Button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {/* Welcome & Status Hero Card */}
        <div className="bg-gradient-to-r from-green-950/60 via-slate-900 to-teal-950/60 border border-green-800/40 rounded-2xl p-6 sm:p-8 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-900/60 border border-green-700/60 text-xs font-semibold text-green-300 mb-3">
                <UserCheck className="w-3.5 h-3.5" />
                <span>Verified Patient Profile</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                Welcome back, {patient.first_name}
              </h1>
              <p className="text-sm text-slate-300 mt-1 max-w-xl">
                Here are your personalized recovery instructions, medication schedules, and clinical discharge documentation.
              </p>
            </div>

            {discharge_package?.has_pdf && (
              <Button
                variant="primary"
                onClick={handleDownloadPdf}
                className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 text-white font-semibold py-3 px-6 rounded-xl shadow-lg shadow-green-900/40 transition-all shrink-0"
              >
                <Download className="w-5 h-5" />
                <span>Download Official Discharge PDF</span>
              </Button>
            )}
          </div>
        </div>

        {/* Admission & Clinical Care Context */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-slate-900 border-slate-800 p-5 rounded-xl">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Primary Diagnosis
            </div>
            <div className="text-base font-bold text-white">
              {admission?.primary_diagnosis || 'Under Clinical Evaluation'}
            </div>
          </Card>

          <Card className="bg-slate-900 border-slate-800 p-5 rounded-xl">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Attending Physician
            </div>
            <div className="text-base font-bold text-white flex items-center gap-2">
              <Stethoscope className="w-4 h-4 text-primary-400" />
              <span>{admission?.attending_doctor || 'Dr. Aris Thorne'}</span>
            </div>
          </Card>

          <Card className="bg-slate-900 border-slate-800 p-5 rounded-xl">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Discharge Status
            </div>
            <div className="text-base font-bold text-white flex items-center gap-2">
              {data.admission?.discharge_ready ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-emerald-400">Discharge Cleared & Ready</span>
                </>
              ) : discharge_package?.has_pdf ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  <span className="text-green-400">Package Ready</span>
                </>
              ) : (
                <>
                  <Clock className="w-4 h-4 text-amber-400" />
                  <span className="text-amber-400">Preparing Care Plan</span>
                </>
              )}
            </div>
          </Card>
        </div>

        {/* Hospital Invoice & UPI Payment Section */}
        {data.invoice && (
          <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2.5">
                  <CreditCard className="w-5 h-5 text-emerald-400" />
                  <span>Hospital Invoice & Dues Settlement</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Invoice #: <span className="font-mono text-slate-200">{data.invoice.invoice_number}</span>
                </p>
              </div>
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
                  data.invoice.payment_status === 'paid_online' || data.invoice.payment_status === 'paid_manual'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                    : data.invoice.payment_status === 'deferred'
                    ? 'bg-blue-950 text-blue-300 border border-blue-800'
                    : 'bg-amber-950 text-amber-300 border border-amber-800'
                }`}
              >
                {data.invoice.payment_status.replace('_', ' ')}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Financial Breakdown */}
              <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Room & Treatment Charges</span>
                  <span className="font-mono font-medium text-slate-200">
                    ₹{data.invoice.subtotal.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Healthcare Surcharge / GST (5%)</span>
                  <span className="font-mono font-medium text-slate-200">
                    ₹{data.invoice.tax_amount.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-bold text-white pt-2 border-t border-slate-800">
                  <span>Total Hospital Bill</span>
                  <span className="font-mono">₹{data.invoice.total_amount.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-emerald-400 font-semibold pt-1">
                  <span>Amount Paid</span>
                  <span className="font-mono">₹{data.invoice.amount_paid.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-amber-400 font-bold text-sm pt-2 border-t border-slate-800">
                  <span>Outstanding Balance</span>
                  <span className="font-mono">₹{data.invoice.balance_amount.toFixed(2)}</span>
                </div>
              </div>

              {/* UPI QR & Instant Payment */}
              <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex flex-col items-center justify-center text-center space-y-3">
                {data.invoice.balance_amount > 0 && data.invoice.payment_status !== 'deferred' ? (
                  <>
                    <div className="p-3 bg-white rounded-xl shadow-inner inline-block">
                      <QrCode className="w-24 h-24 text-slate-950" />
                    </div>
                    <div className="text-xs text-slate-400">
                      Scan with any UPI App (GPay, PhonePe, Paytm)
                    </div>
                    <button
                      onClick={async () => {
                        if (!data?.invoice) return;
                        try {
                          await billingApi.simulateOnlinePayment({
                            invoice_number: data.invoice.invoice_number,
                            amount: data.invoice.balance_amount,
                          });
                          alert('Payment simulated successfully! Invoice marked paid.');
                          fetchProfile();
                        } catch (e: any) {
                          alert('Payment simulation failed');
                        }
                      }}
                      className="w-full py-2 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow transition-colors flex items-center justify-center gap-2"
                    >
                      <CreditCard className="w-4 h-4" />
                      Simulate Instant UPI Payment (₹{data.invoice.balance_amount.toFixed(2)})
                    </button>
                  </>
                ) : (
                  <div className="py-4 space-y-2">
                    <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
                    <div className="text-sm font-bold text-white">All Hospital Dues Cleared</div>
                    <p className="text-xs text-slate-400">
                      {data.invoice.payment_status === 'deferred'
                        ? 'Payment deferred for critical emergency transfer.'
                        : 'No pending payments. Administrative clearance recorded.'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Plain-Language Care Summary Section */}
        {summary ? (
          <div className="space-y-6">
            {/* Overview Card */}
            <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md">
              <h3 className="text-base font-bold text-white flex items-center gap-2.5 mb-3">
                <FileText className="w-5 h-5 text-green-400" />
                <span>Recovery & Care Summary</span>
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                {summary.summary}
              </p>
            </Card>

            {/* Prescribed Medications Schedule */}
            {summary.medications && summary.medications.length > 0 && (
              <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md">
                <h3 className="text-base font-bold text-white flex items-center gap-2.5 mb-4">
                  <Pill className="w-5 h-5 text-primary-400" />
                  <span>Prescribed Medications & Schedule</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {summary.medications.map((med, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-slate-700 transition-colors"
                    >
                      <div className="font-semibold text-white text-sm">{med.name}</div>
                      <div className="text-xs text-primary-300 font-medium mt-1">
                        {med.dosage} • {med.frequency}
                      </div>
                      {med.purpose && (
                        <div className="text-[11px] text-slate-400 mt-1.5">
                          Purpose: {med.purpose}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Activity & Warning Signs */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Activity & Diet Instructions */}
              <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md">
                <h3 className="text-base font-bold text-white flex items-center gap-2.5 mb-3">
                  <ActivitySquare className="w-5 h-5 text-teal-400" />
                  <span>Activity & Diet Guidelines</span>
                </h3>
                <ul className="space-y-2 text-sm text-slate-300">
                  {summary.activity_restrictions && summary.activity_restrictions.length > 0 ? (
                    summary.activity_restrictions.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-green-400 shrink-0 font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-slate-400">Standard activity as tolerated.</li>
                  )}
                </ul>
              </Card>

              {/* Warning Signs */}
              <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md">
                <h3 className="text-base font-bold text-white flex items-center gap-2.5 mb-3">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  <span>When to Seek Immediate Medical Attention</span>
                </h3>
                <ul className="space-y-2 text-sm text-amber-200/90">
                  {summary.warning_signs && summary.warning_signs.length > 0 ? (
                    summary.warning_signs.map((sign, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-400 shrink-0 font-bold">!</span>
                        <span>{sign}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-slate-400">Contact emergency services if you experience severe shortness of breath or chest pain.</li>
                  )}
                </ul>
              </Card>
            </div>

            {/* Follow Up & Emergency Contacts */}
            <Card className="bg-slate-900 border-slate-800 p-6 rounded-xl shadow-md">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-primary-400" />
                    <span>Follow-Up Appointment</span>
                  </h4>
                  <p className="text-sm text-slate-200">
                    {summary.follow_up_instructions || 'Schedule follow up with your primary physician in 7–10 days.'}
                  </p>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Phone className="w-4 h-4 text-red-400" />
                    <span>Emergency Contact</span>
                  </h4>
                  <p className="text-sm font-semibold text-red-300">
                    {summary.emergency_contact || 'Hospital Hotline: +1 (555) 019-9000 or Dial 911'}
                  </p>
                </div>
              </div>
            </Card>
          </div>
        ) : (
          <Card className="bg-slate-900 border-slate-800 p-8 rounded-xl text-center space-y-3">
            <Clock className="w-10 h-10 text-primary-400 mx-auto" />
            <h3 className="text-lg font-bold text-white">Discharge Summary in Progress</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Your medical care team is currently preparing your clinical discharge summary and recovery package. It will automatically appear here once approved by your physician.
            </p>
          </Card>
        )}

        {/* Security & Authenticity Banner */}
        <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-green-400 shrink-0" />
            <span>This is an official clinical document record securely stored with AES/JWT encryption.</span>
          </div>
          <span className="font-mono text-[11px] text-slate-500">ID: {patient.patient_code}</span>
        </div>
      </main>
    </div>
  );
};
