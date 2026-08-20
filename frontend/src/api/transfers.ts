import { apiClient } from './client';
import {
  AmbulanceDispatch,
  HospitalMatch,
  Transfer,
  TransferDetail,
  TransferPacket,
  TransferSummary,
} from '../types';

export interface TransferFilterParams {
  status?: string;
  emergency?: boolean;
  patient_id?: number;
  admission_id?: number;
  skip?: number;
  limit?: number;
}

export interface IncomingTransferParams {
  hospital_id?: number;
  status?: string;
  emergency?: boolean;
  specialty?: string;
  skip?: number;
  limit?: number;
}

export const transferApi = {
  /**
   * Initialize or retrieve an active transfer case for an admission.
   * POST /api/admissions/{admission_id}/transfer
   */
  createTransferForAdmission: async (admissionId: number): Promise<Transfer> => {
    const response = await apiClient.post<Transfer>(`/api/admissions/${admissionId}/transfer`);
    return response.data;
  },

  /**
   * Get full details of a specific transfer case.
   * GET /api/transfers/{transfer_id}
   */
  getTransfer: async (transferId: number): Promise<TransferDetail> => {
    const response = await apiClient.get<TransferDetail>(`/api/transfers/${transferId}`);
    return response.data;
  },

  /**
   * List all transfer summaries with optional filters.
   * GET /api/transfers
   */
  getTransfers: async (params?: TransferFilterParams): Promise<TransferSummary[]> => {
    const response = await apiClient.get<TransferSummary[]>('/api/transfers', { params });
    return response.data;
  },

  /**
   * Retrieve ranked hospital recommendations for a transfer case.
   * GET /api/transfers/{transfer_id}/matches
   */
  getHospitalMatches: async (transferId: number): Promise<HospitalMatch[]> => {
    const response = await apiClient.get<HospitalMatch[]>(`/api/transfers/${transferId}/matches`);
    return response.data;
  },

  /**
   * Select a partner receiving hospital for the transfer case.
   * POST /api/transfers/{transfer_id}/select-hospital
   */
  selectReceivingHospital: async (transferId: number, hospitalId: number): Promise<Transfer> => {
    const response = await apiClient.post<Transfer>(`/api/transfers/${transferId}/select-hospital`, {
      hospital_id: hospitalId,
    });
    return response.data;
  },

  /**
   * Assemble and persist a structured clinical transfer packet for the selected receiving facility.
   * POST /api/transfers/{transfer_id}/packet
   */
  prepareTransferPacket: async (transferId: number): Promise<TransferPacket> => {
    const response = await apiClient.post<TransferPacket>(`/api/transfers/${transferId}/packet`);
    return response.data;
  },

  /**
   * Retrieve the structured transfer packet for the transfer case.
   * GET /api/transfers/{transfer_id}/packet
   */
  getTransferPacket: async (transferId: number, markViewed: boolean = false): Promise<TransferPacket> => {
    const response = await apiClient.get<TransferPacket>(`/api/transfers/${transferId}/packet`, {
      params: { mark_viewed: markViewed },
    });
    return response.data;
  },

  /**
   * Simulate secure delivery into the receiving hospital's application queue.
   * POST /api/transfers/{transfer_id}/packet/send
   */
  sendTransferPacket: async (transferId: number): Promise<TransferPacket> => {
    const response = await apiClient.post<TransferPacket>(`/api/transfers/${transferId}/packet/send`);
    return response.data;
  },

  /**
   * Receiving hospital accepts the transfer request, reserves bed slot transactionally.
   * POST /api/transfers/{transfer_id}/accept
   */
  acceptTransfer: async (transferId: number, notes?: string): Promise<Transfer> => {
    const response = await apiClient.post<Transfer>(`/api/transfers/${transferId}/accept`, {
      notes: notes || undefined,
    });
    return response.data;
  },

  /**
   * Receiving hospital rejects the transfer request with mandatory justification.
   * POST /api/transfers/{transfer_id}/reject
   */
  rejectTransfer: async (transferId: number, reason: string): Promise<Transfer> => {
    const response = await apiClient.post<Transfer>(`/api/transfers/${transferId}/reject`, {
      reason,
    });
    return response.data;
  },

  /**
   * Re-open a rejected transfer case for sending-physician hospital re-matching.
   * POST /api/transfers/{transfer_id}/rematch
   */
  rematchTransfer: async (transferId: number): Promise<Transfer> => {
    const response = await apiClient.post<Transfer>(`/api/transfers/${transferId}/rematch`);
    return response.data;
  },

  /**
   * Receiving hospital triage queue.
   * GET /api/receiving/transfers
   */
  getIncomingTransfers: async (params?: IncomingTransferParams): Promise<TransferSummary[]> => {
    const response = await apiClient.get<TransferSummary[]>('/api/receiving/transfers', { params });
    return response.data;
  },

  /**
   * Receiving hospital transfer detail (marks packet as viewed).
   * GET /api/receiving/transfers/{transfer_id}
   */
  getIncomingTransferDetail: async (transferId: number): Promise<TransferDetail> => {
    const response = await apiClient.get<TransferDetail>(`/api/receiving/transfers/${transferId}`);
    return response.data;
  },

  /**
   * Dispatch an ambulance for an accepted transfer case.
   * POST /api/transfers/{transfer_id}/ambulance/dispatch
   */
  dispatchAmbulance: async (transferId: number): Promise<AmbulanceDispatch> => {
    const response = await apiClient.post<AmbulanceDispatch>(`/api/transfers/${transferId}/ambulance/dispatch`);
    return response.data;
  },

  /**
   * Retrieve active ambulance dispatch tracking data for a transfer case.
   * GET /api/transfers/{transfer_id}/ambulance
   */
  getTransferAmbulance: async (transferId: number): Promise<AmbulanceDispatch | null> => {
    const response = await apiClient.get<AmbulanceDispatch | null>(`/api/transfers/${transferId}/ambulance`);
    return response.data;
  },
};
