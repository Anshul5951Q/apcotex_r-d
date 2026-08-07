// src/app/services/researchApi.ts

const BASE_URL = 'http://localhost:8000/api/v1';
let cachedToken: string | null = null;

// Helper to auto-login as admin for development purposes
export async function getToken(): Promise<string> {
  if (cachedToken) return cachedToken;
  
  try {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'Admin@123!' })
    });
    
    if (!res.ok) throw new Error("Auto-login failed");
    
    const data = await res.json();
    cachedToken = data.data.access_token;
    return cachedToken as string;
  } catch (error) {
    console.error("Auth error:", error);
    throw error;
  }
}

async function authFetch(endpoint: string, options: RequestInit = {}) {
  const token = await getToken();
  
  const headers = {
    ...options.headers,
    'Authorization': `Bearer ${token}`
  };
  
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers
  });
  
  // Basic token expiry retry logic
  if (res.status === 401) {
    cachedToken = null;
    const newToken = await getToken();
    headers['Authorization'] = `Bearer ${newToken}`;
    return fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers
    });
  }
  
  return res;
}

export interface ResearchRunPayload {
  compound_name: string;
  competitors: string[];
  patent_sources?: string[];
  mentioned_websites?: string[];
  publication_filter?: any;
  jurisdictions?: string[];
}

export async function createResearchRun(payload: ResearchRunPayload) {
  const body = {
    compound_name: payload.compound_name,
    competitors: payload.competitors,
    selected_sources: payload.patent_sources || ["google_patents"],
    mentioned_websites: payload.mentioned_websites || [],
    publication_filter: payload.publication_filter || undefined,
    jurisdictions: payload.jurisdictions || ["US", "EP", "IN"]
  };
  
  const res = await authFetch('/research-runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err?.error?.message || 'Failed to create research run');
  }
  
  const data = await res.json();
  return data.data; // Returns ResearchRunResponse
}

export async function getResearchRuns() {
  const res = await authFetch('/research-runs?page_size=100');
  
  if (!res.ok) {
    throw new Error('Failed to fetch research runs');
  }
  
  const data = await res.json();
  return data.data; // Returns ResearchRunList
}

export async function pollResearchStatus(id: string) {
  const res = await authFetch(`/research-runs/${id}`);
  
  if (!res.ok) {
    throw new Error('Failed to poll research run status');
  }
  
  const data = await res.json();
  return data.data; // Returns ResearchRunResponse
}

export async function getReportContent(id: string) {
  const res = await authFetch(`/research-runs/${id}/report`);
  
  if (!res.ok) {
    throw new Error('Failed to fetch report content');
  }
  
  const data = await res.json();
  return data.data; // { html, markdown, extractions }
}

export function getDownloadUrl(id: string, format: 'pdf' | 'docx'): string {
  // We can just construct the URL and pass the token as a query param if supported,
  // but since we need Authorization header, it's tricky to trigger a native download.
  // Standard approach: fetch blob and object URL.
  return `${BASE_URL}/research-runs/${id}/download?format=${format}`;
}

export async function downloadFile(id: string, format: 'pdf' | 'docx', filename: string) {
  const res = await authFetch(`/research-runs/${id}/download?format=${format}`);
  if (!res.ok) throw new Error(`Failed to download ${format}`);
  
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
