import { apiClient } from './client';
import type { DischargePackage } from '../types';

export const dischargePackagesApi = {
  finalizeDischargePackage: async (
    admissionId: number,
    payload?: { notes?: string }
  ): Promise<DischargePackage> => {
    const response = await apiClient.post<DischargePackage>(
      `/admissions/${admissionId}/final-discharge-package`,
      payload || {}
    );
    return response.data;
  },

  getAdmissionDischargePackage: async (
    admissionId: number
  ): Promise<DischargePackage | null> => {
    const response = await apiClient.get<DischargePackage | null>(
      `/admissions/${admissionId}/discharge-package`
    );
    return response.data;
  },

  getPackageById: async (packageId: number): Promise<DischargePackage> => {
    const response = await apiClient.get<DischargePackage>(
      `/discharge-packages/${packageId}`
    );
    return response.data;
  },

  retryGeneratePdf: async (packageId: number): Promise<DischargePackage> => {
    const response = await apiClient.post<DischargePackage>(
      `/discharge-packages/${packageId}/generate-pdf`
    );
    return response.data;
  },

  getPdfDownloadUrl: (packageId: number): string => {
    const base = apiClient.defaults.baseURL || '/api';
    return `${base}/discharge-packages/${packageId}/pdf`;
  },
};
