import axios, { AxiosError } from 'axios';

declare module 'axios' {
  export interface AxiosRequestConfig {
    suppressErrorLog?: boolean;
  }

  export interface InternalAxiosRequestConfig {
    suppressErrorLog?: boolean;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

export const shouldLogApiError = (error: AxiosError): boolean => !error.config?.suppressErrorLog;

// Request interceptor for future JWT authentication header injection
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for consistent error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const data = error.response?.data as { error?: { message?: string }; detail?: string } | undefined;
    const message = data?.error?.message || data?.detail || error.message;
    if (shouldLogApiError(error)) console.error('API Error:', message);
    return Promise.reject(error);
  }
);
