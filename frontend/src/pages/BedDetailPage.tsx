import axios from 'axios';
import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Clock3 } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import { completeBedCleaning, confirmPatientDeparted, getBed, startBedRelease } from '../api/beds';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { bedAction } from '../features/beds/bedState';
import { BedTransitionModal } from '../features/beds/BedTransitionModal';
import type { BedAction, BedDetail } from '../types';

export interface BedRouteIdentity {
  routeKey: string;
  bedId: number;
}

export interface BedRequestIdentity extends BedRouteIdentity {
  epoch: number;
}

export interface TaggedBedDetail extends BedRouteIdentity {
  bed: BedDetail;
}

export const acceptsBedResponse = (
  current: BedRequestIdentity,
  request: BedRequestIdentity,
  responseBedId: number,
): boolean => current.routeKey === request.routeKey
  && current.bedId === request.bedId
  && current.epoch === request.epoch
  && responseBedId === request.bedId;

export const bedForRoute = (
  state: TaggedBedDetail | undefined,
  route: BedRouteIdentity,
): BedDetail | undefined => state?.routeKey === route.routeKey
  && state.bedId === route.bedId
  && state.bed.id === route.bedId
  ? state.bed
  : undefined;

const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(new Date(value));

const formatEvent = (value: string) => value
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

const controlledErrorMessage = (error: unknown, fallback: string) => {
  if (!axios.isAxiosError(error)) return fallback;
  const data = error.response?.data as { detail?: string; error?: { message?: string } } | undefined;
  return data?.error?.message || data?.detail || fallback;
};

export const BedActionPanel: React.FC<{ bed: BedDetail; onAction: (action: BedAction) => void }> = ({ bed, onAction }) => {
  const action = bedAction(bed);

  if (action === 'start_release') return <div className="space-y-3"><p className="text-sm leading-6 text-slate-600">The approved discharge report permits this bed to begin the controlled release workflow.</p><Button onClick={() => onAction(action)}>Start Bed Release</Button></div>;
  if (action === 'patient_departed') return <div className="space-y-3"><p className="text-sm leading-6 text-slate-600">Confirm departure only after the patient has physically left the bed.</p><Button onClick={() => onAction(action)}>Confirm Patient Departed</Button></div>;
  if (action === 'cleaning_complete') return <div className="space-y-3"><p className="text-sm leading-6 text-slate-600">Confirm that cleaning is complete before making this bed available.</p><Button onClick={() => onAction(action)}>Mark Cleaning Complete</Button></div>;
  if (bed.status === 'occupied') return <p className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">Bed release cannot start because one or more release prerequisites are not satisfied.</p>;
  if (bed.status === 'available') return <p className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900">Ready for assignment</p>;
  if (bed.status === 'reserved') return <p className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">This reserved bed has no available workflow action.</p>;
  return null;
};

const Info: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-medium text-slate-900">{value}</dd></div>;

export const BedAdmissionContext: React.FC<{ bed: BedDetail }> = ({ bed }) => {
  if (bed.status === 'occupied' || bed.status === 'vacating') {
    return <Card title="Current patient" subtitle="Operational details needed for this bed workflow.">
      <dl className="grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-4"><Info label="Patient" value={bed.patient_name || 'Not recorded'} /><Info label="Patient ID" value={bed.patient_code || 'Not recorded'} /><Info label="Diagnosis" value={bed.primary_diagnosis || 'Not recorded'} /><div><dt className="text-slate-500">Admission status</dt><dd className="mt-1">{bed.admission_status ? <StatusBadge status={bed.admission_status} /> : 'Not recorded'}</dd></div></dl>
    </Card>;
  }

  if (bed.status === 'cleaning' || bed.status === 'available') {
    return <Card title="Historical admission" subtitle="Turnover context from the most recent discharged admission.">
      <dl className="grid gap-5 text-sm sm:grid-cols-3"><Info label="Admission ID" value={bed.admission_id ?? 'Not recorded'} /><div><dt className="text-slate-500">Admission status</dt><dd className="mt-1">{bed.admission_status ? <StatusBadge status={bed.admission_status} /> : 'Not recorded'}</dd></div><Info label="Diagnosis" value={bed.primary_diagnosis || 'Not recorded'} /></dl>
    </Card>;
  }

  return null;
};

export const BedDetailPage: React.FC = () => {
  const { bedId } = useParams<{ bedId: string }>();
  const route = { routeKey: bedId ?? '', bedId: Number(bedId) };
  const latestRouteRef = useRef<BedRouteIdentity>(route);
  latestRouteRef.current = route;

  return <BedDetailRoute
    key={route.routeKey}
    route={route}
    latestRouteRef={latestRouteRef}
  />;
};

const BedDetailRoute: React.FC<{
  route: BedRouteIdentity;
  latestRouteRef: React.MutableRefObject<BedRouteIdentity>;
}> = ({ route, latestRouteRef }) => {
  const navigate = useNavigate();
  const [bedState, setBedState] = useState<TaggedBedDetail>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [pendingAction, setPendingAction] = useState<BedAction>();
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const workflowEpochRef = useRef(0);
  const detailFocusRef = useRef<HTMLDivElement>(null);
  const bed = bedForRoute(bedState, route);

  const currentRequestIdentity = (): BedRequestIdentity => ({
    ...latestRouteRef.current,
    epoch: workflowEpochRef.current,
  });

  useEffect(() => {
    const request: BedRequestIdentity = {
      ...route,
      epoch: workflowEpochRef.current + 1,
    };
    workflowEpochRef.current = request.epoch;
    const isCurrent = (responseBedId: number) => acceptsBedResponse(
      currentRequestIdentity(),
      request,
      responseBedId,
    );

    setBedState(undefined);
    setLoading(true);
    setLoadError('');
    setActionError('');
    setPendingAction(undefined);
    setSaving(false);

    if (!Number.isInteger(route.bedId) || route.bedId < 1) {
      setLoadError('The bed identifier is invalid.');
      setLoading(false);
      return () => {
        if (workflowEpochRef.current === request.epoch) workflowEpochRef.current += 1;
      };
    }

    void getBed(route.bedId)
      .then((loadedBed) => {
        if (isCurrent(loadedBed.id)) setBedState({ ...route, bed: loadedBed });
      })
      .catch((error: unknown) => {
        if (isCurrent(request.bedId)) setLoadError(controlledErrorMessage(error, 'Bed details could not be loaded. Please try again.'));
      })
      .finally(() => {
        if (isCurrent(request.bedId)) setLoading(false);
      });

    return () => {
      if (workflowEpochRef.current === request.epoch) workflowEpochRef.current += 1;
    };
  }, [route.bedId, route.routeKey, reloadKey]);

  const performTransition = async () => {
    if (!pendingAction || !bed || saving) return;
    const request: BedRequestIdentity = {
      ...route,
      epoch: workflowEpochRef.current,
    };
    const isCurrent = (responseBedId: number) => acceptsBedResponse(
      currentRequestIdentity(),
      request,
      responseBedId,
    );
    const action = pendingAction;
    const transition = {
      start_release: startBedRelease,
      patient_departed: confirmPatientDeparted,
      cleaning_complete: completeBedCleaning,
    }[action];

    setSaving(true);
    setActionError('');
    try {
      const updatedBed = await transition(request.bedId);
      if (!isCurrent(updatedBed.id)) return;
      setBedState({ ...route, bed: updatedBed });
      setPendingAction(undefined);

      try {
        const refreshedBed = await getBed(request.bedId);
        if (isCurrent(refreshedBed.id)) setBedState({ ...route, bed: refreshedBed });
      } catch (error) {
        if (isCurrent(request.bedId)) setActionError(controlledErrorMessage(error, 'The transition was saved, but the latest bed details could not be refreshed.'));
      }
    } catch (error) {
      if (isCurrent(request.bedId)) setActionError(controlledErrorMessage(error, 'The bed transition could not be completed. Please review the current state and try again.'));
    } finally {
      if (isCurrent(request.bedId)) setSaving(false);
    }
  };

  if (loading) return <div className="flex min-h-96 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" /><span>Loading bed details…</span></div>;
  if (loadError || !bed) return <div className="flex min-h-96 flex-col items-center justify-center gap-4 text-center"><p className="font-semibold text-slate-900" role="alert">{loadError || 'Bed details are unavailable.'}</p><div className="flex flex-wrap justify-center gap-3"><Button variant="outline" onClick={() => navigate('/beds')}>Back to Bed Management</Button><Button onClick={() => { workflowEpochRef.current += 1; setReloadKey((value) => value + 1); }}>Retry</Button></div></div>;

  const orderedHistory = [...bed.transition_history].sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at));
  const inertBackground = pendingAction
    ? ({ inert: '', 'aria-hidden': true } as unknown as React.HTMLAttributes<HTMLDivElement>)
    : {};

  return <>
    <div ref={detailFocusRef} tabIndex={-1} className="space-y-6 outline-none" {...inertBackground}>
      <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" aria-hidden="true" />} onClick={() => navigate('/beds')}>Back to Bed Management</Button>
      <PageHeader title={`Bed ${bed.bed_number}`} description={`${bed.ward} · Operational status and release history`} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Bed details" className="lg:col-span-2">
          <dl className="grid gap-5 text-sm sm:grid-cols-3"><Info label="Ward" value={bed.ward} /><Info label="Bed" value={bed.bed_number} /><div><dt className="text-slate-500">Status</dt><dd className="mt-1"><StatusBadge status={bed.status} /></dd></div></dl>
        </Card>
        <Card title="Available action"><BedActionPanel bed={bed} onAction={(action) => { setActionError(''); setPendingAction(action); }} /></Card>
      </div>

      <BedAdmissionContext bed={bed} />

      {actionError && !pendingAction && <p className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-950" role="alert">{actionError}</p>}

      <Card title="Transition history" subtitle="Chronological bed workflow events.">
        {orderedHistory.length === 0
          ? <p className="py-6 text-center text-sm text-slate-500">No bed transitions have been recorded.</p>
          : <ol className="space-y-4">{orderedHistory.map((event, index) => <li key={`${event.created_at}-${event.event_type}-${index}`} className="flex gap-3 border-b border-slate-100 pb-4 last:border-0 last:pb-0"><span className="mt-0.5 rounded-full bg-slate-100 p-2 text-slate-500"><Clock3 className="h-4 w-4" aria-hidden="true" /></span><div><p className="font-semibold text-slate-900">{formatEvent(event.event_type)}</p><p className="mt-1 text-sm text-slate-600">{event.previous_status ? `${formatEvent(event.previous_status)} → ` : ''}{event.new_status ? formatEvent(event.new_status) : 'Status recorded'}</p><time className="mt-1 block text-xs text-slate-500" dateTime={event.created_at}>{formatDateTime(event.created_at)}</time></div></li>)}</ol>}
      </Card>
    </div>
    {pendingAction && <BedTransitionModal action={pendingAction} saving={saving} error={actionError} focusFallbackRef={detailFocusRef} onCancel={() => { if (!saving) { setPendingAction(undefined); setActionError(''); } }} onConfirm={() => void performTransition()} />}
  </>;
};
