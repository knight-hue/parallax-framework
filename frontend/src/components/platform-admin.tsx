'use client';

import { useCallback, useEffect, useState } from 'react';
import { Building2, FolderKanban, Loader2, Plus, RefreshCw, ScrollText, GitBranch } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import type {
  PlatformOrganization,
  PlatformPolicy,
  PlatformProject,
  PlatformRepository,
} from '@/lib/types';
import { Badge, Button, Card, CardBody, CardHeader, EmptyState } from '@/components/ui/primitives';

const defaultPolicy = {
  readers: 4,
  redundancy: 2,
  maxRounds: 3,
  minIndependentSupport: 2,
  falsifierEnabled: true,
  maxTokenBudget: 100_000,
  deadlineSeconds: 3600,
};

export function PlatformAdmin({ onSelectProject }: { onSelectProject?: (projectId: string) => void }) {
  const [organizations, setOrganizations] = useState<PlatformOrganization[]>([]);
  const [organizationId, setOrganizationId] = useState('');
  const [projects, setProjects] = useState<PlatformProject[]>([]);
  const [projectId, setProjectId] = useState('');
  const [repositories, setRepositories] = useState<PlatformRepository[]>([]);
  const [policies, setPolicies] = useState<PlatformPolicy[]>([]);
  const [organizationName, setOrganizationName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [repositoryName, setRepositoryName] = useState('');
  const [cloneUrl, setCloneUrl] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fail = useCallback((error: unknown) => {
    setMessage(error instanceof ApiError ? error.message : String(error));
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      const page = await api.platformOrganizations();
      setOrganizations(page.items);
      setMessage(null);
      return page.items;
    } catch (error) {
      fail(error);
      return [];
    }
  }, [fail]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const page = await api.platformOrganizations();
        if (!cancelled) setOrganizations(page.items);
      } catch (error) { if (!cancelled) fail(error); }
    })();
    return () => { cancelled = true; };
  }, [fail]);

  useEffect(() => {
    if (!organizationId) return;
    let cancelled = false;
    void (async () => {
      try {
        const page = await api.platformProjects(organizationId);
        if (!cancelled) { setProjects(page.items); setMessage(null); }
      } catch (error) { if (!cancelled) fail(error); }
    })();
    return () => { cancelled = true; };
  }, [organizationId, fail]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    void (async () => {
      try {
        const [repos, policyPage] = await Promise.all([
          api.platformRepositories(projectId),
          api.platformPolicies(projectId),
        ]);
        if (!cancelled) {
          setRepositories(repos.items);
          setPolicies(policyPage.items);
          setMessage(null);
        }
      } catch (error) { if (!cancelled) fail(error); }
    })();
    return () => { cancelled = true; };
  }, [projectId, fail]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setMessage(null);
    try { await action(); } catch (error) { fail(error); } finally { setBusy(false); }
  }

  return <Card className="mt-5">
    <CardHeader
      title="组织 / 项目 / 仓库 / 策略"
      hint="平台资源的权威状态在 Java 网关；这里创建的资源可直接用于下方工作台"
      right={<Button variant="ghost" onClick={() => void run(async () => { await loadOrganizations(); })}><RefreshCw size={12} />刷新</Button>}
    />
    <CardBody className="space-y-4 text-xs">
      {message ? <div className="rounded border border-[var(--color-danger)]/40 p-2 text-[var(--color-danger)]">{message}</div> : null}

      <section className="space-y-2">
        <div className="flex items-center gap-1 text-[var(--color-muted)]"><Building2 size={12} />组织</div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="space-y-1">
            <span className="block text-[var(--color-muted)]">选择组织</span>
            <select
              aria-label="选择组织"
              value={organizationId}
              onChange={(event) => {
                setOrganizationId(event.target.value);
                setProjects([]);
                setProjectId('');
                setRepositories([]);
                setPolicies([]);
              }}
              className="rounded border border-[var(--color-border)] bg-[var(--color-canvas)] p-2"
            >
              <option value="">未选择</option>
              {organizations.map((org) => <option key={org.id} value={org.id}>{org.name}（{org.role}）</option>)}
            </select>
          </label>
          <Field label="新建组织名" value={organizationName} onChange={setOrganizationName} placeholder="team" />
          <Button
            disabled={busy || organizationName.trim().length < 1}
            onClick={() => void run(async () => {
              const created = await api.createPlatformOrganization(organizationName.trim());
              setOrganizationName('');
              await loadOrganizations();
              setOrganizationId(created.id);
            })}
          ><Plus size={12} />创建组织</Button>
        </div>
      </section>

      <section className="space-y-2">
        <div className="flex items-center gap-1 text-[var(--color-muted)]"><FolderKanban size={12} />项目</div>
        {!organizationId ? <EmptyState>先选择组织</EmptyState> : <>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="新建项目名" value={projectName} onChange={setProjectName} placeholder="payments" />
            <Button
              disabled={busy || projectName.trim().length < 1}
              onClick={() => void run(async () => {
                const created = await api.createPlatformProject(organizationId, projectName.trim());
                setProjectName('');
                setProjects((previous) => [...previous, created]);
                setProjectId(created.id);
                onSelectProject?.(created.id);
              })}
            ><Plus size={12} />创建项目</Button>
          </div>
          {projects.length === 0 ? <EmptyState>该组织还没有项目</EmptyState> : <div className="grid gap-2 md:grid-cols-3">
            {projects.map((project) => <button
              key={project.id}
              type="button"
              onClick={() => {
                setProjectId(project.id);
                setRepositories([]);
                setPolicies([]);
                onSelectProject?.(project.id);
              }}
              className={`rounded border p-2 text-left hover:bg-[var(--color-surface-2)] ${project.id === projectId ? 'border-[var(--color-accent)]' : 'border-[var(--color-border)]'}`}
            >
              <div className="flex items-center justify-between"><span>{project.name}</span>{project.id === projectId ? <Badge tone="accent">当前</Badge> : null}</div>
              <div className="mono mt-1 text-[var(--color-muted)]">{project.id}</div>
            </button>)}
          </div>}
        </>}
      </section>

      <section className="space-y-2">
        <div className="flex items-center gap-1 text-[var(--color-muted)]"><GitBranch size={12} />仓库</div>
        {!projectId ? <EmptyState>先选择项目</EmptyState> : <>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="仓库名" value={repositoryName} onChange={setRepositoryName} placeholder="api" />
            <Field label="clone URL" value={cloneUrl} onChange={setCloneUrl} placeholder="https://github.com/team/api" />
            <Button
              disabled={busy || !repositoryName.trim() || !cloneUrl.trim()}
              onClick={() => void run(async () => {
                const created = await api.registerPlatformRepository(projectId, {
                  name: repositoryName.trim(), cloneUrl: cloneUrl.trim(),
                });
                setRepositoryName('');
                setCloneUrl('');
                setRepositories((previous) => [...previous, created]);
              })}
            ><Plus size={12} />登记仓库</Button>
          </div>
          {repositories.length === 0 ? <EmptyState>还没有仓库</EmptyState> : <ul className="space-y-1">
            {repositories.map((repository) => <li key={repository.id} className="flex flex-wrap items-center gap-2 rounded border border-[var(--color-border)] p-2">
              <span>{repository.name}</span>
              <span className="mono text-[var(--color-muted)]">{repository.id}</span>
              <span className="text-[var(--color-muted)]">{repository.cloneUrl}</span>
            </li>)}
          </ul>}
        </>}
      </section>

      <section className="space-y-2">
        <div className="flex items-center gap-1 text-[var(--color-muted)]"><ScrollText size={12} />策略</div>
        {!projectId ? <EmptyState>先选择项目</EmptyState> : <>
          <Button
            disabled={busy}
            onClick={() => void run(async () => {
              const created = await api.publishPlatformPolicy(projectId, defaultPolicy);
              setPolicies((previous) => [created, ...previous]);
            })}
          ><Plus size={12} />发布默认策略版本</Button>
          {policies.length === 0 ? <EmptyState>还没有策略版本</EmptyState> : <ul className="space-y-1">
            {policies.map((policy) => <li key={policy.id} className="flex flex-wrap items-center gap-2 rounded border border-[var(--color-border)] p-2">
              <Badge tone="accent">v{policy.versionNumber}</Badge>
              <span className="mono text-[var(--color-muted)]">{policy.id}</span>
              <span className="text-[var(--color-muted)]">readers {policy.config.readers} · 冗余 {policy.config.redundancy} · 预算 {policy.config.maxTokenBudget}</span>
            </li>)}
          </ul>}
        </>}
      </section>

      {busy ? <div className="flex items-center gap-1 text-[var(--color-muted)]"><Loader2 size={12} className="animate-spin" />处理中…</div> : null}
    </CardBody>
  </Card>;
}

function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return <label className="space-y-1">
    <span className="block text-[var(--color-muted)]">{label}</span>
    <input
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="w-full rounded border border-[var(--color-border)] bg-[var(--color-canvas)] p-2"
    />
  </label>;
}
