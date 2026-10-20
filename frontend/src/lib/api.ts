import type {
  AuditSubmitted,
  RunRecord,
  RunResultEnvelope,
  RepairProposal,
} from './types';

/**
 * 后端地址。
 *
 * 默认使用同源代理；生产上游由服务器端 PARALLAX_SERVER_API 指定。
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_PARALLAX_API?.replace(/\/$/, '') || '/backend';

let accessToken = '';
export function setAccessToken(token: string) { accessToken = token.trim(); }
export function accessHeaders(): Record<string, string> {
  return accessToken ? accessToken.startsWith('plx_')
    ? { 'X-API-Key': accessToken } : { Authorization: `Bearer ${accessToken}` } : {};
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...accessHeaders(), ...(init?.headers ?? {}) },
    cache: 'no-store',
  });

  if (!response.ok) {
    // 后端的错误详情放在 detail 里；拿不到就退化为状态码
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* 响应体不是 JSON，保留状态码 */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export interface SubmitAuditPayload {
  repo_path: string;
  question?: string;
  readers?: number;
  redundancy?: number;
  support_threshold?: number;
  max_rounds?: number;
  visibility?: 'blind' | 'shared';
  group_depth?: number;
  max_files?: number;
}

export const api = {
  health: () => request<{ status: string; version: string; llm_configured: boolean; model: string }>('/health'),

  meta: () => request<{ version: string; defaults: Record<string, unknown>; plugins: unknown[] }>('/api/v1/meta'),

  listRuns: (limit = 30) =>
    request<{ total: number; runs: RunRecord[] }>(`/api/v1/audits?limit=${limit}`),

  getRun: (runId: string) => request<RunRecord>(`/api/v1/audits/${runId}`),

  getResult: (runId: string) => request<RunResultEnvelope>(`/api/v1/audits/${runId}/result`),

  submit: (payload: SubmitAuditPayload) =>
    request<AuditSubmitted>('/api/v1/audits', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  proposeRepair: (runId: string, claimId: string) =>
    request<RepairProposal>(`/api/v1/audits/${runId}/repairs`, {
      method: 'POST', body: JSON.stringify({ claim_id: claimId }),
    }),

  getRepair: (runId: string, repairId: string) =>
    request<RepairProposal>(`/api/v1/audits/${runId}/repairs/${repairId}`),

  approveRepair: (runId: string, proposal: RepairProposal) =>
    request<RepairProposal>(`/api/v1/audits/${runId}/repairs/${proposal.repair_id}/approve`, {
      method: 'POST', body: JSON.stringify({ approval_digest: proposal.approval_digest }),
    }),

  reportUrl: (runId: string) => `${API_BASE}/api/v1/audits/${runId}/report`,

  downloadReport: async (runId: string) => {
    const response = await fetch(`${API_BASE}/api/v1/audits/${runId}/report`, {
      headers: accessHeaders(), cache: 'no-store',
    });
    if (!response.ok) throw new ApiError(`报告下载 HTTP ${response.status}`, response.status);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url; link.download = `${runId}.md`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  eventsUrl: (runId: string) => `${API_BASE}/api/v1/audits/${runId}/events`,
};
