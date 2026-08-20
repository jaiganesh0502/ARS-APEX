import React, { useState } from 'react';
import { XCircle, AlertTriangle } from 'lucide-react';
import { Button } from '../../components/common/Button';

interface AmbulanceCancelModalProps {
  isOpen: boolean;
  dispatchReference: string;
  patientName?: string;
  isLoading: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

export const AmbulanceCancelModal: React.FC<AmbulanceCancelModalProps> = ({
  isOpen,
  dispatchReference,
  patientName,
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
      setError('A valid cancellation reason is required (at least 3 characters).');
      return;
    }
    setError('');
    onConfirm(reason.trim());
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-red-50 text-red-700 rounded-xl">
            <XCircle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Cancel Ambulance Dispatch</h3>
            <p className="text-xs text-slate-500">
              Reverts transfer state to accepted for re-dispatch
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="my-5 space-y-4 text-xs">
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-500">Dispatch Reference:</span>
              <span className="font-mono font-bold text-slate-900">{dispatchReference}</span>
            </div>
            {patientName && (
              <div className="flex justify-between">
                <span className="text-slate-500">Patient:</span>
                <span className="font-semibold text-slate-800">{patientName}</span>
              </div>
            )}
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1.5">
              Reason for Cancellation <span className="text-red-600">*</span>:
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError('');
              }}
              placeholder="e.g., Clinical stabilization ordered prior to transport."
              className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-red-500/20 focus:border-red-500 text-xs text-slate-800"
              required
            />
            {error && <p className="text-red-600 font-semibold mt-1">{error}</p>}
          </div>

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2 text-amber-900">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-[11px]">
              Cancellation is only allowed before patient onboarding. After boarding, in-transit protocols apply.
            </p>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={onClose} disabled={isLoading}>
              Close
            </Button>
            <Button
              variant="outline"
              type="submit"
              isLoading={isLoading}
              className="border-red-300 text-red-700 hover:bg-red-50"
              leftIcon={<XCircle className="w-4 h-4" />}
            >
              Confirm Cancellation
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
