import React, { useEffect, useRef } from 'react';

import { Button } from '../../components/common/Button';

interface ReportReviewModalProps {
  acknowledged: boolean;
  saving?: boolean;
  error?: string;
  onAcknowledgedChange?: (acknowledged: boolean) => void;
  onCancel?: () => void;
  onApprove?: () => void;
}

const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const ReportReviewModal: React.FC<ReportReviewModalProps> = ({
  acknowledged,
  saving = false,
  error,
  onAcknowledgedChange,
  onCancel,
  onApprove,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const acknowledgementRef = useRef<HTMLInputElement>(null);
  const onCancelRef = useRef(onCancel);
  const savingRef = useRef(saving);

  onCancelRef.current = onCancel;
  savingRef.current = saving;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    acknowledgementRef.current?.focus();

    const keepFocusInDialog = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !savingRef.current) {
        event.preventDefault();
        onCancelRef.current?.();
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(focusableSelector) || []);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeElement = document.activeElement;
      if (event.shiftKey && (activeElement === first || !dialogRef.current?.contains(activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (activeElement === last || !dialogRef.current?.contains(activeElement))) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', keepFocusInDialog);
    return () => {
      document.removeEventListener('keydown', keepFocusInDialog);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="approve-report-title" aria-describedby="approve-report-consequences">
    <div ref={dialogRef} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl" aria-busy={saving}>
      <h2 id="approve-report-title" className="text-lg font-semibold text-slate-900">Approve discharge report?</h2>
      <p id="approve-report-consequences" className="mt-3 text-sm leading-6 text-slate-600">Approval records this report as physician-approved and creates an internal downstream event. It does not discharge the patient and does not release the bed.</p>
      <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 p-3 text-sm leading-6 text-slate-700">
        <input ref={acknowledgementRef} type="checkbox" className="mt-1" checked={acknowledged} onChange={(event) => onAcknowledgedChange?.(event.target.checked)} />
        <span>I have reviewed the full report and acknowledge the limited effect of approval.</span>
      </label>
      {error && <p className="mt-4 text-sm font-medium text-red-700" role="alert">{error}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button onClick={onApprove} disabled={!acknowledged} isLoading={saving}>Approve Report</Button>
      </div>
    </div>
  </div>;
};
