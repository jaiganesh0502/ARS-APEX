import { apiClient } from './client';
import { AdmissionStatus, PatientDetail, PatientListResponse } from '../types';

export interface PatientListParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: AdmissionStatus | '';
}

export const getPatients = async ({
  page = 1,
  pageSize = 20,
  search = '',
  status = '',
}: PatientListParams = {}): Promise<PatientListResponse> => {
  const response = await apiClient.get<PatientListResponse>('/patients', {
    params: {
      page,
      page_size: pageSize,
      ...(search.trim() ? { search: search.trim() } : {}),
      ...(status ? { status } : {}),
    },
  });
  return response.data;
};

export const getPatientById = async (patientId: number): Promise<PatientDetail> => {
  const response = await apiClient.get<PatientDetail>(`/patients/${patientId}`);
  return response.data;
};

export const createPatient = async (payload: {
  first_name: string;
  last_name: string;
  patient_code: string;
  date_of_birth: string;
  gender: string;
  blood_group?: string;
  phone?: string;
  emergency_contact?: string;
}): Promise<PatientDetail> => {
  const response = await apiClient.post<PatientDetail>('/patients', payload);
  return response.data;
};

export const patientsApi = {
  getPatients,
  getPatientById,
  createPatient,
};


