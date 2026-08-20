import React, { useEffect, useRef } from 'react';

import { Button } from '../../components/common/Button';
import type { BedAction } from '../../types';

interface BedTransitionModalProps {
  action: BedAction;
  saving?: boolean;
  error?: string;
  focusFallbackRef?: React.RefObject<HTMLElement>;
  onCancel: () => void;
  onConfirm: () => void;
}

const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const dialogFocusTarget = (enabledActionCount: number): 'first-action' | 'dialog' =>
  enabledActionCount > 0 ? 'first-action' : 'dialog';

export const focusRestorationTarget = (
  openerConnected: boolean,
  fallbackConnected: boolean,
): 'opener' | 'fallback' | undefined => {
  if (openerConnected) return 'opener';
  if (fallbackConnected) return 'fallback';
  return undefined;
};

export const canDismissBedTransition = (saving: boolean): boolean => !saving;

const modalCopy: Record<BedAction, { title: string; description: string; confirmLabel: string }> = {
  start_release: {
    title: 'Start bed release?',
    description: "The patient's discharge report has been approved. The bed will move from Occupied to Vacating.",
    confirmLabel: 'Start Release',
  },
  patient_departed: {
    title: 'Confirm patient departure?',
    description: 'The bed will move to Cleaning and will no longer be assigned to the patient.',
    confirmLabel: 'Confirm Departure',
  },
  cleaning_complete: {
    title: 'Confirm cleaning is complete?',
    description: 'The bed will become available for another patient.',
    confirmLabel: 'Complete Cleaning',
  },
};

export const BedTransitionModal: React.FC<BedTransitionModalProps> = ({
  action,
  saving = false,
  error,
  focusFallbackRef,
  onCancel,
  onConfirm,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCancelRef = useRef(onCancel);
  const savingRef = useRef(saving);
  const copy = modalCopy[action];

  onCancelRef.current = onCancel;
  savingRef.current = saving;

  const enabledActions = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? []);

  const focusAvailableTarget = () => {
    const focusable = enabledActions();
    if (dialogFocusTarget(focusable.length) === 'first-action') focusable[0].focus();
    else dialogRef.current?.focus();
  };

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    focusAvailableTarget();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (canDismissBedTransition(savingRef.current)) {
          event.preventDefault();
          onCancelRef.current();
        }
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = enabledActions();
      if (focusable.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialogRef.current || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || active === dialogRef.current || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      const fallback = focusFallbackRef?.current ?? null;
      const target = focusRestorationTarget(Boolean(previousFocus?.isConnected), Boolean(fallback?.isConnected));
      if (target === 'opener') previousFocus?.focus();
      else if (target === 'fallback') fallback?.focus();
    };
  }, []);

  useEffect(() => {
    if (saving) dialogRef.current?.focus();
    else if (document.activeElement === dialogRef.current) focusAvailableTarget();
  }, [saving]);

  return <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4"
    role="dialog"
    aria-modal="true"
    aria-labelledby="bed-transition-title"
    aria-describedby="bed-transition-description"
    onMouseDown={(event) => {
      if (event.target === event.currentTarget && canDismissBedTransition(saving)) onCancel();
    }}
  >
    <div ref={dialogRef} tabIndex={-1} className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl outline-none" aria-busy={saving}>
      <h2 id="bed-transition-title" className="text-lg font-semibold text-slate-900">{copy.title}</h2>
      <p id="bed-transition-description" className="mt-3 text-sm leading-6 text-slate-600">{copy.description}</p>
      {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm font-medium text-red-800" role="alert">{error}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button onClick={onConfirm} isLoading={saving} disabled={saving}>{copy.confirmLabel}</Button>
      </div>
    </div>
  </div>;
};
