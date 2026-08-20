import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { BedDetail, BedSummary } from '../../types';
import { apiClient } from '../../api/client';
import {
  completeBedCleaning,
  confirmPatientDeparted,
  getBed,
  listAllBeds,
  listBeds,
  startBedRelease,
} from '../../api/beds';
import { bedAction, filterBeds, summarizeBeds } from './bedState';
import * as bedsPagePresentation from '../../pages/BedsPage';

vi.mock('../../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const bed = (overrides: Partial<BedSummary> = {}): BedSummary => ({
  id: 1,
  ward: 'North',
  bed_number: 'N-01',
  status: 'occupied',
  current_patient_id: 10,
  patient_name: 'Ada Lovelace',
  patient_code: 'PAT-10',
  admission_id: 20,
  admission_status: 'discharging',
  primary_diagnosis: 'Pneumonia',
  release_eligible: false,
  updated_at: '2026-08-19T00:00:00Z',
  ...overrides,
});

const detail = (overrides: Partial<BedDetail> = {}): BedDetail => ({
  ...bed(),
  transition_history: [{
    event_type: 'bed_release_started',
    previous_status: 'occupied',
    new_status: 'vacating',
    created_at: '2026-08-19T00:01:00Z',
  }],
  ...overrides,
});

describe('bed state helpers', () => {
  it('counts every supported bed status', () => {
    const beds = [
      bed({ status: 'occupied' }),
      bed({ id: 2, status: 'vacating' }),
      bed({ id: 3, status: 'cleaning' }),
      bed({ id: 4, status: 'available' }),
      bed({ id: 5, status: 'reserved' }),
    ];

    expect(summarizeBeds(beds)).toEqual({
      total: 5,
      occupied: 1,
      vacating: 1,
      cleaning: 1,
      available: 1,
      reserved: 1,
    });
  });

  it('derives only the permitted action for each bed state boundary', () => {
    expect(bedAction(bed({ release_eligible: true }))).toBe('start_release');
    expect(bedAction(bed({ release_eligible: false }))).toBeUndefined();
    expect(bedAction(bed({ status: 'vacating' }))).toBe('patient_departed');
    expect(bedAction(bed({ status: 'cleaning' }))).toBe('cleaning_complete');
    expect(bedAction(bed({ status: 'available' }))).toBeUndefined();
    expect(bedAction(bed({ status: 'reserved' }))).toBeUndefined();
  });

  it('combines exact ward and status filters with case-insensitive patient search', () => {
    const beds = [
      bed({ ward: 'North', status: 'occupied', patient_name: 'Ada Lovelace' }),
      bed({ id: 2, ward: 'South', status: 'occupied', patient_name: 'Ada Byron' }),
      bed({ id: 3, ward: 'North', status: 'available', patient_name: null }),
    ];

    expect(filterBeds(beds, { ward: 'North', status: 'occupied', search: 'LOVELACE' }))
      .toEqual([beds[0]]);
  });

  it('searches bed numbers and patient codes while preserving empty searches and null patient fields', () => {
    const beds = [
      bed({ bed_number: 'N-07', patient_name: null, patient_code: null }),
      bed({ id: 2, bed_number: 'S-02', patient_code: 'PAT-204' }),
    ];

    expect(filterBeds(beds, { search: 'n-07' })).toEqual([beds[0]]);
    expect(filterBeds(beds, { search: 'pat-204' })).toEqual([beds[1]]);
    expect(filterBeds(beds, { search: '' })).toEqual(beds);
  });
});

describe('bed API', () => {
  const get = vi.mocked(apiClient.get);
  const post = vi.mocked(apiClient.post);

  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it('omits unset list query parameters and returns response data', async () => {
    get.mockResolvedValueOnce({ data: [bed()] });

    await expect(listBeds()).resolves.toEqual([bed()]);
    expect(get).toHaveBeenCalledWith('/beds', { params: {} });
  });

  it('includes supplied list query parameters but keeps frontend search local', async () => {
    get.mockResolvedValueOnce({ data: [] });

    await listBeds({ ward: 'North', status: 'occupied', skip: 0, limit: 25, search: 'Ada' });

    expect(get).toHaveBeenCalledWith('/beds', {
      params: { ward: 'North', status: 'occupied', skip: 0, limit: 25 },
    });
  });

  it('paginates an exactly full first page, includes a later-page patient bed, and stops on the short page', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => bed({
      id: index + 1,
      bed_number: `N-${String(index + 1).padStart(3, '0')}`,
      current_patient_id: index + 1000,
      admission_id: index + 2000,
    }));
    const laterPatientBed = bed({ id: 101, current_patient_id: 12, admission_id: 20 });
    get.mockResolvedValueOnce({ data: firstPage }).mockResolvedValueOnce({ data: [laterPatientBed] });

    await expect(listAllBeds()).resolves.toEqual([...firstPage, laterPatientBed]);
    expect(get).toHaveBeenNthCalledWith(1, '/beds', { params: { skip: 0, limit: 100 } });
    expect(get).toHaveBeenNthCalledWith(2, '/beds', { params: { skip: 100, limit: 100 } });
    expect(get).toHaveBeenCalledTimes(2);
  });

  it('wires the actual Bed Management loader to every paginated bed', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => bed({
      id: index + 1,
      bed_number: `N-${String(index + 1).padStart(3, '0')}`,
    }));
    const laterBed = bed({ id: 101, ward: 'Overflow', bed_number: 'O-101' });
    get.mockResolvedValueOnce({ data: firstPage }).mockResolvedValueOnce({ data: [laterBed] });
    const loadBedsPageData = (bedsPagePresentation as unknown as {
      loadBedsPageData?: () => Promise<BedSummary[]>;
    }).loadBedsPageData ?? (() => listBeds());

    const loadedBeds = await loadBedsPageData();

    expect(loadedBeds).toHaveLength(101);
    expect(loadedBeds[100]).toEqual(laterBed);
    expect(get).toHaveBeenNthCalledWith(2, '/beds', { params: { skip: 100, limit: 100 } });
  });

  it('terminates pagination after an empty first page', async () => {
    get.mockResolvedValueOnce({ data: [] });

    await expect(listAllBeds({ ward: 'North' })).resolves.toEqual([]);
    expect(get).toHaveBeenCalledWith('/beds', { params: { ward: 'North', skip: 0, limit: 100 } });
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('uses the exact detail and workflow action paths', async () => {
    const result = detail({
      current_patient_id: null,
      patient_name: null,
      patient_code: null,
    });
    get.mockResolvedValueOnce({ data: result });
    post.mockResolvedValue({ data: result });

    await expect(getBed(7)).resolves.toEqual(result);
    const mutationResults: BedDetail[] = [
      await startBedRelease(7),
      await confirmPatientDeparted(7),
      await completeBedCleaning(7),
    ];

    expect(get).toHaveBeenCalledWith('/beds/7');
    expect(post).toHaveBeenNthCalledWith(1, '/beds/7/start-release');
    expect(post).toHaveBeenNthCalledWith(2, '/beds/7/patient-departed');
    expect(post).toHaveBeenNthCalledWith(3, '/beds/7/cleaning-complete');
    expect(mutationResults).toEqual([result, result, result]);
    for (const mutationResult of mutationResults) {
      expect(mutationResult).toMatchObject({
        current_patient_id: null,
        patient_name: null,
        patient_code: null,
        transition_history: [{
          event_type: 'bed_release_started',
          previous_status: 'occupied',
          new_status: 'vacating',
        }],
      });
    }
  });
});
