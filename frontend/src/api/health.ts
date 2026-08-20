import { apiClient } from './client';
import { HealthStatusResponse } from '../types';

export const checkSystemHealth = async (): Promise<HealthStatusResponse> => {
  const response = await apiClient.get<HealthStatusResponse>('/health');
  return response.data;
};
