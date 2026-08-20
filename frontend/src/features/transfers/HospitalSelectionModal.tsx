import React from 'react';
import { Building2, AlertCircle, BedDouble, Navigation, CheckCircle2 } from 'lucide-react';
import { HospitalMatch } from '../../types';
import { Button } from '../../components/common/Button';

interface HospitalSelectionModalProps {
  isOpen: boolean;
  match: HospitalMatch | null;
  isLoading: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const HospitalSelectionModal: React.FC<HospitalSelectionModalProps> = ({
  isOpen,
  match,
  isLoading,
  onClose,
  onConfirm,
}) => {
  if (!isOpen || !match) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-primary-50 text-primary-700 rounded-xl">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Select receiving hospital?</h3>
            <p className="text-xs text-slate-500">
              Confirm physician handoff request to destination facility
            </p>
          </div>
        </div>

        <div className="my-5 space-y-4">
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-2.5 text-sm">
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500 font-medium">Hospital Name:</span>
              <span className="font-bold text-slate-900">{match.hospital_name}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500 font-medium">Required Specialty:</span>
              <span className="font-semibold text-primary-700">{match.required_specialty}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500 font-medium flex items-center gap-1">
                <BedDouble className="w-4 h-4 text-slate-400" /> Available Beds:
              </span>
              <span className="font-bold text-green-700">
                {match.available_beds} of {match.total_beds} beds free
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-500 font-medium flex items-center gap-1">
                <Navigation className="w-4 h-4 text-slate-400" /> Transit Distance:
              </span>
              <span className="font-bold text-slate-800">{match.distance_km} km</span>
            </div>
          </div>

          <div className="flex items-start gap-2.5 p-3.5 bg-amber-50 rounded-xl border border-amber-200 text-xs text-amber-800">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p>
              <strong>Notice:</strong> A transfer request will be prepared for this receiving facility. Bed capacity will be held and formally reserved upon receiving-hospital confirmation.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="primary"
            isLoading={isLoading}
            leftIcon={<CheckCircle2 className="w-4 h-4" />}
            onClick={onConfirm}
          >
            Confirm Selection
          </Button>
        </div>
      </div>
    </div>
  );
};
