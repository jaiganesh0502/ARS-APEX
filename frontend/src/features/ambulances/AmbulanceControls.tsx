import React from 'react';
import {
  Ambulance,
  Building2,
  UserCheck,
  Navigation,
  CheckCircle2,
  XCircle,
  FlaskConical,
} from 'lucide-react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { AmbulanceDispatch, AmbulanceStatus } from '../../types';

interface AmbulanceControlsProps {
  dispatch: AmbulanceDispatch;
  isLoading: boolean;
  onAdvanceStatus: (targetStatus: AmbulanceStatus) => void;
  onRequestCancel: () => void;
}

export const AmbulanceControls: React.FC<AmbulanceControlsProps> = ({
  dispatch,
  isLoading,
  onAdvanceStatus,
  onRequestCancel,
}) => {
  const { status } = dispatch;

  const canCancel = status === 'requested' || status === 'en_route';

  return (
    <Card
      title="Simulation Controls"
      subtitle="Operational transit state machine progression"
      action={
        <span className="flex items-center gap-1 text-[11px] font-semibold text-primary-700 bg-primary-50 px-2 py-0.5 rounded border border-primary-200">
          <FlaskConical className="w-3 h-3" /> MVP Simulation Mode
        </span>
      }
    >
      <div className="space-y-4 text-xs">
        <p className="text-slate-600">
          Ambulance dispatch and GPS telemetry are simulated for this demonstration. Use the controls below to advance the transit workflow through each milestone.
        </p>

        {/* Current State Actions */}
        <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Current Milestone
            </span>
            <span className="font-mono font-bold text-slate-900 uppercase">
              {status.replace('_', ' ').toUpperCase()}
            </span>
          </div>

          <div className="pt-2 border-t border-slate-200/60 space-y-2">
            {status === 'requested' && (
              <Button
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isLoading}
                leftIcon={<Ambulance className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('en_route')}
              >
                Mark Ambulance En Route
              </Button>
            )}

            {status === 'en_route' && (
              <Button
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isLoading}
                leftIcon={<Building2 className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('arrived_pickup')}
              >
                Mark Arrived at Sending Hospital (Pickup)
              </Button>
            )}

            {status === 'arrived_pickup' && (
              <Button
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isLoading}
                leftIcon={<UserCheck className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('patient_onboard')}
              >
                Confirm Patient Onboard
              </Button>
            )}

            {status === 'patient_onboard' && (
              <Button
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isLoading}
                leftIcon={<Navigation className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('in_transit')}
              >
                Start Transfer & Depart Origin Facility
              </Button>
            )}

            {status === 'in_transit' && (
              <Button
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isLoading}
                leftIcon={<Building2 className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('arrived_destination')}
              >
                Mark Arrived at Receiving Hospital
              </Button>
            )}

            {status === 'arrived_destination' && (
              <Button
                variant="primary"
                size="md"
                className="w-full bg-green-600 hover:bg-green-700"
                isLoading={isLoading}
                leftIcon={<CheckCircle2 className="w-4 h-4" />}
                onClick={() => onAdvanceStatus('completed')}
              >
                Complete Clinical Handover & Transfer
              </Button>
            )}

            {status === 'completed' && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-900 font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span>Transfer is fully completed. Bed turnover active at origin facility.</span>
              </div>
            )}

            {status === 'cancelled' && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-900 font-semibold flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-600" />
                <span>Ambulance dispatch cancelled. Case is ready for re-dispatch.</span>
              </div>
            )}

            {canCancel && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-red-700 hover:bg-red-50"
                leftIcon={<XCircle className="w-3.5 h-3.5" />}
                onClick={onRequestCancel}
                disabled={isLoading}
              >
                Cancel Dispatch
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};
