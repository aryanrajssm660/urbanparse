/**
 * API client for the UrbanDash backend.
 * 
 * Uses the Vite proxy (/api → localhost:8000) in development.
 * All errors are caught and rethrown with user-friendly messages.
 */

import type { Address, AddressListResponse, AddressUpdate, Stats } from '../types/address';

const API_BASE = '/api';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${url}`, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      let message = `Request failed (${response.status})`;
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join(', ');
      } else if (body.message && typeof body.message === 'string') {
        message = body.message;
      }
      throw new ApiError(message, response.status);
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Network error — is the backend running?', 0);
  }
}

// -------------------------------------------------------------------
// API Functions
// -------------------------------------------------------------------

export async function createAddress(rawAddress: string): Promise<Address> {
  return request<Address>('/addresses', {
    method: 'POST',
    body: JSON.stringify({ raw_address: rawAddress }),
  });
}

export async function listAddresses(
  page: number = 1,
  pageSize: number = 50,
  status?: string,
): Promise<AddressListResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set('status', status);
  return request<AddressListResponse>(`/addresses?${params}`);
}

export async function getAddress(id: number): Promise<Address> {
  return request<Address>(`/addresses/${id}`);
}

export async function reparseAddress(id: number): Promise<Address> {
  return request<Address>(`/addresses/${id}/parse`, { method: 'POST' });
}

export async function updateAddress(id: number, data: AddressUpdate): Promise<Address> {
  return request<Address>(`/addresses/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function getStats(): Promise<Stats> {
  return request<Stats>('/stats');
}

export async function seedAddresses(): Promise<{ message: string; count: number }> {
  return request('/addresses/seed', { method: 'POST' });
}
