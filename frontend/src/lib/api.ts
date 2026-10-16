import type {
  AuditSubmitted,
  RunRecord,
  RunResultEnvelope,
} from './types';

/**
 * 后端地址。
 *
 * 默认指向本机 8000（FastAPI 服务的默认端口）。生产经 Java 网关暴露时，
 * 把它设成网关地址即可，前端代码不需要改动——这也是"薄网关"这个设计的价值所在。
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_PARALLAX_API?.replace(/\/$/, '') ?? 'http://localhost:8000';

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
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
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

  reportUrl: (runId: string) => `${API_BASE}/api/v1/audits/${runId}/report`,

  eventsUrl: (runId: string) => `${API_BASE}/api/v1/audits/${runId}/events`,
};
