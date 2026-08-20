import type { ReactElement, ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { describe, expect, it } from 'vitest';

import { App } from '../../App';
import { BedActionPanel } from '../../pages/BedDetailPage';
import * as bedDetailPresentation from '../../pages/BedDetailPage';
import { BedsSummaryCards, BedsTable } from '../../pages/BedsPage';
import type { BedDetail, BedSummary } from '../../types';
import { BedTransitionModal } from './BedTransitionModal';
import * as transitionPresentation from './BedTransitionModal';

const summary = (overrides: Partial<BedSummary> = {}): BedSummary => ({
  id: 1,
  ward: 'North Ward',
  bed_number: 'N-01',
  status: 'occupied',
  current_patient_id: 10,
  patient_name: 'Ada Lovelace',
  patient_code: 'PAT-10',
  admission_id: 20,
  admission_status: 'discharging',
  primary_diagnosis: 'Pneumonia',
  release_eligible: true,
  updated_at: '2026-08-19T09:30:00Z',
  ...overrides,
});

const detail = (overrides: Partial<BedDetail> = {}): BedDetail => ({
  ...summary(),
  transition_history: [],
  ...overrides,
});

const collectPaths = (node: ReactNode): string[] => {
  if (Array.isArray(node)) return node.flatMap(collectPaths);
  if (!node || typeof node !== 'object' || !('props' in node)) return [];
  const element = node as ReactElement<{ path?: string; children?: ReactNode }>;
  return [element.props.path, ...collectPaths(element.props.children)].filter(
    (path): path is string => typeof path === 'string',
  );
};

describe('bed management presentation', () => {
  it('renders all six operational summary cards from real counts', () => {
    const beds = [
      summary(),
      summary({ id: 2, status: 'vacating' }),
      summary({ id: 3, status: 'cleaning' }),
      summary({ id: 4, status: 'available' }),
      summary({ id: 5, status: 'reserved' }),
    ];

    const html = renderToStaticMarkup(<BedsSummaryCards beds={beds} />);

    for (const label of ['Total Beds', 'Occupied', 'Vacating', 'Cleaning', 'Available', 'Reserved']) {
      expect(html).toContain(label);
    }
    expect(html).toContain('>5<');
  });

  it('does not present initial loading counts as authoritative zeroes', () => {
    const Summary = BedsSummaryCards as React.ComponentType<{ beds: BedSummary[]; state: 'loading' }>;
    const html = renderToStaticMarkup(<Summary beds={[]} state="loading" />);

    expect(html).toContain('aria-busy="true"');
    expect(html).toContain('Loading bed counts');
    expect(html).not.toContain('>0<');
  });

  it('marks summary counts unavailable after a load error', () => {
    const Summary = BedsSummaryCards as React.ComponentType<{ beds: BedSummary[]; state: 'error' }>;
    const html = renderToStaticMarkup(<Summary beds={[]} state="error" />);

    expect(html).toContain('Bed counts unavailable');
    expect(html).not.toContain('>0<');
  });

  it('renders the required table headers and safe available-bed copy', () => {
    const html = renderToStaticMarkup(
      <StaticRouter location="/beds">
        <BedsTable beds={[summary({ status: 'available', current_patient_id: null, patient_name: null, patient_code: null, admission_id: null, admission_status: null, primary_diagnosis: null, release_eligible: false })]} />
      </StaticRouter>,
    );

    for (const header of ['Ward', 'Bed', 'Status', 'Current Patient', 'Patient ID', 'Diagnosis', 'Last Updated', 'Action']) {
      expect(html).toContain(`>${header}<`);
    }
    expect(html).toContain('—');
    expect(html).toContain('Ready for assignment');
  });

  it('derives exactly one visible action or explanation for every bed state', () => {
    const cases: Array<[BedDetail, string]> = [
      [detail(), 'Start Bed Release'],
      [detail({ release_eligible: false }), 'Bed release cannot start because one or more release prerequisites are not satisfied.'],
      [detail({ status: 'vacating' }), 'Confirm Patient Departed'],
      [detail({ status: 'cleaning', current_patient_id: null, patient_name: null, patient_code: null }), 'Mark Cleaning Complete'],
      [detail({ status: 'available', current_patient_id: null, patient_name: null, patient_code: null }), 'Ready for assignment'],
      [detail({ status: 'reserved', current_patient_id: null, patient_name: null, patient_code: null }), 'This reserved bed has no available workflow action.'],
    ];

    for (const [bed, expected] of cases) {
      expect(renderToStaticMarkup(<BedActionPanel bed={bed} onAction={() => undefined} />)).toContain(expected);
    }
  });

  it.each(['cleaning', 'available'] as const)(
    'labels %s turnover data as historical admission context without a current-patient block',
    (status) => {
      const BedAdmissionContext = (bedDetailPresentation as unknown as {
        BedAdmissionContext?: React.ComponentType<{ bed: BedDetail }>;
      }).BedAdmissionContext ?? (() => null);
      const html = renderToStaticMarkup(<BedAdmissionContext bed={detail({
        status,
        current_patient_id: null,
        patient_name: null,
        patient_code: null,
        admission_id: 20,
        admission_status: 'discharged',
        primary_diagnosis: 'Resolved pneumonia',
      })} />);

      expect(html).toContain('Historical admission');
      expect(html).toContain('Admission ID');
      expect(html).toContain('20');
      expect(html).toContain('Resolved pneumonia');
      expect(html).toContain('discharged');
      expect(html).not.toContain('Current patient');
    },
  );

  it('registers the bed list and numeric detail route contracts', () => {
    expect(collectPaths(App({}))).toEqual(expect.arrayContaining(['/beds', '/beds/:bedId']));
  });

  it('rejects load and mutation responses after the route identity changes', () => {
    type Identity = { routeKey: string; bedId: number; epoch: number };
    const acceptsResponse = (bedDetailPresentation as unknown as {
      acceptsBedResponse?: (current: Identity, request: Identity, responseBedId: number) => boolean;
    }).acceptsBedResponse ?? (() => true);
    const oldRequest = { routeKey: '1', bedId: 1, epoch: 4 };

    expect(acceptsResponse({ routeKey: '2', bedId: 2, epoch: 4 }, oldRequest, 1)).toBe(false);
    expect(acceptsResponse({ routeKey: '1', bedId: 1, epoch: 5 }, oldRequest, 1)).toBe(false);
    expect(acceptsResponse(oldRequest, oldRequest, 2)).toBe(false);
    expect(acceptsResponse(oldRequest, oldRequest, 1)).toBe(true);
  });

  it('never selects a previous bed for presentation under a new route', () => {
    type TaggedBed = { routeKey: string; bedId: number; bed: BedDetail };
    const bedForRoute = (bedDetailPresentation as unknown as {
      bedForRoute?: (state: TaggedBed | undefined, route: { routeKey: string; bedId: number }) => BedDetail | undefined;
    }).bedForRoute ?? ((state: TaggedBed | undefined) => state?.bed);
    const previousBed = detail({ id: 1, bed_number: 'N-01' });

    expect(bedForRoute({ routeKey: '1', bedId: 1, bed: previousBed }, { routeKey: '2', bedId: 2 })).toBeUndefined();
  });
});

describe('bed transition confirmation dialog', () => {
  const cases = [
    ['start_release', 'Start bed release?', "The patient's discharge report has been approved. The bed will move from Occupied to Vacating.", 'Start Release'],
    ['patient_departed', 'Confirm patient departure?', 'The bed will move to Cleaning and will no longer be assigned to the patient.', 'Confirm Departure'],
    ['cleaning_complete', 'Confirm cleaning is complete?', 'The bed will become available for another patient.', 'Complete Cleaning'],
  ] as const;

  it.each(cases)('renders exact %s safety copy', (action, title, description, confirmLabel) => {
    const html = renderToStaticMarkup(<BedTransitionModal action={action} onCancel={() => undefined} onConfirm={() => undefined} />)
      .replace(/&#x27;/g, "'");

    expect(html).toContain(title);
    expect(html).toContain(description);
    expect(html).toContain('>Cancel<');
    expect(html).toContain(`>${confirmLabel}<`);
  });

  it('exposes labelled modal semantics and disables every dismissal while saving', () => {
    const html = renderToStaticMarkup(<BedTransitionModal action="start_release" saving onCancel={() => undefined} onConfirm={() => undefined} />);

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-labelledby="bed-transition-title"');
    expect(html).toContain('aria-describedby="bed-transition-description"');
    expect(html.match(/disabled=""/g)).toHaveLength(2);
  });

  it('chooses the first enabled action initially and the dialog when no action is enabled', () => {
    const dialogFocusTarget = (transitionPresentation as unknown as {
      dialogFocusTarget?: (enabledActionCount: number) => 'first-action' | 'dialog';
    }).dialogFocusTarget ?? (() => 'missing' as never);

    expect(dialogFocusTarget(2)).toBe('first-action');
    expect(dialogFocusTarget(0)).toBe('dialog');
  });

  it('restores focus to a stable fallback when the action opener unmounts', () => {
    const focusRestorationTarget = (transitionPresentation as unknown as {
      focusRestorationTarget?: (openerConnected: boolean, fallbackConnected: boolean) => 'opener' | 'fallback' | undefined;
    }).focusRestorationTarget ?? (() => undefined);

    expect(focusRestorationTarget(true, true)).toBe('opener');
    expect(focusRestorationTarget(false, true)).toBe('fallback');
    expect(focusRestorationTarget(false, false)).toBeUndefined();
  });

  it('allows Escape and backdrop dismissal only while the dialog is idle', () => {
    const canDismissBedTransition = (transitionPresentation as unknown as {
      canDismissBedTransition?: (saving: boolean) => boolean;
    }).canDismissBedTransition ?? (() => true);

    expect(canDismissBedTransition(false)).toBe(true);
    expect(canDismissBedTransition(true)).toBe(false);
  });
});
