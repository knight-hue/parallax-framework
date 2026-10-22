'use client';

import { useCallback, useState } from 'react';
import { CheckCircle2, Loader2, RefreshCw, Send, ShieldCheck, XCircle } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import type { PlatformRepairReview, PlatformTask } from '@/lib/types';
import { Badge, Button, Card, CardBody, CardHeader, EmptyState } from '@/components/ui/primitives';

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

const taskTone: Record<PlatformTask['state'], 'neutral' | 'accent' | 'ok' | 'warn' | 'danger'> = {
  QUEUED: 'neutral', DISPATCHED: 'accent', RUNNING: 'accent', CANCEL_REQUESTED: 'warn',
  SUCCEEDED: 'ok', FAILED: 'danger', CANCELED: 'neutral',
};

export function PlatformWorkspace({ projectId: controlledProjectId, onProjectIdChange }: { projectId?: string; onProjectIdChange?: (value: string) => void }) {
  const [manualProjectId, setManualProjectId] = useState('');
  const projectId = controlledProjectId ?? manualProjectId;
  const setProjectId = onProjectIdChange ?? setManualProjectId;
  const [repositoryId, setRepositoryId] = useState('');
  const [policyVersion, setPolicyVersion] = useState('');
  const [commitSha, setCommitSha] = useState('');
  const [budget, setBudget] = useState('1000');
  const [tasks, setTasks] = useState<PlatformTask[]>([]);
  const [selected, setSelected] = useState<PlatformTask | null>(null);
  const [review, setReview] = useState<PlatformRepairReview | null>(null);
  const [patch, setPatch] = useState('');
  const [testCommand, setTestCommand] = useState('mvn -q test');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!projectId.trim()) return;
    try {
      const page = await api.platformTasks(projectId.trim());
      setTasks(page.items);
      if (selected) setSelected(page.items.find((task) => task.id === selected.id) ?? selected);
      setMessage(null);
    } catch (error) { setMessage(error instanceof ApiError ? error.message : String(error)); }
  }, [projectId, selected]);

  async function submit() {
    setBusy(true); setMessage(null);
    try {
      const task = await api.submitPlatformTask(projectId.trim(), crypto.randomUUID(), {
        repositoryId: repositoryId.trim(), policyVersion: policyVersion.trim(), commitSha: commitSha.trim(), tokenBudget: Number(budget),
      });
      setSelected(task); await refresh();
    } catch (error) { setMessage(error instanceof ApiError ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  async function propose() {
    if (!selected || !patch) return;
    setBusy(true); setMessage(null);
    try {
      const digest = await sha256(patch);
      setReview(await api.proposePlatformRepair(projectId.trim(), selected.id, {
        sourceCommitSha: selected.commitSha, patchSha256: digest, patchContent: patch, testCommand,
      }));
    } catch (error) { setMessage(error instanceof ApiError ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!selected || !review) return;
    setBusy(true); setMessage(null);
    try { setReview(await api.approvePlatformRepair(projectId.trim(), selected.id, review.id, review.approvalDigest)); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  return <Card className="mt-5">
    <CardHeader title="Java 平台工作台" hint="任务、报告版本和修复审批均由 Java 网关持有权威状态" right={<Button variant="ghost" onClick={() => void refresh()}><RefreshCw size={12} />刷新</Button>} />
    <CardBody className="space-y-4 text-xs">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
        <Input label="项目 ID" value={projectId} onChange={setProjectId} placeholder="project UUID" />
        <Input label="仓库 ID" value={repositoryId} onChange={setRepositoryId} placeholder="repository UUID" />
        <Input label="策略版本 ID" value={policyVersion} onChange={setPolicyVersion} placeholder="policy UUID" />
        <Input label="固定 commit SHA" value={commitSha} onChange={setCommitSha} placeholder="40/64 位小写" />
        <Input label="Token 预算" value={budget} onChange={setBudget} placeholder="1000" />
      </div>
      <Button onClick={() => void submit()} disabled={busy || !projectId || !repositoryId || !policyVersion || !commitSha}><Send size={12} />提交 Java 审查</Button>
      {message ? <div className="rounded border border-[var(--color-danger)]/40 p-2 text-[var(--color-danger)]">{message}</div> : null}
      {tasks.length === 0 ? <EmptyState>输入项目 ID 后加载任务</EmptyState> : <div className="grid gap-2 md:grid-cols-2">
        {tasks.map((task) => <button key={task.id} type="button" onClick={() => { setSelected(task); setReview(null); }} className="rounded border border-[var(--color-border)] p-3 text-left hover:bg-[var(--color-surface-2)]">
          <div className="flex items-center justify-between"><span className="mono">{task.id}</span><Badge tone={taskTone[task.state]}>{task.state}</Badge></div>
          <div className="mt-2 text-[var(--color-muted)]">commit <span className="mono">{task.commitSha.slice(0, 12)}…</span> · 预算 {task.tokenBudget}</div>
        </button>)}
      </div>}
      {selected ? <div className="space-y-3 rounded border border-[var(--color-border)] p-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><span>当前任务：<span className="mono">{selected.id}</span></span><Badge tone={taskTone[selected.state]}>{selected.state}</Badge></div>
        {selected.state === 'QUEUED' || selected.state === 'RUNNING' || selected.state === 'DISPATCHED' ? <Button variant="ghost" onClick={async () => { await api.cancelPlatformTask(projectId.trim(), selected.id); await refresh(); }}><XCircle size={12} />请求取消</Button> : null}
        {selected.state === 'SUCCEEDED' ? <>
          <textarea aria-label="修复补丁" value={patch} onChange={(event) => setPatch(event.target.value)} placeholder="粘贴经过审阅的 unified diff" className="min-h-28 w-full rounded border border-[var(--color-border)] bg-[var(--color-canvas)] p-2 mono" />
          <Input label="隔离回归命令" value={testCommand} onChange={setTestCommand} placeholder="mvn -q test" />
          <Button onClick={() => void propose()} disabled={busy || !patch}><ShieldCheck size={12} />生成修复提案</Button>
          {review ? <div className="space-y-2 rounded border border-[var(--color-border)] p-3"><div className="flex items-center gap-2"><Badge tone={review.status === 'PASSED' ? 'ok' : review.status === 'FAILED' ? 'danger' : 'warn'}>{review.status}</Badge><span className="mono break-all">digest {review.approvalDigest}</span></div><div className="text-[var(--color-muted)]">提案绑定 commit、补丁摘要和回归命令；批准不会代替隔离执行。</div>{review.status === 'AWAITING_APPROVAL' ? <Button onClick={() => void approve()} disabled={busy}><CheckCircle2 size={12} />批准指定版本</Button> : null}{review.status === 'PASSED' ? <span className="inline-flex items-center gap-1 text-[var(--color-ok)]"><CheckCircle2 size={12} />回归已通过</span> : null}</div> : null}
        </> : null}
      </div> : null}
      {busy ? <div className="flex items-center gap-1 text-[var(--color-muted)]"><Loader2 size={12} className="animate-spin" />处理中…</div> : null}
    </CardBody>
  </Card>;
}

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return <label className="space-y-1"><span className="block text-[var(--color-muted)]">{label}</span><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full rounded border border-[var(--color-border)] bg-[var(--color-canvas)] p-2" /></label>;
}
