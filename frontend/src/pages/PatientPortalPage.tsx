import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  HeartPulse,
  Download,
  AlertTriangle,
  Calendar,
  Pill,
  Utensils,
  Activity,
  CheckCircle2,
  PhoneCall,
  Clock,
  Building,
  ArrowLeft,
  FileCheck2,
} from 'lucide-react';

import { getPatientById } from '../api/patients';
import { dischargePackagesApi } from '../api/dischargePackages';
import { Spinner } from '../components/common/Spinner';
import type { PatientDetail, DischargePackage } from '../types';

export const PatientPortalPage: React.FC = () => {
  const { patientId } = useParams<{ patientId: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [pkg, setPkg] = useState<DischargePackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const numId = patientId ? parseInt(patientId, 10) : 0;

  useEffect(() => {
    const fetchData = async () => {
      if (!numId) return;
      try {
        setLoading(true);
        setError('');
        const p = await getPatientById(numId);
        setPatient(p);

        if (p.admission?.id) {
          const pack = await dischargePackagesApi.getAdmissionDischargePackage(p.admission.id);
          setPkg(pack);
        }
      } catch (err: any) {
        setError('Unable to load patient care instructions at this time.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [numId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-slate-600">
        <Spinner size="lg" />
        <p className="mt-4 text-sm font-medium">Loading your care instructions…</p>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
        <div className="p-4 bg-rose-50 text-rose-700 rounded-xl border border-rose-200 max-w-md">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-rose-500" />
          <h2 className="text-lg font-bold">Document Not Available</h2>
          <p className="text-sm mt-1 text-rose-600">{error || 'Patient record could not be found.'}</p>
        </div>
      </div>
    );
  }

  const { demographics, admission } = patient;
  const summary = pkg?.patient_summary;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Navigation & Brand Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-md">
              <HeartPulse className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">
                MedOrchestrate Health System
              </h1>
              <p className="text-xs text-slate-500">Patient & Family Care Portal</p>
            </div>
          </div>

          <Link
            to={`/patients/${patient.id}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Staff View
          </Link>
        </div>

        {/* Patient Hero Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                  {pkg ? 'Discharge Package Ready' : 'Inpatient Care'}
                </span>
                <span className="text-xs font-mono text-slate-400">#{patient.patient_code}</span>
              </div>
              <h2 className="text-2xl font-extrabold text-slate-900 mt-1">
                {demographics.first_name} {demographics.last_name}
              </h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Primary Diagnosis: <span className="font-semibold text-slate-700">{admission?.primary_diagnosis || 'Under Evaluation'}</span>
              </p>
            </div>

            {pkg && (
              <a
                href={`/api/discharge-packages/${pkg.id}/pdf`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md transition shrink-0"
              >
                <Download className="w-4 h-4" />
                Download Discharge PDF
              </a>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 text-xs text-slate-600">
            <div>
              <span className="text-slate-400 block mb-0.5">Attending Doctor</span>
              <span className="font-semibold text-slate-800">{admission?.attending_doctor || 'Attending Physician'}</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Admission Date</span>
              <span className="font-semibold text-slate-800">
                {admission?.admission_date ? new Date(admission.admission_date).toLocaleDateString() : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Package Reference</span>
              <span className="font-semibold text-slate-800">{pkg ? `#PKG-${pkg.id.toString().padStart(5, '0')}` : 'Pending'}</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Billing Status</span>
              <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                <CheckCircle2 className="w-3.5 h-3.5" /> Cleared
              </span>
            </div>
          </div>
        </div>

        {/* Not Ready Banner */}
        {!pkg && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-center text-amber-900">
            <Clock className="w-8 h-8 text-amber-500 mx-auto mb-2" />
            <h3 className="text-base font-bold">Your Discharge Documents Are Being Prepared</h3>
            <p className="text-xs text-amber-700 mt-1 max-w-md mx-auto leading-relaxed">
              Your physician and care team are finalizing your discharge care plan and billing clearance. Please check back shortly or speak with your ward nurse.
            </p>
          </div>
        )}

        {/* Structured Patient-Friendly Care Guide */}
        {pkg && summary && (
          <div className="space-y-6">
            {/* Section 1: Why Admitted & Treatments */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-2">
                <div className="flex items-center gap-2 text-blue-600 font-bold text-sm">
                  <Building className="w-4 h-4" />
                  <h3>Why You Were in the Hospital</h3>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {summary.why_you_were_admitted || 'You completed inpatient clinical care and observation.'}
                </p>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-2">
                <div className="flex items-center gap-2 text-blue-600 font-bold text-sm">
                  <FileCheck2 className="w-4 h-4" />
                  <h3>Summary of Treatment Received</h3>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {summary.what_treatment_you_received || 'Inpatient therapy and medical management.'}
                </p>
              </div>
            </div>

            {/* Section 2: Medication Schedule */}
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-4">
              <div className="flex items-center gap-2 text-slate-900 font-bold text-base">
                <Pill className="w-5 h-5 text-indigo-600" />
                <h3>Your Medication Schedule</h3>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="bg-emerald-50/50 border border-emerald-200/80 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 block">
                    Medications to Take / Continue
                  </span>
                  <ul className="space-y-2 text-xs text-slate-700">
                    {summary.medications_to_take && summary.medications_to_take.length > 0 ? (
                      summary.medications_to_take.map((med, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                          <span>{med}</span>
                        </li>
                      ))
                    ) : (
                      <li>Take all medications strictly as directed by your pharmacy label.</li>
                    )}
                  </ul>
                </div>

                <div className="bg-rose-50/50 border border-rose-200/80 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-rose-800 block">
                    Medications to Stop
                  </span>
                  <ul className="space-y-2 text-xs text-slate-700">
                    {summary.medications_to_stop && summary.medications_to_stop.length > 0 ? (
                      summary.medications_to_stop.map((med, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 shrink-0" />
                          <span>{med}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-slate-500">No discontinued medications noted.</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>

            {/* Section 3: Diet & Activity */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-2">
                <div className="flex items-center gap-2 text-amber-700 font-bold text-sm">
                  <Utensils className="w-4 h-4" />
                  <h3>Diet Instructions</h3>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {summary.diet_instructions || 'Maintain balanced nutrition and adequate hydration.'}
                </p>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-2">
                <div className="flex items-center gap-2 text-emerald-700 font-bold text-sm">
                  <Activity className="w-4 h-4" />
                  <h3>Activity & Recovery Guidance</h3>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {summary.activity_instructions || 'Gradually resume daily activities; avoid heavy lifting.'}
                </p>
              </div>
            </div>

            {/* Section 4: Follow-Up Appointment */}
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-2">
              <div className="flex items-center gap-2 text-indigo-700 font-bold text-base">
                <Calendar className="w-5 h-5" />
                <h3>Follow-Up Care Plan</h3>
              </div>
              <p className="text-sm text-slate-800 leading-relaxed">
                {summary.follow_up_plan || 'Schedule a follow-up appointment with your doctor within 7-10 days.'}
              </p>
            </div>

            {/* Section 5: Warning Signs & Emergency Box */}
            <div className="bg-gradient-to-br from-rose-50 to-red-50 rounded-2xl border border-rose-200 shadow-sm p-6 sm:p-8 space-y-4">
              <div className="flex items-center gap-2 text-rose-800 font-extrabold text-base">
                <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
                <h3>Warning Signs — When to Contact Us</h3>
              </div>

              <ul className="grid sm:grid-cols-2 gap-3 text-xs text-rose-950">
                {summary.warning_signs && summary.warning_signs.length > 0 ? (
                  summary.warning_signs.map((sign, i) => (
                    <li key={i} className="flex items-start gap-2 bg-white/70 p-3 rounded-lg border border-rose-100">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-600 mt-1.5 shrink-0" />
                      <span>{sign}</span>
                    </li>
                  ))
                ) : (
                  <li className="bg-white/70 p-3 rounded-lg border border-rose-100">
                    High fever, chest pain, difficulty breathing, or sudden weakness.
                  </li>
                )}
              </ul>

              <div className="pt-2 flex items-center gap-3 text-xs text-rose-900 font-semibold bg-rose-100/70 p-3 rounded-xl border border-rose-200">
                <PhoneCall className="w-4 h-4 text-rose-700 shrink-0" />
                <p>{summary.when_to_seek_urgent_help || 'Call your doctor or visit the nearest emergency room immediately for severe pain or breathing trouble.'}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
