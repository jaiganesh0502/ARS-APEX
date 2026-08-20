import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  Clock,
  Navigation,
  ShieldAlert,
  Phone,
  User,
  FlaskConical,
  ExternalLink,
} from 'lucide-react';

import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import { AmbulanceTimeline } from '../features/ambulances/AmbulanceTimeline';
import { AmbulanceControls } from '../features/ambulances/AmbulanceControls';
import { AmbulanceCancelModal } from '../features/ambulances/AmbulanceCancelModal';
import { ambulanceApi } from '../api/ambulance';
import { AmbulanceDispatch, AmbulanceStatus } from '../types';

export const AmbulanceDetailPage: React.FC = () => {
  const { dispatchId } = useParams<{ dispatchId: string }>();
  const navigate = useNavigate();

  const [dispatch, setDispatch] = useState<AmbulanceDispatch | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);

  const fetchDispatchData = async () => {
    if (!dispatchId) return;
    setIsLoading(true);
    setError(null);
    try {
      const id = parseInt(dispatchId, 10);
      const data = await ambulanceApi.getDispatchDetail(id);
      setDispatch(data);
    } catch (err) {
      console.error('Failed to load dispatch detail', err);
      setError('Ambulance dispatch tracking record not found.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDispatchData();
  }, [dispatchId]);

  const handleAdvanceStatus = async (targetStatus: AmbulanceStatus) => {
    if (!dispatch) return;
    setIsActionLoading(true);
    try {
      const updated = await ambulanceApi.updateStatus(dispatch.id, targetStatus);
      setDispatch(updated);
      // Reload full detail
      await fetchDispatchData();
    } catch (err) {
      console.error('Failed to update status', err);
      alert('Unable to advance transit status. Please try again.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleConfirmCancel = async (reason: string) => {
    if (!dispatch) return;
    setIsActionLoading(true);
    try {
      const updated = await ambulanceApi.cancelDispatch(dispatch.id, reason);
      setDispatch(updated);
      setIsCancelModalOpen(false);
      await fetchDispatchData();
    } catch (err) {
      console.error('Failed to cancel dispatch', err);
      alert('Unable to cancel dispatch. Please try again.');
    } finally {
      setIsActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Spinner size="lg" />
        <span className="text-sm font-medium text-slate-600 mt-3">
          Loading ambulance vehicle telemetry and transit records...
        </span>
      </div>
    );
  }

  if (error || !dispatch) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => navigate('/ambulances')}
        >
          Back to Ambulance Fleet
        </Button>
        <Card title="Dispatch Unavailable">
          <p className="text-sm text-rose-600">{error || 'Dispatch not found.'}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Navigation Bar */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => navigate('/ambulances')}
        >
          Back to Ambulance Fleet
        </Button>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
            onClick={() => navigate(`/transfers/${dispatch.transfer_id}`)}
          >
            View Transfer Case #TRF-00{dispatch.transfer_id}
          </Button>
        </div>
      </div>

      {/* Header */}
      <PageHeader
        title={`Ambulance Tracking: ${dispatch.dispatch_reference}`}
        description="Real-time transit milestones, simulated navigation telemetry, and clinical handover coordination."
        action={<StatusBadge status={dispatch.status} />}
      />

      {/* Simulation Notice Banner */}
      <div className="p-3.5 bg-blue-50/75 border border-blue-200 rounded-xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600 text-white rounded-lg">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-blue-950 text-xs block">
              Simulation Mode Active
            </span>
            <span className="text-[11px] text-blue-800">
              Ambulance routing, distance computation, and ETAs are calculated using deterministic simulation parameters.
            </span>
          </div>
        </div>
        <span className="text-[10px] font-mono uppercase bg-blue-200/70 text-blue-950 px-2 py-1 rounded font-bold">
          ETA_MODE=simulation
        </span>
      </div>

      {/* Emergency Urgency Banner */}
      {dispatch.emergency && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-rose-950">
            <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <span className="font-bold text-xs block">Emergency Priority Transfer</span>
              <span className="text-[11px] text-rose-800">
                Expedited ambulance routing with prioritized dispatch buffer.
              </span>
            </div>
          </div>
          <span className="px-2.5 py-0.5 bg-rose-200 text-rose-950 font-bold text-[10px] rounded uppercase">
            Priority 1
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Telemetry, Routing & Controls */}
        <div className="space-y-6 lg:col-span-2">
          {/* Routing & Live Telemetry Card */}
          <Card title="Transit Telemetry & Route Details">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Pickup Facility */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                  Origin (Pickup Facility)
                </span>
                <h4 className="font-bold text-slate-900 flex items-center gap-1.5 text-sm">
                  <MapPin className="w-4 h-4 text-slate-500" />
                  {dispatch.pickup_name}
                </h4>
                <span className="text-[11px] font-mono text-slate-500 block">
                  Coords: {dispatch.pickup_latitude.toFixed(4)}, {dispatch.pickup_longitude.toFixed(4)}
                </span>
              </div>

              {/* Destination Facility */}
              <div className="p-4 bg-blue-50/50 rounded-xl border border-blue-200 space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 block">
                  Destination (Receiving Facility)
                </span>
                <h4 className="font-bold text-blue-950 flex items-center gap-1.5 text-sm">
                  <MapPin className="w-4 h-4 text-blue-600" />
                  {dispatch.destination_name}
                </h4>
                <span className="text-[11px] font-mono text-blue-700/80 block">
                  Coords: {dispatch.destination_latitude.toFixed(4)}, {dispatch.destination_longitude.toFixed(4)}
                </span>
              </div>
            </div>

            {/* Telemetry Metrics Bar */}
            <div className="mt-4 p-4 bg-slate-900 text-white rounded-xl grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Route Distance</span>
                <span className="text-base font-extrabold text-white mt-0.5 flex items-center gap-1">
                  <Navigation className="w-3.5 h-3.5 text-blue-400" />
                  {dispatch.distance_km} km
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Total Est. Duration</span>
                <span className="text-base font-extrabold text-white mt-0.5 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  {dispatch.estimated_duration_minutes} mins
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Current Simulated ETA</span>
                <span className="text-base font-extrabold text-emerald-400 mt-0.5 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-emerald-400" />
                  {dispatch.status === 'completed' ? '0 mins' : `${dispatch.current_eta_minutes} mins`}
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Assigned Vehicle</span>
                <span className="text-xs font-mono font-bold text-slate-200 mt-1 block truncate">
                  {dispatch.vehicle_number || 'TN-DEMO-101'}
                </span>
              </div>
            </div>

            {/* Driver Contact Info */}
            <div className="mt-4 p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-200 rounded-lg text-slate-700">
                  <User className="w-4 h-4" />
                </div>
                <div>
                  <span className="font-bold text-slate-900 block">{dispatch.driver_name || 'Rajesh Sharma'}</span>
                  <span className="text-[11px] text-slate-500">Certified Emergency Transport Specialist</span>
                </div>
              </div>

              {dispatch.driver_phone && (
                <span className="font-mono text-slate-700 flex items-center gap-1 font-semibold">
                  <Phone className="w-3.5 h-3.5 text-slate-400" /> {dispatch.driver_phone}
                </span>
              )}
            </div>
          </Card>

          {/* Patient Context Card */}
          <Card title="Patient Profile">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Patient Name</span>
                <span className="font-bold text-slate-900 text-sm block mt-0.5">
                  {dispatch.patient_name || 'Kavitha Rajan'}
                </span>
                <span className="text-slate-500 font-mono text-[11px]">{dispatch.patient_code || 'PT-1004'}</span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Primary Diagnosis</span>
                <span className="font-semibold text-slate-900 block mt-0.5 truncate">
                  {dispatch.primary_diagnosis || 'Acute Ischemic Stroke'}
                </span>
                <span className="text-slate-500 text-[11px]">Required: {dispatch.required_specialty || 'Neurology'}</span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Transfer Status</span>
                <span className="font-bold text-blue-700 block mt-0.5 uppercase">
                  {dispatch.transfer_status || 'ambulance_requested'}
                </span>
                <span className="text-slate-500 text-[11px]">
                  Ref: #TRF-00{dispatch.transfer_id}
                </span>
              </div>
            </div>
          </Card>

          {/* Simulation Progression Controls */}
          <AmbulanceControls
            dispatch={dispatch}
            isLoading={isActionLoading}
            onAdvanceStatus={handleAdvanceStatus}
            onRequestCancel={() => setIsCancelModalOpen(true)}
          />
        </div>

        {/* Right Column: Milestones Timeline */}
        <div className="space-y-6">
          <Card title="Transit Progression Milestones">
            <AmbulanceTimeline dispatch={dispatch} />
          </Card>
        </div>
      </div>

      {/* Cancel Modal */}
      <AmbulanceCancelModal
        isOpen={isCancelModalOpen}
        dispatchReference={dispatch.dispatch_reference}
        patientName={dispatch.patient_name}
        isLoading={isActionLoading}
        onClose={() => setIsCancelModalOpen(false)}
        onConfirm={handleConfirmCancel}
      />
    </div>
  );
};
