import { apiClient } from './client';
import { ClinicalDecision, ClinicalDecisionRequest } from '../types';

export const CLINICAL_SPECIALTIES = [
  'Cardiology', 'Neurology', 'Orthopedics', 'General Surgery',
  'Critical Care', 'Pulmonology', 'Nephrology', 'Gastroenterology',
] as const;

export const createClinicalDecision = async (admissionId: number, request: ClinicalDecisionRequest): Promise<ClinicalDecision> => {
  const response = await apiClient.post<ClinicalDecision>(`/admissions/${admissionId}/clinical-decision`, request);
  return response.data;
};

export const getClinicalDecision = async (admissionId: number): Promise<ClinicalDecision> => {
  const response = await apiClient.get<ClinicalDecision>(`/admissions/${admissionId}/clinical-decision`, {
    suppressErrorLog: true,
  });
  return response.data;
};

export const updateClinicalDecision = async (decisionId: number, request: ClinicalDecisionRequest): Promise<ClinicalDecision> => {
  const response = await apiClient.put<ClinicalDecision>(`/clinical-decisions/${decisionId}`, request);
  return response.data;
};

export const confirmClinicalDecision = async (decisionId: number): Promise<ClinicalDecision> => {
  const response = await apiClient.post<ClinicalDecision>(`/clinical-decisions/${decisionId}/confirm`);
  return response.data;
};
