import { apiClient } from './client';
import {
  AmbulanceDashboardCounts,
  AmbulanceDispatch,
  AmbulanceStatus,
} from '../types';

export interface AmbulanceListParams {
  status?: string;
  emergency?: boolean;
  skip?: number;
  limit?: number;
}

export const ambulanceApi = {
  /**
   * List all ambulance dispatches with optional status and priority filters.
   * GET /api/ambulance-dispatches
   */
  listDispatches: async (params?: AmbulanceListParams): Promise<AmbulanceDispatch[]> => {
    const response = await apiClient.get<AmbulanceDispatch[]>('/api/ambulance-dispatches', {
      params,
    });
    return response.data;
  },

  /**
   * Operational aggregate counts for ambulance fleet dashboard.
   * GET /api/ambulance-dispatches/counts
   */
  getDashboardCounts: async (): Promise<AmbulanceDashboardCounts> => {
    const response = await apiClient.get<AmbulanceDashboardCounts>('/api/ambulance-dispatches/counts');
    return response.data;
  },

  /**
   * Retrieve full tracking telemetry and patient context for an ambulance dispatch.
   * GET /api/ambulance-dispatches/{dispatch_id}
   */
  getDispatchDetail: async (dispatchId: number): Promise<AmbulanceDispatch> => {
    const response = await apiClient.get<AmbulanceDispatch>(`/api/ambulance-dispatches/${dispatchId}`);
    return response.data;
  },

  /**
   * Advance ambulance dispatch status through the validated state machine.
   * POST /api/ambulance-dispatches/{dispatch_id}/status
   */
  updateStatus: async (dispatchId: number, status: AmbulanceStatus): Promise<AmbulanceDispatch> => {
    const response = await apiClient.post<AmbulanceDispatch>(
      `/api/ambulance-dispatches/${dispatchId}/status`,
      { status }
    );
    return response.data;
  },

  /**
   * Cancel an ambulance dispatch before patient boarding.
   * POST /api/ambulance-dispatches/{dispatch_id}/cancel
   */
  cancelDispatch: async (dispatchId: number, reason: string): Promise<AmbulanceDispatch> => {
    const response = await apiClient.post<AmbulanceDispatch>(
      `/api/ambulance-dispatches/${dispatchId}/cancel`,
      { reason }
    );
    return response.data;
  },
};
