import { apiClient } from './client';
import type { Notification, NotificationListResponse } from '../types';

export const notificationsApi = {
  listNotifications: async (params?: {
    recipient_reference?: string;
    recipient_type?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }): Promise<NotificationListResponse> => {
    const response = await apiClient.get<NotificationListResponse>('/notifications', { params });
    return response.data;
  },

  markAsRead: async (notificationId: number): Promise<Notification> => {
    const response = await apiClient.post<Notification>(`/notifications/${notificationId}/read`);
    return response.data;
  },
};
