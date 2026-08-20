import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import {
  acceptsPatientOperationalResponse,
  bedCandidateForPatient,
  operationalBedForPatient,
  PatientBedInformation,
  PatientOperationalStatus,
} from '../../pages/PatientDetailPage';
import { DashboardBedMetric, DashboardSafetyNotice } from '../../pages/DashboardPage';
import type { BedSummary, PatientDetail } from '../../types';

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

describe('patient bed workflow integration', () => {
  it('shows approved discharge and pending release for an eligible occupied bed', () => {
    const html = renderToStaticMarkup(
      <PatientOperationalStatus bed={bed()} state="ready" admissionStatus="discharging" />,
    );

    expect(html).toContain('Discharge Report Approved');
    expect(html).toContain('Bed Release Pending');
    expect(html).toContain('Approval alone does not discharge the patient or release the bed');
  });

  it('shows vacating as operational progress without claiming release is pending', () => {
    const html = renderToStaticMarkup(
      <PatientOperationalStatus
        bed={bed({ status: 'vacating', release_eligible: false })}
        state="ready"
        admissionStatus="discharging"
      />,
    );

    expect(html).toContain('Bed Status: Vacating');
    expect(html).not.toContain('Bed Release Pending');
  });

  it('shows the discharged admission and cleaning bed after departure', () => {
    const html = renderToStaticMarkup(
      <PatientOperationalStatus
        bed={bed({
          status: 'cleaning',
          current_patient_id: null,
          patient_name: null,
          patient_code: null,
          admission_status: 'discharged',
          release_eligible: false,
        })}
        state="ready"
        admissionStatus="discharged"
      />,
    );

    expect(html).toContain('Admission Status: Discharged');
    expect(html).toContain('Bed Status: Cleaning');
  });

  it('rejects old patient, admission, and epoch responses', () => {
    const request = { patientId: 12, admissionId: 20, epoch: 4 };

    expect(acceptsPatientOperationalResponse(request, request)).toBe(true);
    expect(acceptsPatientOperationalResponse({ ...request, patientId: 13 }, request)).toBe(false);
    expect(acceptsPatientOperationalResponse({ ...request, admissionId: 21 }, request)).toBe(false);
    expect(acceptsPatientOperationalResponse({ ...request, epoch: 5 }, request)).toBe(false);
  });

  it('does not associate a discharged patient with a bed reassigned to someone else', () => {
    const reassignedBed = bed({ current_patient_id: 13, admission_id: 21, release_eligible: false });
    const patient: Pick<PatientDetail, 'id' | 'admission' | 'bed'> = {
      id: 12,
      admission: {
        id: 20,
        admission_date: '2026-08-18T09:30:00Z',
        primary_diagnosis: 'Pneumonia',
        status: 'discharged',
        attending_doctor_id: 4,
        attending_doctor: 'Dr Rao',
      },
      bed: { ward: 'North', bed_number: 'N-07', status: 'occupied' },
    };

    expect(operationalBedForPatient([reassignedBed], patient)).toBeUndefined();
  });

  it('finds a physical bed on a later complete-list page but requires detail admission identity', () => {
    const patient: Pick<PatientDetail, 'id' | 'admission' | 'bed'> = {
      id: 12,
      admission: {
        id: 20,
        admission_date: '2026-08-18T09:30:00Z',
        primary_diagnosis: 'Pneumonia',
        status: 'discharged',
        attending_doctor_id: 4,
        attending_doctor: 'Dr Rao',
      },
      bed: { ward: 'Overflow', bed_number: 'O-101', status: 'cleaning' },
    };
    const firstPage = Array.from({ length: 100 }, (_, index) => bed({
      id: index + 1,
      ward: 'North',
      bed_number: `N-${index + 1}`,
      current_patient_id: index + 100,
      admission_id: index + 200,
    }));
    const physicalBed = bed({
      id: 101,
      ward: 'Overflow',
      bed_number: 'O-101',
      status: 'cleaning',
      current_patient_id: null,
      admission_id: null,
      admission_status: null,
    });
    const matchingDetail = { ...physicalBed, admission_id: 20, admission_status: 'discharged' as const, transition_history: [] };
    const reusedDetail = { ...matchingDetail, admission_id: 21 };

    expect(bedCandidateForPatient([...firstPage, physicalBed], patient)).toEqual(physicalBed);
    expect(operationalBedForPatient([physicalBed], patient)).toBeUndefined();
    expect(operationalBedForPatient([matchingDetail], patient)).toEqual(matchingDetail);
    expect(operationalBedForPatient([reusedDetail], patient)).toBeUndefined();
  });

  it('never presents historical patient bed status as current operational status', () => {
    const html = renderToStaticMarkup(
      <PatientBedInformation
        historicalBed={{ ward: 'North', bed_number: 'N-07', status: 'occupied' }}
        state="ready"
      />,
    );

    expect(html).toContain('Historical bed');
    expect(html).toContain('North / N-07');
    expect(html).toContain('Current operational status unavailable');
    expect(html).not.toContain('OCCUPIED');
  });
});

describe('dashboard bed integration', () => {
  it('presents real occupancy, available, and cleaning counts', () => {
    const beds = [
      bed(),
      bed({ id: 2, status: 'vacating' }),
      bed({ id: 3, status: 'cleaning' }),
      bed({ id: 4, status: 'available' }),
      bed({ id: 5, status: 'reserved' }),
    ];
    const html = renderToStaticMarkup(<DashboardBedMetric beds={beds} state="ready" />);

    expect(html).toContain('Bed Occupancy');
    expect(html).toContain('40%');
    expect(html).toContain('1 Available, 1 Cleaning');
  });

  it('does not present fake zeroes while loading or unavailable', () => {
    const loading = renderToStaticMarkup(<DashboardBedMetric beds={[]} state="loading" />);
    const unavailable = renderToStaticMarkup(<DashboardBedMetric beds={[]} state="error" />);

    expect(loading).toContain('aria-busy="true"');
    expect(loading).toContain('Loading bed data');
    expect(loading).not.toContain('>0<');
    expect(unavailable).toContain('Bed data unavailable');
    expect(unavailable).not.toContain('>0<');
  });

  it('describes the manual workflow without automatic or n8n bed-release claims', () => {
    const html = renderToStaticMarkup(<DashboardSafetyNotice />).toLowerCase();

    expect(html).toContain('staff manually start bed release');
    expect(html).not.toContain('automatic bed release');
    expect(html).not.toContain('n8n');
  });
});
