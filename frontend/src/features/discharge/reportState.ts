import { DischargeReport } from '../../types';

export interface DischargeReportActions {
  canEdit: boolean;
  canReview: boolean;
}

export const effectiveReportContent = (report: DischargeReport): string =>
  report.edited_content ?? report.generated_content;

export const availableReportActions = (report: DischargeReport): DischargeReportActions => {
  const isEditableStatus = report.status === 'generated' || report.status === 'under_review';
  return {
    canEdit: isEditableStatus,
    canReview: isEditableStatus,
  };
};
