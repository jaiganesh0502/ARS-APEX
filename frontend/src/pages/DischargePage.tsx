import axios from 'axios';
import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, FileText, Pencil, ShieldCheck } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { getBed, listAllBeds } from '../api/beds';
import { approveDischargeReport, editDischargeReport, generateDischargeReport, getAdmissionDischargeReport } from '../api/dischargeReports';
import { getPatientById } from '../api/patients';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { ReportReviewModal } from '../features/discharge/ReportReviewModal';
import { ReportSafetyNotice } from '../features/discharge/ReportSafetyNotice';
import { availableReportActions, effectiveReportContent } from '../features/discharge/reportState';
import { billingApi } from '../api/billing';
import { BedSummary, BillingClearance, DischargeReport, PatientDetail } from '../types';
import { CreditCard, CheckCircle, AlertCircle } from 'lucide-react';

export const BillingClearanceCard: React.FC<{
  admissionId: number;
  billing?: BillingClearance | null;
  onClearanceUpdated: () => void;
}> = ({ admissionId: _admissionId, billing, onClearanceUpdated }) => {
  const [clearing, setClearing] = useState(false);
  const [refInput, setRefInput] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');

  const handleClear = async () => {
    if (!billing) return;
    const ref = refInput.trim() || `CLR-${Date.now().toString().slice(-6)}`;
    try {
      setClearing(true);
      setError('');
      await billingApi.confirmBillingClearance(billing.id, {
        clearance_reference: ref,
        notes: 'Simulated finance department settlement',
      });
      setShowConfirm(false);
      onClearanceUpdated();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to clear billing');
    } finally {
      setClearing(false);
    }
  };

  return (
    <Card
      title="Billing Clearance Gate"
      subtitle="Parallel administrative stream: bed turnover is non-blocking while billing clearance is verified."
      action={
        billing?.status === 'cleared' ? (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle className="w-3.5 h-3.5 mr-1" /> Cleared
          </span>
        ) : billing?.status === 'deferred' ? (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Deferred (Emergency)
          </span>
        ) : (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertCircle className="w-3.5 h-3.5 mr-1" /> Pending Clearance
          </span>
        )
      }
    >
      <div className="space-y-4 text-sm">
        {billing?.status === 'pending' && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-900">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Billing Verification in Progress</p>
                <p className="mt-1 text-xs text-amber-800">
                  Bed turnover can continue, but final discharge authorization is held until billing clearance is confirmed.
                </p>
                <div className="mt-2 text-xs font-medium text-amber-950">
                  Outstanding Amount: ₹{Number(billing.outstanding_amount || 18500).toLocaleString('en-IN')}
                </div>
              </div>
            </div>
          </div>
        )}

        {billing?.status === 'cleared' && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-emerald-900">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Billing Clearance Confirmed</p>
                <p className="mt-1 text-xs text-emerald-800">
                  Reference: <span className="font-mono font-medium">{billing.clearance_reference}</span> | All dues settled. Patient handoff authorized.
                </p>
              </div>
            </div>
          </div>
        )}

        {billing?.status === 'pending' && !showConfirm && (
          <Button
            size="sm"
            variant="outline"
            leftIcon={<CreditCard className="w-4 h-4" />}
            onClick={() => setShowConfirm(true)}
          >
            Confirm Billing Clearance (Simulate Finance)
          </Button>
        )}

        {showConfirm && (
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
            <label className="block text-xs font-semibold text-slate-700">
              Clearance Reference / Transaction ID
            </label>
            <input
              type="text"
              className="w-full text-xs font-mono px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
              placeholder="e.g. TXN-INS-98765"
              value={refInput}
              onChange={(e) => setRefInput(e.target.value)}
            />
            {error && <p className="text-xs text-rose-600">{error}</p>}
            <div className="flex gap-2 justify-end">
              <Button size="sm" variant="ghost" onClick={() => setShowConfirm(false)} disabled={clearing}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleClear} isLoading={clearing}>
                Confirm Clearance
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};
import {
  acceptsPatientOperationalResponse,
  bedCandidateForPatient,
  operationalBedForPatient,
  PatientOperationalIdentity,
} from './PatientDetailPage';

type ViewMode = 'summary' | 'editing' | 'approval_review';
type BedLoadState = 'loading' | 'ready' | 'error';
type PrimaryLoadState = 'loading' | 'ready' | 'error';

export const isDischargeWorkflowReady = (states: {
  patient: PrimaryLoadState;
  report: PrimaryLoadState;
  bed: BedLoadState;
}): boolean => states.patient === 'ready' && states.report === 'ready';

export const acceptsDischargeBedResponse = (
  current: PatientOperationalIdentity,
  request: PatientOperationalIdentity,
  expectedBedId: number,
  responseBedId: number,
): boolean => acceptsPatientOperationalResponse(current, request) && expectedBedId === responseBedId;

export const ApprovedBedReleaseStatus: React.FC<{ bed?: BedSummary; state: BedLoadState }> = ({ bed, state }) => {
  let nextStep = 'Next Step: Bed workflow status unavailable';
  if (state === 'loading') nextStep = 'Loading bed workflow status…';
  else if (bed?.status === 'occupied' && bed.release_eligible) nextStep = 'Next Step: Start Bed Release';
  else if (bed?.status === 'occupied') nextStep = 'Next Step: Await bed release eligibility';
  else if (bed?.status === 'vacating') nextStep = 'Next Step: Confirm Patient Departed';
  else if (bed?.status === 'cleaning') nextStep = 'Next Step: Complete Cleaning';
  else if (bed?.status === 'available') nextStep = 'Ready for assignment';
  else if (bed?.status === 'reserved') nextStep = 'Bed Status: Reserved';

  const canStart = state === 'ready' && bed?.status === 'occupied' && bed.release_eligible;
  return <Card title="Report Approved" subtitle="Clinical approval is recorded; operational bed turnover remains a separate manual workflow.">
    <div className="space-y-3 text-sm leading-6 text-slate-700" aria-busy={state === 'loading' || undefined}>
      <p className="font-semibold text-slate-900">{nextStep}</p>
      {bed && <p>Bed Status: {bed.status.charAt(0).toUpperCase() + bed.status.slice(1)}</p>}
      <p>Approval alone does not discharge the patient or release the bed.</p>
      {canStart && <Link className="inline-flex rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800" to={`/beds/${bed.id}`}>Start Bed Release</Link>}
    </div>
  </Card>;
};

const formatDateTime = (value?: string | null) => value
  ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : 'Not recorded';

export const DischargePage: React.FC = () => {
  const { patientId } = useParams<{ patientId: string }>();
  return <DischargeRouteBoundary
    routeKey={patientId ?? ''}
    patientId={Number(patientId)}
  />;
};

export const DischargeRouteBoundary: React.FC<{
  routeKey: string;
  patientId: number;
}> = ({ routeKey, patientId }) => <DischargeRoute
  key={`discharge:${routeKey}`}
  patientId={patientId}
/>;

const DischargeRoute: React.FC<{ patientId: number }> = ({ patientId: numericPatientId }) => {
  const navigate = useNavigate();
  const [patient, setPatient] = useState<PatientDetail>();
  const [report, setReport] = useState<DischargeReport>();
  const [operationalBed, setOperationalBed] = useState<BedSummary>();
  const [billing, setBilling] = useState<BillingClearance | null>(null);
  const [bedLoadState, setBedLoadState] = useState<BedLoadState>('loading');
  const [patientLoadState, setPatientLoadState] = useState<PrimaryLoadState>('loading');
  const [reportLoadState, setReportLoadState] = useState<PrimaryLoadState>('loading');
  const [mode, setMode] = useState<ViewMode>('summary');
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [editorText, setEditorText] = useState('');
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const workflowEpochRef = useRef(0);
  const bedEpochRef = useRef(0);
  const operationalIdentityRef = useRef<PatientOperationalIdentity>({ patientId: numericPatientId, admissionId: null, epoch: 0 });

  useEffect(() => {
    const requestEpoch = workflowEpochRef.current + 1;
    workflowEpochRef.current = requestEpoch;
    const bedEpoch = bedEpochRef.current + 1;
    bedEpochRef.current = bedEpoch;
    const isCurrentRequest = () => workflowEpochRef.current === requestEpoch;
    const bedRouteRequest = { patientId: numericPatientId, admissionId: null, epoch: bedEpoch };
    operationalIdentityRef.current = bedRouteRequest;

    setPatient(undefined);
    setReport(undefined);
    setOperationalBed(undefined);
    setBedLoadState('loading');
    setPatientLoadState('loading');
    setReportLoadState('loading');
    setMode('summary');
    setEditorText('');
    setLoadError('');
    setActionError('');
    setGenerating(false);
    setSaving(false);
    setAcknowledged(false);
    setShowApprovalModal(false);

    if (!Number.isInteger(numericPatientId) || numericPatientId < 1) {
      setLoadError('The patient identifier is invalid.');
      setPatientLoadState('error');
      setReportLoadState('error');
      setBedLoadState('error');
      return () => { if (workflowEpochRef.current === requestEpoch) workflowEpochRef.current += 1; };
    }

    const load = async () => {
      try {
        const loadedPatient = await getPatientById(numericPatientId);
        if (!isCurrentRequest() || loadedPatient.id !== numericPatientId) return;
        setPatient(loadedPatient);
        setPatientLoadState('ready');
        if (!loadedPatient.admission) {
          setLoadError('This patient has no active admission.');
          setReportLoadState('error');
          setBedLoadState('error');
          return;
        }
        const operationalRequest = {
          patientId: numericPatientId,
          admissionId: loadedPatient.admission.id,
          epoch: bedEpoch,
        };
        operationalIdentityRef.current = operationalRequest;
        const loadOperationalBed = async () => {
          try {
            const beds = await listAllBeds();
            if (!acceptsPatientOperationalResponse(operationalIdentityRef.current, operationalRequest)) return;
            const candidate = bedCandidateForPatient(beds, loadedPatient);
            if (!candidate) {
              setOperationalBed(undefined);
              setBedLoadState('ready');
              return;
            }
            const detail = await getBed(candidate.id);
            if (!acceptsDischargeBedResponse(operationalIdentityRef.current, operationalRequest, candidate.id, detail.id)) return;
            setOperationalBed(operationalBedForPatient([detail], loadedPatient));
            setBedLoadState('ready');
          } catch {
            if (acceptsPatientOperationalResponse(operationalIdentityRef.current, operationalRequest)) setBedLoadState('error');
          }
        };
        void loadOperationalBed();

        try {
          const [loadedReport, loadedBilling] = await Promise.all([
            getAdmissionDischargeReport(loadedPatient.admission.id).catch((err) => {
              if (!axios.isAxiosError(err) || err.response?.status !== 404) throw err;
              return undefined;
            }),
            billingApi.getAdmissionBillingClearance(loadedPatient.admission.id).catch(() => null),
          ]);
          if (isCurrentRequest()) {
            if (loadedReport) setReport(loadedReport);
            setBilling(loadedBilling);
          }
        } catch (error) {
          if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error;
        }
        if (isCurrentRequest()) setReportLoadState('ready');
      } catch {
        if (isCurrentRequest()) {
          setLoadError('The discharge report could not be loaded.');
          setPatientLoadState((state) => state === 'ready' ? state : 'error');
          setReportLoadState('error');
        }
      }
    };

    void load();
    return () => {
      if (workflowEpochRef.current === requestEpoch) workflowEpochRef.current += 1;
      if (bedEpochRef.current === bedEpoch) bedEpochRef.current += 1;
      operationalIdentityRef.current = { patientId: numericPatientId, admissionId: null, epoch: bedEpochRef.current };
    };
  }, [numericPatientId, reloadKey]);

  const generate = async () => {
    if (!patient?.admission || generating) return;
    const requestEpoch = workflowEpochRef.current;
    setGenerating(true); setActionError('');
    try {
      const generatedReport = await generateDischargeReport(patient.admission.id);
      if (workflowEpochRef.current === requestEpoch) { setReport(generatedReport); setMode('summary'); }
    } catch {
      if (workflowEpochRef.current === requestEpoch) setActionError('The AI draft could not be generated. No report was created. Review the clinical decision and try again.');
    } finally {
      if (workflowEpochRef.current === requestEpoch) setGenerating(false);
    }
  };

  const startEditing = () => {
    if (!report) return;
    setActionError(''); setEditorText(effectiveReportContent(report)); setMode('editing');
  };

  const saveEdits = async () => {
    if (!report || saving) return;
    if (!editorText.trim()) { setActionError('Report text is required before it can be saved.'); return; }
    const requestEpoch = workflowEpochRef.current;
    setSaving(true); setActionError('');
    try {
      const editedReport = await editDischargeReport(report.id, editorText);
      if (workflowEpochRef.current === requestEpoch) { setReport(editedReport); setMode('summary'); }
    } catch {
      if (workflowEpochRef.current === requestEpoch) setActionError('The changes could not be saved. Your edited text is still available below.');
    } finally {
      if (workflowEpochRef.current === requestEpoch) setSaving(false);
    }
  };

  const startApprovalReview = () => { setActionError(''); setAcknowledged(false); setMode('approval_review'); };

  const approve = async () => {
    if (!report || !acknowledged || saving) return;
    const requestEpoch = workflowEpochRef.current;
    setSaving(true); setActionError('');
    try {
      const approvedReport = await approveDischargeReport(report.id);
      if (workflowEpochRef.current === requestEpoch) {
        setReport(approvedReport);
        setShowApprovalModal(false);
        setMode('summary');
        setReloadKey((value) => value + 1);
      }
    } catch {
      if (workflowEpochRef.current === requestEpoch) setActionError('The report could not be approved. The reviewed report remains available; please try again.');
    } finally {
      if (workflowEpochRef.current === requestEpoch) setSaving(false);
    }
  };

  if (!isDischargeWorkflowReady({ patient: patientLoadState, report: reportLoadState, bed: bedLoadState }) && !loadError) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" />Loading discharge report…</div>;
  if (loadError || !patient?.admission) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-center"><p className="font-semibold text-slate-900">{loadError || 'No active admission found.'}</p><div className="flex gap-2"><Button variant="outline" onClick={() => navigate(`/patients/${numericPatientId}`)}>Back to Patient</Button><Button onClick={() => setReloadKey((value) => value + 1)}>Retry</Button></div></div>;

  const { demographics, admission, bed } = patient;
  const effectiveContent = report ? effectiveReportContent(report) : '';
  const actions = report ? availableReportActions(report) : undefined;

  return <div className="space-y-6">
    <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(`/patients/${patient.id}`)}>Back to Patient</Button>
    <PageHeader title="Discharge Report" description="Create, review, and approve a clinical draft. Final discharge and bed release are separate later steps." />
    <Card title="Patient and admission" subtitle="Clinical context for this report workflow.">
      <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3"><Info label="Patient" value={`${demographics.first_name} ${demographics.last_name}`} /><Info label="Patient code" value={patient.patient_code} /><Info label="Primary diagnosis" value={admission.primary_diagnosis} /><Info label="Attending doctor" value={admission.attending_doctor} /><Info label="Admission date" value={formatDateTime(admission.admission_date)} /><Info label="Ward / bed" value={bed ? `${bed.ward} / ${bed.bed_number}` : 'Unassigned'} /><div><dt className="text-slate-500">Admission status</dt><dd className="mt-1"><StatusBadge status={admission.status} /></dd></div></dl>
    </Card>

    {!report && <Card title="Generate AI draft" subtitle="Generation is started only when you choose it.">
      <ReportSafetyNotice status="generated" />
      <div className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-600"><FileText className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" /><p>The draft uses persisted patient, admission, medical-record, medication, vital-sign, and confirmed clinical-decision information. Missing information remains marked as not documented.</p></div>
      {actionError && <p className="mt-4 text-sm font-medium text-rose-700" role="alert">{actionError}</p>}
      <div className="mt-6"><Button onClick={generate} isLoading={generating} disabled={generating}>{generating ? 'Generating draft' : actionError ? 'Retry Generation' : 'Generate AI Draft'}</Button></div>
    </Card>}

    {report && mode === 'summary' && <><ReportSafetyNotice status={report.status} /><Card title="Clinical discharge report" subtitle={`Generated with ${report.generation_model || 'the configured clinical model'}.`} action={<StatusBadge status={report.status} />}>
      {report.status === 'approved' && <ApprovalAudit report={report} />}<ReportText content={effectiveContent} />
      {actionError && <p className="mt-4 text-sm font-medium text-rose-700" role="alert">{actionError}</p>}
      {actions && (actions.canEdit || actions.canReview) && <div className="mt-6 flex flex-wrap gap-3"><Button variant="outline" leftIcon={<Pencil className="h-4 w-4" />} onClick={startEditing} disabled={!actions.canEdit}>Edit Draft</Button><Button leftIcon={<ShieldCheck className="h-4 w-4" />} onClick={startApprovalReview} disabled={!actions.canReview}>Review for Approval</Button></div>}
    </Card></>}
    {report?.status === 'approved' && mode === 'summary' && (
      <>
        <ApprovedBedReleaseStatus bed={operationalBed} state={bedLoadState} />
        <BillingClearanceCard
          admissionId={admission.id}
          billing={billing}
          onClearanceUpdated={() => setReloadKey((v) => v + 1)}
        />
      </>
    )}

    {report && mode === 'editing' && <><ReportSafetyNotice status={report.status} /><Card title="Edit discharge report" subtitle="Changes remain a physician-reviewed report and do not finalize discharge.">
      <label className="block text-sm font-semibold text-slate-800" htmlFor="discharge-report-editor">Report text</label><textarea id="discharge-report-editor" className="mt-2 min-h-96 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm leading-6 text-slate-800" value={editorText} onChange={(event) => setEditorText(event.target.value)} />
      {actionError && <p className="mt-4 text-sm font-medium text-rose-700" role="alert">{actionError}</p>}
      <div className="mt-6 flex flex-wrap justify-between gap-3"><Button variant="outline" onClick={() => { setMode('summary'); setActionError(''); }} disabled={saving}>Cancel</Button><Button onClick={saveEdits} isLoading={saving}>Save Changes</Button></div>
    </Card></>}

    {report && mode === 'approval_review' && <><ReportSafetyNotice status={report.status} /><Card title="Review report for approval" subtitle="Read the effective report before recording physician approval." action={<StatusBadge status={report.status} />}>
      <dl className="mb-5 grid gap-4 text-sm sm:grid-cols-2"><Info label="Patient" value={`${demographics.first_name} ${demographics.last_name} (${patient.patient_code})`} /><Info label="Generation model" value={report.generation_model} /></dl><ReportText content={effectiveContent} />
      <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 p-3 text-sm leading-6 text-slate-700"><input type="checkbox" className="mt-1" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I have reviewed the full report and understand that approval records this report only; it does not discharge the patient or release the bed.</span></label>
      {actionError && <p className="mt-4 text-sm font-medium text-rose-700" role="alert">{actionError}</p>}
      <div className="mt-6 flex flex-wrap justify-between gap-3"><Button variant="outline" onClick={() => { setMode('summary'); setActionError(''); }} disabled={saving}>Back to Report</Button><Button onClick={() => setShowApprovalModal(true)} disabled={!acknowledged || saving}>Approve Report</Button></div>
    </Card></>}
    {showApprovalModal && <ReportReviewModal acknowledged={acknowledged} saving={saving} error={actionError} onAcknowledgedChange={setAcknowledged} onCancel={() => { if (!saving) setShowApprovalModal(false); }} onApprove={approve} />}
  </div>;
};

const Info: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-medium text-slate-900">{value || 'Not recorded'}</dd></div>;
const ReportText: React.FC<{ content: string }> = ({ content }) => <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-4 font-mono text-sm leading-6 text-slate-800">{content}</pre>;
const ApprovalAudit: React.FC<{ report: DischargeReport }> = ({ report }) => <div className="mb-5 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-950"><p className="font-semibold">Approved by {report.approving_doctor_name || 'the reviewing doctor'} on {formatDateTime(report.approved_at)}.</p><p>Final discharge and bed release are separate later steps.</p></div>;
