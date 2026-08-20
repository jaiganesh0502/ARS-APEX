import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { describe, expect, it } from 'vitest';

import {
  acceptsDischargeBedResponse,
  ApprovedBedReleaseStatus,
  DischargePage,
  isDischargeWorkflowReady,
} from '../../pages/DischargePage';
import type { BedSummary } from '../../types';
import { ReportReviewModal } from './ReportReviewModal';
import { ReportSafetyNotice } from './ReportSafetyNotice';

const bed = (overrides: Partial<BedSummary> = {}): BedSummary => ({
  id: 7,
  ward: 'North',
  bed_number: 'N-07',
  status: 'occupied',
  current_patient_id: 12,
  patient_name: 'Ada Lovelace',
  patient_code: 'PAT-12',
  admission_id: 20,
  admission_status: 'discharging',
  primary_diagnosis: 'Pneumonia',
  release_eligible: true,
  updated_at: '2026-08-19T09:30:00Z',
  ...overrides,
});

describe('discharge report presentation safety', () => {
  it('starts by loading the patient and optional report rather than generating one', () => {
    const html = renderToStaticMarkup(
      <StaticRouter location="/patients/12/discharge">
        <DischargePage />
      </StaticRouter>,
    );

    expect(html).toContain('Loading discharge report');
    expect(html).not.toContain('Generate AI Draft');
  });

  it('states that generated content is unapproved', () => {
    const html = renderToStaticMarkup(<ReportSafetyNotice status="generated" />);

    expect(html).toContain('requires physician review');
    expect(html).not.toContain('bed has been released');
  });

  it('keeps the safety warning after a doctor edit', () => {
    const html = renderToStaticMarkup(<ReportSafetyNotice status="under_review" />);

    expect(html).toContain('requires physician review');
    expect(html).not.toContain('patient has been discharged');
  });

  it('approval modal states the exact limited consequence', () => {
    const html = renderToStaticMarkup(<ReportReviewModal acknowledged={false} />);

    expect(html).toContain('does not discharge the patient');
    expect(html).toContain('does not release the bed');
  });

  it('exposes the approval consequences as the modal description', () => {
    const html = renderToStaticMarkup(<ReportReviewModal acknowledged={false} />);

    expect(html).toContain('aria-describedby="approve-report-consequences"');
    expect(html).toContain('id="approve-report-consequences"');
  });

  it('keeps approval unavailable until the physician acknowledgement is checked', () => {
    const html = renderToStaticMarkup(<ReportReviewModal acknowledged={false} />);

    expect(html).toContain('disabled=""');
  });

  it('offers the bed workflow only for an approved eligible occupied bed', () => {
    const html = renderToStaticMarkup(
      <StaticRouter location="/patients/12/discharge">
        <ApprovedBedReleaseStatus bed={bed()} state="ready" />
      </StaticRouter>,
    );

    expect(html).toContain('Report Approved');
    expect(html).toContain('Next Step: Start Bed Release');
    expect(html).toContain('href="/beds/7"');
    expect(html).toContain('>Start Bed Release<');
    expect(html).toContain('Approval alone does not discharge the patient or release the bed');
  });

  it.each([
    ['vacating', 'Next Step: Confirm Patient Departed'],
    ['cleaning', 'Next Step: Complete Cleaning'],
    ['available', 'Ready for assignment'],
  ] as const)('shows truthful %s progress without an invalid start action', (status, expected) => {
    const html = renderToStaticMarkup(
      <StaticRouter location="/patients/12/discharge">
        <ApprovedBedReleaseStatus
          bed={bed({
            status,
            current_patient_id: status === 'vacating' ? 12 : null,
            patient_name: status === 'vacating' ? 'Ada Lovelace' : null,
            patient_code: status === 'vacating' ? 'PAT-12' : null,
            release_eligible: false,
          })}
          state="ready"
        />
      </StaticRouter>,
    );

    expect(html).toContain(expected);
    expect(html).not.toContain('href="/beds/7"');
    expect(html).not.toContain('>Start Bed Release<');
  });

  it('makes report presentation readiness independent of bed lookup readiness', () => {
    expect(isDischargeWorkflowReady({ patient: 'ready', report: 'ready', bed: 'loading' })).toBe(true);
    expect(isDischargeWorkflowReady({ patient: 'ready', report: 'ready', bed: 'error' })).toBe(true);
    expect(isDischargeWorkflowReady({ patient: 'ready', report: 'loading', bed: 'ready' })).toBe(false);
  });

  it('rejects stale and wrong-bed operational detail responses independently', () => {
    const request = { patientId: 12, admissionId: 20, epoch: 4 };

    expect(acceptsDischargeBedResponse(request, request, 7, 7)).toBe(true);
    expect(acceptsDischargeBedResponse({ ...request, epoch: 5 }, request, 7, 7)).toBe(false);
    expect(acceptsDischargeBedResponse({ ...request, patientId: 13 }, request, 7, 7)).toBe(false);
    expect(acceptsDischargeBedResponse(request, request, 7, 8)).toBe(false);
  });
});
