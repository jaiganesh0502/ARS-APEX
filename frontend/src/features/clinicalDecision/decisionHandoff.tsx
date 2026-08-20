import React from 'react';
import { CheckCircle, Info } from 'lucide-react';

import { ClinicalDecisionType } from '../../types';

export interface DecisionConfirmationNavigation {
  pathname: string;
  search?: string;
  state: { confirmationMessage: string };
}

export const getDecisionConfirmationNavigation = (
  decisionType: ClinicalDecisionType,
  patientId: number,
): DecisionConfirmationNavigation => decisionType === 'discharge'
  ? {
      pathname: `/patients/${patientId}/discharge`,
      state: { confirmationMessage: 'Discharge decision confirmed.' },
    }
  : {
      pathname: '/transfers/new',
      search: `?patientId=${patientId}`,
      state: { confirmationMessage: 'Transfer decision confirmed.' },
    };

export const DecisionHandoffNotice: React.FC<{
  message: string;
  nextStep: string;
}> = ({ message, nextStep }) => (
  <div className="space-y-4" role="status">
    <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
      <CheckCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <p className="font-semibold">{message}</p>
    </div>
    <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
      <Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <p>
        The next step is <strong>{nextStep}</strong>. This downstream workflow has not started automatically.
      </p>
    </div>
  </div>
);
