import { apiClient } from './client';
import type { BillingClearance, ChargeMasterItem, Invoice } from '../types';

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

  // Invoice & Payments API
  getAdmissionInvoice: async (admissionId: number): Promise<Invoice> => {
    const response = await apiClient.get<Invoice>(`/admissions/${admissionId}/invoice`);
    return response.data;
  },

  getInvoiceById: async (invoiceId: number): Promise<Invoice> => {
    const response = await apiClient.get<Invoice>(`/invoices/${invoiceId}`);
    return response.data;
  },

  listInvoices: async (paymentStatus?: string): Promise<Invoice[]> => {
    const response = await apiClient.get<Invoice[]>('/invoices', {
      params: paymentStatus ? { payment_status: paymentStatus } : undefined,
    });
    return response.data;
  },

  recordManualPayment: async (
    invoiceId: number,
    payload: { amount: number; payment_method: string; reference: string; notes?: string }
  ): Promise<any> => {
    const response = await apiClient.post(`/invoices/${invoiceId}/payments/manual`, payload);
    return response.data;
  },

  simulateOnlinePayment: async (payload: {
    invoice_number: string;
    amount?: number;
    transaction_reference?: string;
  }): Promise<any> => {
    const response = await apiClient.post('/payments/simulate-online', payload);
    return response.data;
  },

  getChargeMaster: async (category?: string): Promise<ChargeMasterItem[]> => {
    const response = await apiClient.get<ChargeMasterItem[]>('/charge-master', {
      params: category ? { category } : undefined,
    });
    return response.data;
  },
};
