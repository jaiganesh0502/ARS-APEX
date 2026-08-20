import { describe, expect, it } from 'vitest';

import type { DischargeReport } from '../../types';
import { availableReportActions, effectiveReportContent } from './reportState';

const generatedReport: DischargeReport = {
  id: 1,
  patient_id: 2,
  admission_id: 3,
  generated_content: 'AI draft',
  edited_content: null,
  effective_content: 'AI draft',
  generation_provider: 'replicate',
  generation_model: 'configured-model',
  status: 'generated',
  approving_doctor_name: null,
  approved_by: null,
  approved_at: null,
  created_at: '2026-08-19T00:00:00Z',
  updated_at: '2026-08-19T00:00:00Z',
};

describe('discharge report state helpers', () => {
  it('uses doctor-edited content when present', () => {
    expect(effectiveReportContent({ ...generatedReport, edited_content: 'Doctor revision' }))
      .toBe('Doctor revision');
  });

  it('preserves an intentionally empty doctor edit', () => {
    expect(effectiveReportContent({ ...generatedReport, edited_content: '' }))
      .toBe('');
  });

  it('falls back to generated content only when no doctor edit is present', () => {
    expect(effectiveReportContent({ ...generatedReport, edited_content: null }))
      .toBe('AI draft');
    expect(effectiveReportContent({ ...generatedReport, edited_content: undefined }))
      .toBe('AI draft');
  });

  it('makes approved reports read-only', () => {
    expect(availableReportActions({ ...generatedReport, status: 'approved' }))
      .toEqual({ canEdit: false, canReview: false });
  });

  it('keeps legacy draft reports out of the edit and approval workflow', () => {
    expect(availableReportActions({ ...generatedReport, status: 'draft' }))
      .toEqual({ canEdit: false, canReview: false });
  });
});
