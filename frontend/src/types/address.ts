/**
 * TypeScript type definitions for the UrbanDash Address Parser.
 * Mirrors the backend Pydantic schemas.
 */

export type AddressStatus = 'PARSED' | 'NEEDS_REVIEW' | 'UNPARSEABLE' | 'ERROR' | 'PENDING';

export interface ParseLog {
  id: number;
  model_used: string | null;
  prompt_version: string | null;
  parsed_successfully: boolean;
  parsing_duration_ms: number | null;
  created_at: string;
}

export interface Address {
  id: number;
  raw_address: string;
  house: string | null;
  street: string | null;
  locality: string | null;
  city: string | null;
  state: string | null;
  pin: string | null;
  status: AddressStatus;
  confidence: number | null;
  warnings: string[];
  created_at: string;
  updated_at: string;
  parse_logs: ParseLog[];
}

export interface AddressListResponse {
  items: Address[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  total: number;
  parsed: number;
  needs_review: number;
  unparseable: number;
  error: number;
  pending: number;
}

export interface AddressUpdate {
  house?: string | null;
  street?: string | null;
  locality?: string | null;
  city?: string | null;
  state?: string | null;
  pin?: string | null;
  status?: AddressStatus;
  confidence?: number | null;
}
