import { apiClient } from './client';
import { DischargeReport } from '../types';

export const getAdmissionDischargeReport = async (admissionId: number): Promise<DischargeReport> => {
  const response = await apiClient.get<DischargeReport>(`/discharge/admissions/${admissionId}/report`, {
    suppressErrorLog: true,
  });
  return response.data;
};

export const generateDischargeReport = async (admissionId: number): Promise<DischargeReport> => {
  const response = await apiClient.post<DischargeReport>(`/discharge/generate/${admissionId}`);
  return response.data;
};

export const editDischargeReport = async (reportId: number, editedContent: string): Promise<DischargeReport> => {
  const response = await apiClient.put<DischargeReport>(`/discharge/reports/${reportId}/edit`, {
    edited_content: editedContent,
  });
  return response.data;
};

export const approveDischargeReport = async (reportId: number, clinicalNotes?: string): Promise<DischargeReport> => {
  const response = await apiClient.post<DischargeReport>(`/discharge/reports/${reportId}/approve`, {
    acknowledged: true,
    ...(clinicalNotes === undefined ? {} : { clinical_notes: clinicalNotes }),
  });
  return response.data;
};
