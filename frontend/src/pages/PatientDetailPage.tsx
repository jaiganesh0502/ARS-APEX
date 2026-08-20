import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Send } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import { getBed, listAllBeds } from '../api/beds';
import { getPatientById } from '../api/patients';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { AdmissionStatus, BedSummary, PatientBedDetail, PatientDetail } from '../types';

export interface PatientOperationalIdentity {
  patientId: number;
  admissionId: number | null;
  epoch: number;
}

export const acceptsPatientOperationalResponse = (
  current: PatientOperationalIdentity,
  request: PatientOperationalIdentity,
): boolean => current.patientId === request.patientId
  && current.admissionId === request.admissionId
  && current.epoch === request.epoch;

export const operationalBedForPatient = (
  beds: BedSummary[],
  patient: Pick<PatientDetail, 'id' | 'admission' | 'bed'>,
): BedSummary | undefined => {
  if (!patient.admission) return undefined;
  return beds.find((bed) => bed.admission_id === patient.admission?.id && (
    ((bed.status === 'occupied' || bed.status === 'vacating') && bed.current_patient_id === patient.id)
    || ((bed.status === 'cleaning' || bed.status === 'available') && bed.current_patient_id === null)
  ));
};

export const bedCandidateForPatient = (
  beds: BedSummary[],
  patient: Pick<PatientDetail, 'id' | 'admission' | 'bed'>,
): BedSummary | undefined => operationalBedForPatient(beds, patient) ?? beds.find((bed) => (
  bed.ward === patient.bed?.ward && bed.bed_number === patient.bed?.bed_number
));

type OperationalLoadState = 'loading' | 'ready' | 'error';

export const PatientOperationalStatus: React.FC<{
  bed?: BedSummary;
  state: OperationalLoadState;
  admissionStatus?: AdmissionStatus;
}> = ({ bed, state, admissionStatus }) => {
  if (state === 'loading') {
    return <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600" aria-busy="true">Loading bed workflow status…</div>;
  }
  if (state === 'error') {
    return <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Bed workflow status unavailable.</div>;
  }
  if (!bed) return null;

  const displayedAdmissionStatus = bed.admission_status ?? admissionStatus;
  return <section className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700" aria-label="Bed release status">
    {displayedAdmissionStatus === 'discharged' && <p className="font-semibold text-green-800">Admission Status: Discharged</p>}
    {bed.status === 'occupied' && bed.release_eligible && <>
      <p className="font-semibold text-green-800">Discharge Report Approved</p>
      <p className="font-medium text-slate-900">Bed Release Pending</p>
    </>}
    {bed.status === 'vacating' && <p className="font-semibold text-amber-800">Bed Status: Vacating</p>}
    {bed.status === 'cleaning' && <p className="font-semibold text-purple-800">Bed Status: Cleaning</p>}
    {bed.status === 'available' && <p className="font-semibold text-green-800">Bed Status: Available</p>}
    {bed.status === 'reserved' && <p className="font-semibold text-purple-800">Bed Status: Reserved</p>}
    <p>Approval alone does not discharge the patient or release the bed.</p>
  </section>;
};

export const PatientBedInformation: React.FC<{
  historicalBed?: PatientBedDetail;
  operationalBed?: BedSummary;
  state: OperationalLoadState;
}> = ({ historicalBed, operationalBed, state }) => <Card title="Bed Information">
  <dl className="text-sm">
    <DetailRow label="Historical bed" value={historicalBed ? `${historicalBed.ward} / ${historicalBed.bed_number}` : undefined} />
    <DetailRow label="Current ward" value={operationalBed?.ward} />
    <DetailRow label="Current bed" value={operationalBed?.bed_number} />
    <DetailRow
      label="Current status"
      value={operationalBed
        ? <StatusBadge status={operationalBed.status} />
        : state === 'loading'
          ? 'Loading operational status'
          : 'Current operational status unavailable'}
    />
  </dl>
</Card>;

const formatDate = (value?: string) => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(value)) : 'Not recorded';
const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

const DetailRow: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => (
  <div className="grid grid-cols-[140px_1fr] gap-3 border-b border-slate-100 py-2 last:border-0"><dt className="text-slate-500">{label}</dt><dd className="font-medium text-slate-800">{value || 'Not recorded'}</dd></div>
);

export const PatientDetailPage: React.FC = () => {
  const { patientId } = useParams<{ patientId: string }>();
  return <PatientDetailRouteBoundary
    routeKey={patientId ?? ''}
    patientId={Number(patientId)}
  />;
};

export const PatientDetailRouteBoundary: React.FC<{
  routeKey: string;
  patientId: number;
}> = ({ routeKey, patientId }) => <PatientDetailRoute
  key={`patient:${routeKey}`}
  patientId={patientId}
/>;

const PatientDetailRoute: React.FC<{ patientId: number }> = ({ patientId: numericId }) => {
  const navigate = useNavigate();
  const [patient, setPatient] = useState<PatientDetail>();
  const [operationalBed, setOperationalBed] = useState<BedSummary>();
  const [operationalState, setOperationalState] = useState<OperationalLoadState>('loading');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const routeEpochRef = useRef(0);
  const operationalIdentityRef = useRef<PatientOperationalIdentity>({ patientId: numericId, admissionId: null, epoch: 0 });

  useEffect(() => {
    const epoch = routeEpochRef.current + 1;
    routeEpochRef.current = epoch;
    const routeRequest = { patientId: numericId, admissionId: null, epoch };
    operationalIdentityRef.current = routeRequest;
    setPatient(undefined);
    setOperationalBed(undefined);
    setOperationalState('loading');
    setLoading(true);
    setError(false);

    if (!Number.isInteger(numericId) || numericId < 1) {
      setError(true);
      setLoading(false);
      setOperationalState('error');
      return () => { if (routeEpochRef.current === epoch) routeEpochRef.current += 1; };
    }

    const load = async () => {
      try {
        const loadedPatient = await getPatientById(numericId);
        if (!acceptsPatientOperationalResponse(operationalIdentityRef.current, routeRequest) || loadedPatient.id !== numericId) return;

        const operationalRequest = {
          patientId: numericId,
          admissionId: loadedPatient.admission?.id ?? null,
          epoch,
        };
        operationalIdentityRef.current = operationalRequest;
        setPatient(loadedPatient);
        setLoading(false);

        try {
          const beds = await listAllBeds();
          if (!acceptsPatientOperationalResponse(operationalIdentityRef.current, operationalRequest)) return;
          const candidate = bedCandidateForPatient(beds, loadedPatient);
          if (!candidate) {
            setOperationalBed(undefined);
            setOperationalState('ready');
            return;
          }
          const detail = await getBed(candidate.id);
          if (!acceptsPatientOperationalResponse(operationalIdentityRef.current, operationalRequest) || detail.id !== candidate.id) return;
          setOperationalBed(operationalBedForPatient([detail], loadedPatient));
          setOperationalState('ready');
        } catch {
          if (acceptsPatientOperationalResponse(operationalIdentityRef.current, operationalRequest)) setOperationalState('error');
        }
      } catch {
        if (acceptsPatientOperationalResponse(operationalIdentityRef.current, routeRequest)) {
          setError(true);
          setLoading(false);
          setOperationalState('error');
        }
      }
    };

    void load();
    return () => {
      if (routeEpochRef.current === epoch) routeEpochRef.current += 1;
      operationalIdentityRef.current = { patientId: numericId, admissionId: null, epoch: routeEpochRef.current };
    };
  }, [numericId, reloadKey]);

  if (loading) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" /><span>Loading patient profile…</span></div>;
  if (error || !patient) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-center"><p className="font-semibold text-slate-900">Patient profile could not be loaded.</p><p className="text-sm text-slate-500">The patient may not exist or the service is unavailable.</p><div className="flex gap-2"><Button variant="outline" onClick={() => navigate('/patients')}>Back to Patients</Button><Button onClick={() => setReloadKey((value) => value + 1)}>Retry</Button></div></div>;

  const { demographics, admission, bed, medical_record: record } = patient;
  const displayedAdmissionStatus = operationalBed?.admission_status ?? admission?.status;
  const primaryAction = admission?.status === 'admitted'
    ? { label: 'Start Discharge / Transfer', path: `/patients/${patient.id}/decision` }
    : admission?.status === 'discharging'
      ? { label: 'Continue Discharge', path: `/patients/${patient.id}/discharge` }
      : admission?.status === 'transfer_pending'
        ? { label: 'Continue Transfer', path: `/transfers/new?patientId=${patient.id}` }
        : undefined;
  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate('/patients')}>Back to Patients</Button>
      <PageHeader title={`${demographics.first_name} ${demographics.last_name}`} description={`${patient.patient_code} · ${demographics.age} years · ${demographics.gender} · Blood group ${demographics.blood_group || 'not recorded'}`} action={primaryAction && <Button leftIcon={<Send className="h-4 w-4" />} onClick={() => navigate(primaryAction.path)}>{primaryAction.label}</Button>} />
      {admission && <div className="flex items-center gap-2 text-sm"><span className="text-slate-500">Admission status</span><StatusBadge status={displayedAdmissionStatus || admission.status} /></div>}
      <PatientOperationalStatus bed={operationalBed} state={operationalState} admissionStatus={displayedAdmissionStatus} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Patient Information"><dl className="text-sm"><DetailRow label="Date of birth" value={formatDate(demographics.date_of_birth)} /><DetailRow label="Gender" value={demographics.gender} /><DetailRow label="Blood group" value={demographics.blood_group} /><DetailRow label="Phone" value={demographics.phone} /><DetailRow label="Emergency contact" value={demographics.emergency_contact} /></dl></Card>
        <Card title="Admission"><dl className="text-sm"><DetailRow label="Admission date" value={formatDateTime(admission?.admission_date || '')} /><DetailRow label="Primary diagnosis" value={admission?.primary_diagnosis} /><DetailRow label="Attending doctor" value={admission?.attending_doctor} /><DetailRow label="Status" value={displayedAdmissionStatus && <StatusBadge status={displayedAdmissionStatus} />} /></dl></Card>
        <PatientBedInformation historicalBed={bed} operationalBed={operationalBed} state={operationalState} />
      </div>

      <Card title="Current Diagnosis / Medical Record"><div className="grid gap-5 lg:grid-cols-3"><section><h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Diagnosis</h3><p className="mt-2 text-sm text-slate-800">{record?.diagnosis || admission?.primary_diagnosis || 'Not recorded'}</p></section><section><h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Treatment Course</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{record?.treatment_course || 'Not recorded'}</p></section><section><h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Clinical Notes</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{record?.notes || 'Not recorded'}</p></section></div></Card>

      <Card title="Recent Vitals" subtitle="Latest five observations, newest first"><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="border-b bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-3 py-3">Temperature</th><th className="px-3 py-3">Heart Rate</th><th className="px-3 py-3">Blood Pressure</th><th className="px-3 py-3">SpO₂</th><th className="px-3 py-3">Recorded Time</th></tr></thead><tbody className="divide-y">{patient.vitals.map((vital) => <tr key={vital.id}><td className="px-3 py-3">{vital.temperature.toFixed(1)} °C</td><td className="px-3 py-3">{vital.heart_rate} bpm</td><td className="px-3 py-3">{vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg</td><td className="px-3 py-3">{vital.oxygen_saturation}%</td><td className="px-3 py-3">{formatDateTime(vital.recorded_at)}</td></tr>)}</tbody></table>{patient.vitals.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No vitals recorded.</p>}</div></Card>

      <Card title="Medications"><div className="overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead className="border-b bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-3 py-3">Medication</th><th className="px-3 py-3">Dosage</th><th className="px-3 py-3">Frequency</th><th className="px-3 py-3">Route</th><th className="px-3 py-3">Start Date</th><th className="px-3 py-3">End Date / Ongoing</th></tr></thead><tbody className="divide-y">{patient.medications.map((medication) => <tr key={medication.id}><td className="px-3 py-3 font-medium text-slate-900">{medication.medication_name}</td><td className="px-3 py-3">{medication.dosage}</td><td className="px-3 py-3">{medication.frequency}</td><td className="px-3 py-3">{medication.route}</td><td className="px-3 py-3">{formatDate(medication.start_date)}</td><td className="px-3 py-3">{medication.end_date ? formatDate(medication.end_date) : 'Ongoing'}</td></tr>)}</tbody></table>{patient.medications.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No medications recorded.</p>}</div></Card>
    </div>
  );
};
