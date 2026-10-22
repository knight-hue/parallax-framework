import type {
  AuditSubmitted,
  RunRecord,
  RunResultEnvelope,
  RepairProposal,
  PlatformTask,
  PlatformTaskPage,
  PlatformRepairReview,
  PlatformOrganization,
  PlatformProject,
  PlatformRepository,
  PlatformPolicy,
  PlatformCursorPage,
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

  platformTasks: (projectId: string, after = '', limit = 20) =>
    request<PlatformTaskPage>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks?after=${encodeURIComponent(after)}&limit=${limit}`),

  platformTask: (projectId: string, taskId: string) =>
    request<PlatformTask>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}`),

  submitPlatformTask: (projectId: string, idempotencyKey: string, payload: { repositoryId: string; policyVersion: string; commitSha: string; tokenBudget: number }) =>
    request<PlatformTask>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) }),

  cancelPlatformTask: (projectId: string, taskId: string) =>
    request<PlatformTask>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' }),

  proposePlatformRepair: (projectId: string, taskId: string, payload: { sourceCommitSha: string; patchSha256: string; patchContent: string; testCommand: string }) =>
    request<PlatformRepairReview>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/repairs`, { method: 'POST', body: JSON.stringify(payload) }),

  approvePlatformRepair: (projectId: string, taskId: string, reviewId: string, approvalDigest: string) =>
    request<PlatformRepairReview>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/repairs/${encodeURIComponent(reviewId)}/approve`, { method: 'POST', body: JSON.stringify({ approvalDigest }) }),

  platformOrganizations: () =>
    request<PlatformCursorPage<PlatformOrganization>>('/api/v1/platform/organizations'),

  createPlatformOrganization: (name: string) =>
    request<PlatformOrganization>('/api/v1/platform/organizations', { method: 'POST', body: JSON.stringify({ name }) }),

  platformProjects: (organizationId: string) =>
    request<PlatformCursorPage<PlatformProject>>(`/api/v1/platform/organizations/${encodeURIComponent(organizationId)}/projects`),

  createPlatformProject: (organizationId: string, name: string) =>
    request<PlatformProject>(`/api/v1/platform/organizations/${encodeURIComponent(organizationId)}/projects`, { method: 'POST', body: JSON.stringify({ name }) }),

  platformRepositories: (projectId: string) =>
    request<PlatformCursorPage<PlatformRepository>>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/repositories`),

  registerPlatformRepository: (projectId: string, payload: { name: string; cloneUrl: string }) =>
    request<PlatformRepository>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/repositories`, { method: 'POST', body: JSON.stringify(payload) }),

  platformPolicies: (projectId: string) =>
    request<PlatformCursorPage<PlatformPolicy>>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/policies`),

  publishPlatformPolicy: (projectId: string, config: PlatformPolicy['config']) =>
    request<PlatformPolicy>(`/api/v1/platform/projects/${encodeURIComponent(projectId)}/policies`, { method: 'POST', body: JSON.stringify(config) }),

};
