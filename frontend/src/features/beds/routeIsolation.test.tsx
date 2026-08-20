import React, { type ReactElement } from 'react';
import { describe, expect, it } from 'vitest';

import * as dischargePresentation from '../../pages/DischargePage';
import * as patientPresentation from '../../pages/PatientDetailPage';


type RouteBoundary = (props: { routeKey: string; patientId: number }) => ReactElement;

const missingBoundary: RouteBoundary = () => React.createElement('div');

describe('patient-keyed workflow boundaries', () => {
  it('synchronously remounts patient details before a new route can reuse prior state', () => {
    const boundary = (patientPresentation as unknown as {
      PatientDetailRouteBoundary?: RouteBoundary;
    }).PatientDetailRouteBoundary ?? missingBoundary;

    const previous = boundary({ routeKey: '12', patientId: 12 });
    const next = boundary({ routeKey: '13', patientId: 13 });

    expect(previous.key).toBe('patient:12');
    expect(next.key).toBe('patient:13');
    expect(next.key).not.toBe(previous.key);
  });

  it('synchronously remounts discharge workflow before a new route can reuse prior state', () => {
    const boundary = (dischargePresentation as unknown as {
      DischargeRouteBoundary?: RouteBoundary;
    }).DischargeRouteBoundary ?? missingBoundary;

    const previous = boundary({ routeKey: '12', patientId: 12 });
    const next = boundary({ routeKey: '13', patientId: 13 });

    expect(previous.key).toBe('discharge:12');
    expect(next.key).toBe('discharge:13');
    expect(next.key).not.toBe(previous.key);
  });
});
