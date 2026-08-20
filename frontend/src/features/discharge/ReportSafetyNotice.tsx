import React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

import { DischargeReportStatus } from '../../types';

interface ReportSafetyNoticeProps {
  status: DischargeReportStatus;
}

export const ReportSafetyNotice: React.FC<ReportSafetyNoticeProps> = ({ status }) => {
  const isApproved = status === 'approved';

  return (
    <div className={`flex items-start gap-3 rounded-lg border p-4 text-sm leading-6 ${isApproved ? 'border-green-200 bg-green-50 text-green-950' : 'border-amber-300 bg-amber-50 text-amber-950'}`} role="note">
      {isApproved ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" /> : <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />}
      <div>
        <p className="font-semibold">{isApproved ? 'Physician-approved report' : 'Unapproved AI-assisted draft'}</p>
        <p>{isApproved
          ? 'This report is physician-approved. Final discharge and bed release are separate later steps.'
          : 'Any AI-assisted generated content requires physician review and sign-off. It does not discharge the patient or release the bed.'}
        </p>
      </div>
    </div>
  );
};
