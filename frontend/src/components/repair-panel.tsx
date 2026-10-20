'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type { RepairProposal } from '@/lib/types';
import { Badge, Button } from '@/components/ui/primitives';

const STATUS: Record<string, string> = {
  awaiting_approval: '等待审阅', executing: '正在验证', not_reproduced: '基线未复现',
  regression_passed: '副本回归通过', regression_failed: '回归失败', failed: '执行失败',
};

export function RepairPanel({ runId, claimId }: { runId: string; claimId: string }) {
  const [proposal, setProposal] = useState<RepairProposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(false);

  async function generate() {
    setBusy(true); setError(null); setReviewed(false);
    try { setProposal(await api.proposeRepair(runId, claimId)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!proposal || !reviewed) return;
    setBusy(true); setError(null);
    try { setProposal(await api.approveRepair(runId, proposal)); }
    catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      // 请求断开时执行可能已经结束，重新读取持久化结果以免重复批准。
      try { setProposal(await api.getRepair(runId, proposal.repair_id)); } catch { /* 保留错误 */ }
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3 border-t border-[var(--color-border)] pt-3">
      <div className="font-medium">修复与回归</div>
      <p className="text-[var(--color-muted)]">先审阅补丁与测试，再批准在隔离副本验证。原始仓库保持不变。</p>
      <Button onClick={() => void generate()} disabled={busy || proposal?.status === 'executing'}>
        {busy ? '处理中…' : proposal ? '重新生成提案' : '生成修复提案'}
      </Button>
      {error ? <p role="alert" className="text-[var(--color-danger)]">{error}</p> : null}
      {proposal ? (
        <div className="space-y-2">
          <Badge tone={proposal.status === 'regression_passed' ? 'ok' : 'warn'}>
            {STATUS[proposal.status] ?? proposal.status}
          </Badge>
          <p>{proposal.plan.explanation}</p>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded border border-[var(--color-border)] p-2 text-[11px]">{proposal.patch}</pre>
          <div>回归命令：<code>{JSON.stringify(proposal.plan.regression_command)}</code></div>
          <div>基线失败标记：<code>{proposal.plan.baseline_failure_contains}</code></div>
          {proposal.status === 'awaiting_approval' ? (
            <>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} />
                我已审阅补丁、测试与执行命令
              </label>
              <Button onClick={() => void approve()} disabled={busy || !reviewed}>批准并验证副本</Button>
            </>
          ) : null}
          {proposal.reason ? <p>{proposal.reason}</p> : null}
          {[['基线复现', proposal.baseline_result], ['修复回归', proposal.regression_result]].map(([label, execution]) => {
            if (!execution || typeof execution === 'string') return null;
            return <details key={String(label)}><summary>{String(label)}：exit {execution.exit_code ?? '—'}</summary>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap">{execution.reason}{'\n'}{execution.stdout}{'\n'}{execution.stderr}</pre>
            </details>;
          })}
          <p className="text-[var(--color-muted)]">只代表所列测试在该副本上的结果。通过后可审阅并下载补丁。</p>
          <a download={`${proposal.repair_id}.diff`} href={`data:text/plain;charset=utf-8,${encodeURIComponent(proposal.patch)}`}>下载补丁</a>
        </div>
      ) : null}
    </div>
  );
}
