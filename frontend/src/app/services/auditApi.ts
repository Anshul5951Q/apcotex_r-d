// src/app/services/auditApi.ts

import { authFetch } from './researchApi';

export interface AuditLogEntry {
  id: string;
  user_id: string;
  entity_type: string;
  entity_id: string | null;
  action: string;
  detail: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function getAuditLogs(params: {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  entity_type?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
} = {}): Promise<AuditLogListResponse> {
  const queryParams = new URLSearchParams();
  
  if (params.page) queryParams.append('page', params.page.toString());
  if (params.page_size) queryParams.append('page_size', params.page_size.toString());
  if (params.user_id) queryParams.append('user_id', params.user_id);
  if (params.action) queryParams.append('action', params.action);
  if (params.entity_type) queryParams.append('entity_type', params.entity_type);
  if (params.date_from) queryParams.append('date_from', params.date_from);
  if (params.date_to) queryParams.append('date_to', params.date_to);
  if (params.search) queryParams.append('search', params.search);
  
  const queryString = queryParams.toString();
  const endpoint = `/audit-log${queryString ? `?${queryString}` : ''}`;
  
  const res = await authFetch(endpoint);
  
  if (res.status === 403) {
    throw new Error('Access denied: Admin only');
  }
  
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err?.error?.message || 'Failed to fetch audit logs');
  }
  
  const data = await res.json();
  return data.data;
}
