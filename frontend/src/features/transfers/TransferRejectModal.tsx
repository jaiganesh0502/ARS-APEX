import React, { useState } from 'react';
import { XCircle, AlertTriangle } from 'lucide-react';
import { Button } from '../../components/common/Button';

interface TransferRejectModalProps {
  isOpen: boolean;
  patientName: string;
  specialty: string;
  sendingHospitalName?: string;
  isLoading: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

export const TransferRejectModal: React.FC<TransferRejectModalProps> = ({
  isOpen,
  patientName,
  specialty,
  sendingHospitalName,
  isLoading,
  onClose,
  onConfirm,
}) => {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim() || reason.trim().length < 3) {
      setError('A mandatory clinical rejection reason is required (at least 3 characters).');
      return;
    }
    setError('');
    onConfirm(reason.trim());
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-red-50 text-red-700 rounded-xl">
            <XCircle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Reject Transfer Request</h3>
            <p className="text-xs text-slate-500">
              Provide justification for sending physician review and re-matching
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
              <span className="font-semibold text-primary-700">{specialty}</span>
            </div>
            {sendingHospitalName && (
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 font-medium">Origin Facility:</span>
                <span className="font-medium text-slate-800">{sendingHospitalName}</span>
              </div>
            )}
          </div>

          {/* Clinical Justification Input */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1.5">
              Reason for Rejection <span className="text-red-600">*</span>:
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError('');
              }}
              placeholder="e.g., Critical care unit at maximum census. No ventilator available."
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-red-500/20 focus:border-red-500 text-xs text-slate-800"
              required
            />
            {error && <p className="text-red-600 font-semibold mt-1">{error}</p>}
          </div>

          {/* Re-match Info Alert */}
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5 text-amber-900">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p>
              <strong>Follow-up Action:</strong> The sending hospital will be notified of this rejection and can re-open hospital matching to select an alternative accredited facility.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button
              variant="outline"
              type="submit"
              isLoading={isLoading}
              className="border-red-300 text-red-700 hover:bg-red-50"
              leftIcon={<XCircle className="w-4 h-4" />}
            >
              Confirm Rejection
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
