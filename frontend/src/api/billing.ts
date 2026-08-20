import { apiClient } from './client';
import type { BillingClearance } from '../types';

export const billingApi = {
  getAdmissionBillingClearance: async (admissionId: number): Promise<BillingClearance | null> => {
    const response = await apiClient.get<BillingClearance | null>(`/admissions/${admissionId}/billing-clearance`);
    return response.data;
  },

  listBillingClearances: async (params?: {
    status?: string;
    deferred?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<BillingClearance[]> => {
    const response = await apiClient.get<BillingClearance[]>('/billing-clearances', { params });
    return response.data;
  },

  confirmBillingClearance: async (
    billingId: number,
    payload: { clearance_reference: string; notes?: string }
  ): Promise<BillingClearance> => {
    const response = await apiClient.post<BillingClearance>(`/billing-clearances/${billingId}/clear`, payload);
    return response.data;
  },
};
