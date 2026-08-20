import { apiClient } from './client';

export interface UserProfile {
  id: number;
  name: string;
  email: string;
  role: 'doctor' | 'medical_superintendent' | 'receptionist' | 'patient' | 'ward_admin' | 'receiving_doctor' | 'receiving_admin';
  is_active: boolean;
  patient_id?: number | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface PatientPortalProfileResponse {
  patient: {
    id: number;
    patient_code: string;
    first_name: string;
    last_name: string;
    date_of_birth?: string | null;
    gender: string;
    blood_group?: string | null;
    phone?: string | null;
  };
  admission?: {
    id?: number | null;
    status?: string | null;
    primary_diagnosis?: string | null;
    admission_date?: string | null;
    attending_doctor?: string | null;
    discharge_ready?: boolean;
  } | null;
  bed?: {
    ward?: string;
    bed_number?: string;
  } | null;
  invoice?: {
    id: number;
    invoice_number: string;
    subtotal: number;
    discount_amount: number;
    tax_amount: number;
    total_amount: number;
    amount_paid: number;
    balance_amount: number;
    payment_status: string;
    qr_code_uri?: string | null;
  } | null;
  discharge_package?: {
    id?: number | null;
    status?: string | null;
    authorized_at?: string | null;
    has_pdf: boolean;
    download_url?: string | null;
    patient_summary?: {
      summary: string;
      medications: Array<{
        name: string;
        dosage: string;
        frequency: string;
        purpose?: string;
      }>;
      activity_restrictions: string[];
      warning_signs: string[];
      follow_up_instructions: string;
      emergency_contact?: string;
    } | null;
  } | null;
}

export const authApi = {
  login: async (credentials: { email: string; password: string }): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/auth/login', credentials, {
      suppressErrorLog: true,
    });
    return response.data;
  },

  getMe: async (): Promise<UserProfile> => {
    const response = await apiClient.get<UserProfile>('/auth/me', {
      suppressErrorLog: true,
    });
    return response.data;
  },

  getPatientProfile: async (): Promise<PatientPortalProfileResponse> => {
    const response = await apiClient.get<PatientPortalProfileResponse>('/patient-portal/profile');
    return response.data;
  },
};
