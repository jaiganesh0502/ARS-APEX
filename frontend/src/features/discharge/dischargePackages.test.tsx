import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { describe, expect, it } from 'vitest';

import { FinalDischargePackageCard } from '../../pages/DischargePage';
import type { BillingClearance, DischargeReport } from '../../types';

const makeReport = (overrides: Partial<DischargeReport> = {}): DischargeReport => ({
  id: 1,
  admission_id: 10,
  patient_id: 20,
  status: 'approved',
  generated_content: 'Approved report',
  effective_content: 'Approved report',
  generation_provider: 'replicate',
  generation_model: 'openai/gpt-5.6-luna',
  created_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  ...overrides,
});

const makeBilling = (overrides: Partial<BillingClearance> = {}): BillingClearance => ({
  id: 5,
  admission_id: 10,
  patient_id: 20,
  status: 'pending',
  total_amount: 10000,
  amount_paid: 0,
  outstanding_amount: 10000,
  deferred: false,
  created_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  ...overrides,
});

describe('FinalDischargePackageCard Presentation', () => {
  it('does not render if report is not approved', () => {
    const markup = renderToStaticMarkup(
      <StaticRouter location="/patients/20/discharge">
        <FinalDischargePackageCard
          admissionId={10}
          patientId={20}
          billing={makeBilling()}
          report={makeReport({ status: 'generated' })}
        />
      </StaticRouter>
    );
    expect(markup).toBe('');
  });

  it('renders billing clearance warning when billing is pending', () => {
    const markup = renderToStaticMarkup(
      <StaticRouter location="/patients/20/discharge">
        <FinalDischargePackageCard
          admissionId={10}
          patientId={20}
          billing={makeBilling({ status: 'pending' })}
          report={makeReport({ status: 'approved' })}
        />
      </StaticRouter>
    );

    expect(markup).toContain('Awaiting Billing Clearance');
    expect(markup).toContain('Billing Clearance Required');
    expect(markup).toContain('final discharge package generation is locked');
  });

  it('renders Ready to Generate when billing is cleared', () => {
    const markup = renderToStaticMarkup(
      <StaticRouter location="/patients/20/discharge">
        <FinalDischargePackageCard
          admissionId={10}
          patientId={20}
          billing={makeBilling({ status: 'cleared', amount_paid: 10000, outstanding_amount: 0 })}
          report={makeReport({ status: 'approved' })}
        />
      </StaticRouter>
    );

    expect(markup).toContain('Ready to Generate');
    expect(markup).toContain('Generate Final Package');
  });
});
