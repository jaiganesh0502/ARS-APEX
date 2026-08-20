import axios from 'axios';
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, Check, Stethoscope, Truck } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  CLINICAL_SPECIALTIES,
  confirmClinicalDecision,
  createClinicalDecision,
  getClinicalDecision,
  updateClinicalDecision,
} from '../api/clinicalDecisions';
import { getPatientById } from '../api/patients';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { getDecisionConfirmationNavigation } from '../features/clinicalDecision/decisionHandoff';
import { ClinicalDecision, ClinicalDecisionRequest, ClinicalDecisionType, PatientDetail, TransferUrgency } from '../types';

type Step = 'decision' | 'review';

const formatDateTime = (value?: string) => value
  ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : 'Not confirmed';

export const ClinicalDecisionPage: React.FC = () => {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const numericPatientId = Number(patientId);
  const [patient, setPatient] = useState<PatientDetail>();
  const [decision, setDecision] = useState<ClinicalDecision>();
  const [decisionType, setDecisionType] = useState<ClinicalDecisionType>();
  const [urgency, setUrgency] = useState<TransferUrgency>();
  const [specialty, setSpecialty] = useState('');
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [step, setStep] = useState<Step>('decision');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    if (!Number.isInteger(numericPatientId) || numericPatientId < 1) {
      setError('The patient identifier is invalid.'); setLoading(false); return;
    }
    setLoading(true); setError('');
    try {
      const loadedPatient = await getPatientById(numericPatientId);
      setPatient(loadedPatient);
      if (!loadedPatient.admission) { setError('This patient has no active admission.'); return; }
      try {
        const current = await getClinicalDecision(loadedPatient.admission.id);
        setDecision(current);
        setDecisionType(current.decision_type);
        setUrgency(current.transfer_urgency);
        setSpecialty(current.required_specialty || '');
        setReason(current.reason);
        setNotes(current.notes || '');
      } catch (requestError) {
        if (!axios.isAxiosError(requestError) || requestError.response?.status !== 404) throw requestError;
      }
    } catch {
      setError('The clinical decision screen could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [numericPatientId, reloadKey]);

  useEffect(() => { load(); }, [load]);

  const request = (): ClinicalDecisionRequest => ({
    decision_type: decisionType as ClinicalDecisionType,
    reason: reason.trim(),
    notes: notes.trim() || undefined,
    ...(decisionType === 'transfer' ? { transfer_urgency: urgency, required_specialty: specialty } : {}),
  });

  const validate = () => {
    if (!decisionType) return 'Choose Discharge Patient or Transfer Patient.';
    if (!reason.trim()) return 'A clinical reason is required.';
    if (decisionType === 'transfer' && !urgency) return 'Choose the transfer urgency.';
    if (decisionType === 'transfer' && !specialty) return 'Choose the required specialty.';
    return '';
  };

  const review = () => {
    const message = validate();
    setFormError(message);
    if (!message) setStep('review');
  };

  const prepareConfirmation = async () => {
    if (!patient?.admission) return;
    setSaving(true); setFormError('');
    try {
      const saved = decision
        ? await updateClinicalDecision(decision.id, request())
        : await createClinicalDecision(patient.admission.id, request());
      setDecision(saved);
      setShowConfirm(true);
    } catch {
      setFormError('The draft could not be saved. Review the fields and try again.');
    } finally { setSaving(false); }
  };

  const confirm = async () => {
    if (!decision) return;
    setSaving(true); setFormError('');
    try {
      const confirmed = await confirmClinicalDecision(decision.id);
      setDecision(confirmed);
      setShowConfirm(false);
      const destination = getDecisionConfirmationNavigation(confirmed.decision_type, numericPatientId);
      navigate({ pathname: destination.pathname, search: destination.search }, { state: destination.state });
    } catch {
      setFormError('The decision could not be confirmed. It may already have changed.');
      setShowConfirm(false);
    } finally { setSaving(false); }
  };

  if (loading) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" />Loading clinical decision…</div>;
  if (error || !patient?.admission) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-center"><p className="font-semibold text-slate-900">{error || 'No active admission found.'}</p><div className="flex gap-2"><Button variant="outline" onClick={() => navigate(`/patients/${numericPatientId}`)}>Back to Patient</Button><Button onClick={() => setReloadKey((value) => value + 1)}>Retry</Button></div></div>;

  const { demographics, admission, bed } = patient;
  const confirmed = decision?.status === 'confirmed';

  if (confirmed) {
    return <div className="space-y-6">
      <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(`/patients/${patient.id}`)}>Back to Patient</Button>
      <PageHeader title="Current Clinical Decision" description="This decision has been confirmed and is preserved as part of the clinical record." />
      <Card><dl className="grid gap-4 text-sm sm:grid-cols-2"><Info label="Patient" value={`${demographics.first_name} ${demographics.last_name} (${patient.patient_code})`} /><Info label="Decision" value={decision.decision_type === 'discharge' ? 'Discharge Patient' : 'Transfer Patient'} /><Info label="Urgency" value={decision.transfer_urgency?.replace('_', '-')} /><Info label="Required Specialty" value={decision.required_specialty} /><Info label="Reason" value={decision.reason} /><Info label="Notes" value={decision.notes} /><Info label="Decided by" value={decision.decided_by_name} /><Info label="Decision time" value={formatDateTime(decision.decided_at)} /><div><dt className="text-slate-500">Status</dt><dd className="mt-1"><StatusBadge status={decision.status} /></dd></div></dl></Card>
      <Button onClick={() => decision.decision_type === 'discharge' ? navigate(`/patients/${patient.id}/discharge`) : navigate(`/transfers/new?patientId=${patient.id}`)}>{decision.decision_type === 'discharge' ? 'Continue to Discharge Report' : 'Continue to Transfer Workflow'}</Button>
    </div>;
  }

  return <div className="space-y-6">
    <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(`/patients/${patient.id}`)}>Back to Patient</Button>
    <PageHeader title="Clinical Decision" description="Choose the next step for this patient's current admission." />
    <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm sm:grid-cols-2 lg:grid-cols-4"><Info label="Patient" value={`${demographics.first_name} ${demographics.last_name}`} /><Info label="Patient Code" value={patient.patient_code} /><Info label="Age / Gender" value={`${demographics.age} / ${demographics.gender}`} /><Info label="Diagnosis" value={admission.primary_diagnosis} /><Info label="Ward / Bed" value={bed ? `${bed.ward} / ${bed.bed_number}` : 'Unassigned'} /><div><dt className="text-slate-500">Admission Status</dt><dd className="mt-1"><StatusBadge status={admission.status} /></dd></div></div>
    <div className="flex items-center gap-3 text-sm"><span className={`rounded-full px-3 py-1 font-semibold ${step === 'decision' ? 'bg-primary-700 text-white' : 'bg-slate-100 text-slate-600'}`}>1 Decision</span><span className="h-px w-8 bg-slate-300" /><span className={`rounded-full px-3 py-1 font-semibold ${step === 'review' ? 'bg-primary-700 text-white' : 'bg-slate-100 text-slate-600'}`}>2 Review</span></div>

    {step === 'decision' ? <Card title="Select the next clinical step">
      <div className="grid gap-4 md:grid-cols-2">
        <DecisionCard selected={decisionType === 'discharge'} title="Discharge Patient" description="Patient is clinically stable and can continue recovery outside the hospital." icon={<Stethoscope className="h-5 w-5" />} onClick={() => { setDecisionType('discharge'); setUrgency(undefined); setSpecialty(''); }} />
        <DecisionCard selected={decisionType === 'transfer'} title="Transfer Patient" description="Patient requires care at another hospital or specialist facility." icon={<Truck className="h-5 w-5" />} onClick={() => setDecisionType('transfer')} />
      </div>
      {decisionType && <div className="mt-6 space-y-5 border-t border-slate-100 pt-6">
        {decisionType === 'transfer' && <><fieldset><legend className="mb-2 text-sm font-semibold text-slate-800">Transfer Urgency *</legend><div className="flex flex-wrap gap-3"><Radio label="Emergency" checked={urgency === 'emergency'} onChange={() => setUrgency('emergency')} /><Radio label="Non-Emergency" checked={urgency === 'non_emergency'} onChange={() => setUrgency('non_emergency')} /></div></fieldset><label className="block text-sm font-semibold text-slate-800">Required Specialty *<select className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-normal" value={specialty} onChange={(event) => setSpecialty(event.target.value)}><option value="">Select specialty</option>{CLINICAL_SPECIALTIES.map((item) => <option key={item}>{item}</option>)}</select></label>{urgency === 'emergency' && <Notice warning text="Emergency transfers will follow an expedited workflow after the clinical decision is confirmed." />}{urgency === 'non_emergency' && <Notice text="The receiving facility will require confirmation before transport begins." />}</>}
        <label className="block text-sm font-semibold text-slate-800">{decisionType === 'discharge' ? 'Reason for discharge' : 'Reason for Transfer'} *<textarea className="mt-2 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 font-normal" placeholder={decisionType === 'discharge' ? 'Patient clinically stable for discharge.' : 'Explain why specialist or facility transfer is required.'} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <label className="block text-sm font-semibold text-slate-800">Clinical notes<textarea className="mt-2 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 font-normal" value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      </div>}
      {formError && <p className="mt-4 text-sm font-medium text-red-700">{formError}</p>}
      <div className="mt-6 flex justify-end"><Button onClick={review}>Review Decision</Button></div>
    </Card> : <Card title="Review Decision" subtitle="Confirm that the clinical information and consequences are correct.">
      <dl className="grid gap-4 text-sm sm:grid-cols-2"><Info label="Patient" value={`${demographics.first_name} ${demographics.last_name}`} /><Info label="Decision Type" value={decisionType === 'discharge' ? 'Discharge Patient' : 'Transfer Patient'} />{decisionType === 'transfer' && <><Info label="Urgency" value={urgency?.replace('_', '-')} /><Info label="Required Specialty" value={specialty} /></>}<Info label="Reason" value={reason} /><Info label="Notes" value={notes || 'None recorded'} /></dl>
      {formError && <p className="mt-4 text-sm font-medium text-red-700">{formError}</p>}
      <div className="mt-6 flex flex-wrap justify-between gap-3"><Button variant="outline" onClick={() => setStep('decision')} disabled={saving}>Back to Edit</Button><Button onClick={prepareConfirmation} isLoading={saving}>Confirm Decision</Button></div>
    </Card>}

    {showConfirm && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"><h2 id="confirm-title" className="text-lg font-semibold text-slate-900">Confirm {decisionType} decision?</h2><p className="mt-3 text-sm leading-6 text-slate-600">{decisionType === 'discharge' ? 'The patient will be marked as Discharging and the discharge report workflow can begin.' : 'The patient will be marked as Transfer Pending and the hospital matching workflow can begin.'}</p><div className="mt-6 flex justify-end gap-3"><Button variant="outline" onClick={() => setShowConfirm(false)} disabled={saving}>Cancel</Button><Button onClick={confirm} isLoading={saving}>Confirm</Button></div></div></div>}
  </div>;
};

const Info: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-medium text-slate-900">{value || 'Not applicable'}</dd></div>;
const Radio: React.FC<{ label: string; checked: boolean; onChange: () => void }> = ({ label, checked, onChange }) => <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm"><input type="radio" checked={checked} onChange={onChange} />{label}</label>;
const Notice: React.FC<{ text: string; warning?: boolean }> = ({ text, warning }) => <div className={`flex gap-3 rounded-md border p-3 text-sm ${warning ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-primary-200 bg-primary-50 text-primary-900'}`}><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{text}</div>;
const DecisionCard: React.FC<{ selected: boolean; title: string; description: string; icon: React.ReactNode; onClick: () => void }> = ({ selected, title, description, icon, onClick }) => <button type="button" role="radio" aria-checked={selected} onClick={onClick} className={`relative rounded-lg border-2 p-5 text-left transition ${selected ? 'border-primary-700 bg-primary-50' : 'border-slate-200 bg-white hover:border-slate-400'}`}><div className="flex items-center gap-3 font-semibold text-slate-900">{icon}{title}{selected && <span className="ml-auto inline-flex items-center gap-1 text-xs text-primary-700"><Check className="h-4 w-4" />Selected</span>}</div><p className="mt-3 text-sm leading-6 text-slate-600">{description}</p></button>;
