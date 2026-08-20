import React from 'react';
import {
  Check,
  Clock,
  Building2,
  UserCheck,
  Navigation,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { AmbulanceDispatch } from '../../types';

interface AmbulanceTimelineProps {
  dispatch: AmbulanceDispatch;
}

export const AmbulanceTimeline: React.FC<AmbulanceTimelineProps> = ({ dispatch }) => {
  const formatTime = (iso?: string) => {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  const isCancelled = dispatch.status === 'cancelled';

  // Step milestone states
  const isStep2Done = Boolean(dispatch.en_route_at);
  const isStep3Done = Boolean(dispatch.arrived_pickup_at);
  const isStep4Done = Boolean(dispatch.patient_onboard_at);
  const isStep5Done = Boolean(dispatch.departed_pickup_at);
  const isStep6Done = Boolean(dispatch.arrived_destination_at);
  const isStep7Done = Boolean(dispatch.completed_at);

  return (
    <div className="space-y-4 text-xs">
      <ol className="relative border-l border-slate-200 ml-3 space-y-6">
        {/* Step 1: Dispatch Requested */}
        <li className="ml-5">
          <div className="absolute -left-2 mt-0.5 w-4 h-4 bg-green-500 rounded-full border-2 border-white flex items-center justify-center text-white">
            <Check className="w-2.5 h-2.5" />
          </div>
          <div>
            <span className="font-bold text-slate-900 block text-xs">Dispatch Requested</span>
            <span className="text-slate-500 block text-[11px]">
              Assigned Vehicle: {dispatch.vehicle_number || 'TN-DEMO-101'} • {formatTime(dispatch.requested_at)}
            </span>
          </div>
        </li>

        {/* Step 2: En Route */}
        <li className={`ml-5 ${isStep2Done ? 'opacity-100' : 'opacity-50'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep2Done ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            {isStep2Done ? <Check className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">Ambulance En Route</span>
            <span className="text-slate-500 block text-[11px]">
              {isStep2Done
                ? `En route to origin facility • ${formatTime(dispatch.en_route_at)}`
                : 'Pending dispatch departure'}
            </span>
          </div>
        </li>

        {/* Step 3: Arrived at Pickup */}
        <li className={`ml-5 ${isStep3Done ? 'opacity-100' : 'opacity-50'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep3Done ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            {isStep3Done ? <Building2 className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">
              Arrived at Sending Hospital (Pickup)
            </span>
            <span className="text-slate-500 block text-[11px]">
              {isStep3Done
                ? `Ambulance staged at ${dispatch.pickup_name} • ${formatTime(dispatch.arrived_pickup_at)}`
                : `Awaiting arrival at ${dispatch.pickup_name}`}
            </span>
          </div>
        </li>

        {/* Step 4: Patient Onboard */}
        <li className={`ml-5 ${isStep4Done ? 'opacity-100' : 'opacity-50'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep4Done ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            {isStep4Done ? <UserCheck className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">Patient Onboard</span>
            <span className="text-slate-500 block text-[11px]">
              {isStep4Done
                ? `Patient loaded & prepped for transit • ${formatTime(dispatch.patient_onboard_at)}`
                : 'Medical team boarding patient'}
            </span>
          </div>
        </li>

        {/* Step 5: Patient In Transit */}
        <li className={`ml-5 ${isStep5Done ? 'opacity-100' : 'opacity-50'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep5Done ? 'bg-primary-600 animate-pulse' : 'bg-slate-300'
            }`}
          >
            {isStep5Done ? <Navigation className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">Patient In Transit</span>
            <span className="text-slate-500 block text-[11px]">
              {isStep5Done
                ? `Departed origin facility • Bed turnover started • ${formatTime(dispatch.departed_pickup_at)}`
                : 'Transit en route to destination'}
            </span>
          </div>
        </li>

        {/* Step 6: Arrived Destination */}
        <li className={`ml-5 ${isStep6Done ? 'opacity-100' : 'opacity-50'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep6Done ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            {isStep6Done ? <Building2 className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">
              Arrived at Receiving Hospital
            </span>
            <span className="text-slate-500 block text-[11px]">
              {isStep6Done
                ? `Staged at ${dispatch.destination_name} • ${formatTime(dispatch.arrived_destination_at)}`
                : `Destination: ${dispatch.destination_name}`}
            </span>
          </div>
        </li>

        {/* Step 7: Completed */}
        <li className={`ml-5 ${isStep7Done ? 'opacity-100' : 'opacity-40'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isStep7Done
                ? 'bg-green-500'
                : isCancelled
                ? 'bg-red-500'
                : 'bg-slate-300'
            }`}
          >
            {isStep7Done ? (
              <CheckCircle2 className="w-2.5 h-2.5" />
            ) : isCancelled ? (
              <XCircle className="w-2.5 h-2.5" />
            ) : (
              <Clock className="w-2.5 h-2.5" />
            )}
          </div>
          <div>
            <span
              className={`font-bold block text-xs ${
                isStep7Done ? 'text-green-950' : isCancelled ? 'text-red-950' : 'text-slate-800'
              }`}
            >
              {isStep7Done ? 'Transfer Completed' : isCancelled ? 'Dispatch Cancelled' : 'Handover & Completion'}
            </span>
            <span className="text-slate-500 block text-[11px]">
              {isStep7Done
                ? `Clinical handover complete • Transferred • ${formatTime(dispatch.completed_at)}`
                : isCancelled
                ? `Cancelled: ${dispatch.cancellation_reason || 'Operational delay'}`
                : 'Awaiting clinical handover at destination'}
            </span>
          </div>
        </li>
      </ol>
    </div>
  );
};
