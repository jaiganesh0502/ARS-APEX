import { apiClient } from './client';
import type {
  WorkflowEvent,
  WorkflowDashboardCounts,
  WorkflowEventRetryResponse,
} from '../types';

export const workflowsApi = {
  listWorkflowEvents: async (params?: {
    delivery_status?: string;
    orchestration_status?: string;
    event_type?: string;
    entity_type?: string;
    skip?: number;
    limit?: number;
  }): Promise<WorkflowEvent[]> => {
    const response = await apiClient.get<WorkflowEvent[]>('/workflow-events', { params });
    return response.data;
  },

  getWorkflowDashboardCounts: async (): Promise<WorkflowDashboardCounts> => {
    const response = await apiClient.get<WorkflowDashboardCounts>('/workflow-events/counts');
    return response.data;
  },

  getWorkflowEventDetail: async (eventId: number): Promise<WorkflowEvent> => {
    const response = await apiClient.get<WorkflowEvent>(`/workflow-events/${eventId}`);
    return response.data;
  },

  retryWorkflowEvent: async (eventId: number): Promise<WorkflowEventRetryResponse> => {
    const response = await apiClient.post<WorkflowEventRetryResponse>(`/workflow-events/${eventId}/retry`);
    return response.data;
  },
};
