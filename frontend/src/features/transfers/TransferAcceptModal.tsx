import React, { useState } from 'react';
import { BedDouble, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '../../components/common/Button';

interface TransferAcceptModalProps {
  isOpen: boolean;
  patientName: string;
  specialty: string;
  hospitalName?: string;
  availableBeds?: number;
  isLoading: boolean;
  onClose: () => void;
  onConfirm: (notes?: string) => void;
}

export const TransferAcceptModal: React.FC<TransferAcceptModalProps> = ({
  isOpen,
  patientName,
  specialty,
  hospitalName,
  availableBeds,
  isLoading,
  onClose,
  onConfirm,
}) => {
  const [notes, setNotes] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(notes.trim() || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-emerald-50 text-emerald-700 rounded-xl">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Accept Transfer & Reserve Bed</h3>
            <p className="text-xs text-slate-500">
              Confirm patient admission and hold specialty capacity
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="my-5 space-y-4 text-xs">
          {/* Summary Box */}
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2 text-slate-700">
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500 font-medium">Patient:</span>
              <span className="font-bold text-slate-900">{patientName}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500 font-medium">Required Specialty:</span>
              <span className="font-semibold text-blue-700">{specialty}</span>
            </div>
            {hospitalName && (
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
                <span className="text-slate-500 font-medium">Destination Facility:</span>
                <span className="font-medium text-slate-800">{hospitalName}</span>
              </div>
            )}
            {availableBeds !== undefined && (
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 font-medium flex items-center gap-1">
                  <BedDouble className="w-3.5 h-3.5 text-slate-400" /> Current Capacity:
                </span>
                <span className="font-bold text-emerald-700">
                  {availableBeds} {availableBeds === 1 ? 'bed' : 'beds'} free
                </span>
              </div>
            )}
          </div>

          {/* Atomic Reservation Notice */}
          <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-2.5 text-emerald-900">
            <AlertCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <p>
              <strong>Capacity Reservation Notice:</strong> Accepting this case will atomically decrement 1 bed slot in your facility&apos;s <strong>{specialty}</strong> capacity.
            </p>
          </div>

          {/* Optional Clinical Acceptance Notes */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1.5">
              Receiving Physician Notes (Optional):
            </label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g., Bed assigned in ICU-West. On-call catheterization team notified."
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 text-xs text-slate-800"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              isLoading={isLoading}
              leftIcon={<CheckCircle2 className="w-4 h-4" />}
            >
              Confirm Acceptance & Reserve Bed
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
