import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import {
  DecisionHandoffNotice,
  getDecisionConfirmationNavigation,
} from './decisionHandoff';

describe('clinical decision handoff', () => {
  it('routes a confirmed discharge to its honest Feature 3 placeholder', () => {
    expect(getDecisionConfirmationNavigation('discharge', 12)).toEqual({
      pathname: '/patients/12/discharge',
      state: { confirmationMessage: 'Discharge decision confirmed.' },
    });
  });

  it('routes a confirmed transfer to its matching-workflow placeholder', () => {
    expect(getDecisionConfirmationNavigation('transfer', 12)).toEqual({
      pathname: '/transfers/new',
      search: '?patientId=12',
      state: { confirmationMessage: 'Transfer decision confirmed.' },
    });
  });

  it('states that downstream discharge automation has not started', () => {
    const html = renderToStaticMarkup(
      <DecisionHandoffNotice
        message="Discharge decision confirmed."
        nextStep="AI-assisted discharge report generation and doctor review"
      />,
    );

    expect(html).toContain('Discharge decision confirmed.');
    expect(html).toContain('has not started automatically');
    expect(html).toContain('AI-assisted discharge report generation and doctor review');
  });
});
