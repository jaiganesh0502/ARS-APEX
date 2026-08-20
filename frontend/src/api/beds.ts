import { apiClient } from './client';
import type { BedDetail, BedFilters, BedSummary } from '../types';

export const listBeds = async (filters: BedFilters = {}): Promise<BedSummary[]> => {
  const params = {
    ...(filters.status === undefined ? {} : { status: filters.status }),
    ...(filters.ward === undefined ? {} : { ward: filters.ward }),
    ...(filters.skip === undefined ? {} : { skip: filters.skip }),
    ...(filters.limit === undefined ? {} : { limit: filters.limit }),
  };
  const response = await apiClient.get<BedSummary[]>('/beds', { params });
  return response.data;
};

export const listAllBeds = async (
  filters: Omit<BedFilters, 'skip' | 'limit'> = {},
): Promise<BedSummary[]> => {
  const pageSize = 100;
  const beds: BedSummary[] = [];

  for (let skip = 0; ; skip += pageSize) {
    const page = await listBeds({ ...filters, skip, limit: pageSize });
    beds.push(...page);
    if (page.length < pageSize) return beds;
  }
};

export const getBed = async (id: number): Promise<BedDetail> => {
  const response = await apiClient.get<BedDetail>(`/beds/${id}`);
  return response.data;
};

export const startBedRelease = async (id: number): Promise<BedDetail> => {
  const response = await apiClient.post<BedDetail>(`/beds/${id}/start-release`);
  return response.data;
};

export const confirmPatientDeparted = async (id: number): Promise<BedDetail> => {
  const response = await apiClient.post<BedDetail>(`/beds/${id}/patient-departed`);
  return response.data;
};

export const completeBedCleaning = async (id: number): Promise<BedDetail> => {
  const response = await apiClient.post<BedDetail>(`/beds/${id}/cleaning-complete`);
  return response.data;
};
