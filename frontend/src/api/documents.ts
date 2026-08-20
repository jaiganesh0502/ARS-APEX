import { apiClient } from './client';
import { ClinicalDocument } from '../types';

export const documentsApi = {
  uploadDocument: async (
    admissionId: number,
    file: File,
    documentType: string = 'doctor_handwritten_notes'
  ): Promise<ClinicalDocument> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    const response = await apiClient.post<ClinicalDocument>(
      `/admissions/${admissionId}/documents`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  listDocuments: async (admissionId: number): Promise<ClinicalDocument[]> => {
    const response = await apiClient.get<ClinicalDocument[]>(
      `/admissions/${admissionId}/documents`
    );
    return response.data;
  },

  retryOcr: async (documentId: number): Promise<ClinicalDocument> => {
    const response = await apiClient.post<ClinicalDocument>(
      `/documents/${documentId}/retry-ocr`
    );
    return response.data;
  },

  getDocumentDownloadUrl: (documentId: number): string => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    return `${baseUrl}/documents/${documentId}/file`;
  },
};
