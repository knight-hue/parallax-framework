'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Download, RefreshCw, RotateCcw } from 'lucide-react';
import { api, API_BASE, ApiError } from '@/lib/api';
import type { ClaimRow, ProvenanceGraph, RunRecord, RunResult } from '@/lib/types';
import { AuditForm } from '@/components/audit-form';
import { ClaimLedger } from '@/components/claim-ledger';
import { CoverageHeatmap } from '@/components/coverage-heatmap';
import { EventStream } from '@/components/event-stream';
import { RunHistory, RunSummary } from '@/components/run-history';
import { Badge, Button, Card, CardBody, CardHeader, EmptyState } from '@/components/ui/primitives';
import { formatPercent } from '@/lib/utils';

interface Health {
  status: string;
  version: string;
  llm_configured: boolean;
  model: string;
}

export default function Page() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [streamRunId, setStreamRunId] = useState<string | null>(null);
  const [viewRunId, setViewRunId] = useState<string | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ClaimRow | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(null);
    } catch (err) {
      setHealth(null);
      setHealthError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  const refreshRuns = useCallback(async () => {
    try {
      const { runs: list } = await api.listRuns();
      setRuns(list);
    } catch {
      /* 历史列表拉不到不该阻断主流程：提交与事件流才是核心功能 */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    /* 首次加载放在 effect 里是必要的（数据来自浏览器之外的系统）。
       用局部 async 函数包起来，是为了让 setState 都发生在 await 之后，
       避免在 effect 体内同步 setState 触发级联渲染。 */
    void (async () => {
      try {
        const info = await api.health();
        if (!cancelled) {
          setHealth(info);
          setHealthError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setHealth(null);
          setHealthError(err instanceof ApiError ? err.message : String(err));
        }
      }
    })();

    void (async () => {
      try {
        const { runs: list } = await api.listRuns();
        if (!cancelled) setRuns(list);
      } catch {
        /* 历史列表拉不到不该阻断主流程：提交与事件流才是核心功能 */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /** 运行结束后拉取结构化结果。 */
  const loadResult = useCallback(async (runId: string) => {
    setResultError(null);
    try {
      const envelope = await api.getResult(runId);
      setResult(envelope.ready && envelope.result ? envelope.result : null);
      if (!envelope.ready) setResultError('结果尚未落盘，稍后可在运行历史中重新打开');
    } catch (err) {
      setResult(null);
      setResultError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  const handleFinished = useCallback(
    (runId: string) => {
      void loadResult(runId);
      void refreshRuns();
    },
    [loadResult, refreshRuns],
  );

  const handleSubmitted = useCallback(
    (runId: string) => {
      setResult(null);
      setResultError(null);
      setSelectedClaim(null);
      setStreamRunId(runId);
      setViewRunId(runId);
      void refreshRuns();
    },
    [refreshRuns],
  );

  /** 点历史记录：切到该运行的已有结果，不重连事件流。 */
  const handleSelectRun = useCallback(
    (run: RunRecord) => {
      setViewRunId(run.run_id);
      setSelectedClaim(null);
      if (run.status === 'done') {
        void loadResult(run.run_id);
        setStreamRunId(run.run_id);
      } else if (run.status === 'running') {
        setResult(null);
        setStreamRunId(run.run_id);
      } else {
        setResult(null);
        setStreamRunId(null);
      }
    },
    [loadResult],
  );

  const activeRun = useMemo(
    () => runs.find((r) => r.run_id === viewRunId) ?? null,
    [runs, viewRunId],
  );

  const offline = healthError !== null;

  return (
    <div className="mx-auto max-w-[1600px] px-5 py-5">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Parallax<span className="ml-2 text-sm font-normal text-[var(--color-muted)]">视差</span>
          </h1>
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            抗从众的多智能体证据装配框架 · 先独立，后共识
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {offline ? (
            <Badge tone="danger">
              <AlertTriangle size={10} className="mr-1" />
              后端不可达
            </Badge>
          ) : health ? (
            <>
              <Badge tone="ok">服务在线 v{health.version}</Badge>
              <Badge tone={health.llm_configured ? 'accent' : 'warn'}>
                {health.llm_configured ? health.model : '未配置模型凭据'}
              </Badge>
            </>
          ) : (
            <Badge tone="neutral">连接中…</Badge>
          )}
          <Button variant="ghost" onClick={() => void refreshHealth()} title="重新探测后端">
            <RefreshCw size={12} />
            探活
          </Button>
        </div>
      </header>

      {offline ? (
        <Card className="mb-5 border-[rgba(248,81,73,0.35)]">
          <CardBody className="text-xs leading-5 text-[var(--color-danger)]">
            无法连接 <span className="mono">{API_BASE}</span>：{healthError}
            <div className="mt-1 text-[var(--color-muted)]">
              请先启动后端：<span className="mono">python -m parallax.service.app</span>，或用{' '}
              <span className="mono">NEXT_PUBLIC_PARALLAX_API</span> 指向 Java 网关地址。
            </div>
          </CardBody>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)_360px]">
        {/* 左栏：提交与历史 */}
        <div className="flex flex-col gap-4">
          <AuditForm onSubmitted={handleSubmitted} />
          <div className="min-h-[280px] xl:flex-1">
            <RunHistory runs={runs} activeId={viewRunId} onSelect={handleSelectRun} />
          </div>
        </div>

        {/* 中栏：事件流 + 结论 */}
        <div className="flex min-w-0 flex-col gap-4">
          <Card className="flex flex-col">
            <CardHeader
              title="运行过程"
              hint="盲读分区 → 入账本 → 规则聚合 → 覆盖率补检"
              right={
                result ? (
                  <a href={api.reportUrl(result.run_id)} target="_blank" rel="noreferrer">
                    <Button variant="ghost">
                      <Download size={12} />
                      Markdown 报告
                    </Button>
                  </a>
                ) : null
              }
            />
            {/* key 让 EventStream 在切换运行记录时重挂载，从而自然清空事件列表 */}
            <EventStream
              key={streamRunId ?? 'idle'}
              runId={streamRunId}
              onFinished={handleFinished}
            />
          </Card>

          {activeRun ? <RunSummary record={activeRun} /> : null}

          {resultError ? (
            <Card>
              <CardBody className="text-xs text-[var(--color-muted)]">{resultError}</CardBody>
            </Card>
          ) : null}

          {result ? (
            <>
              <Card>
                <CardHeader
                  title="分轮次收敛过程"
                  hint={`共 ${result.manifest.rounds.length} 轮｜停止原因：${
                    result.manifest.stop_reason ?? '—'
                  }`}
                />
                <CardBody className="p-0">
                  <table className="w-full text-xs">
                    <thead className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">
                      <tr className="border-b border-[var(--color-border)]">
                        <th className="px-3 py-2 text-left font-medium">轮次</th>
                        <th className="px-3 py-2 text-right font-medium">Reader</th>
                        <th className="px-3 py-2 text-right font-medium">新增结论</th>
                        <th className="px-3 py-2 text-right font-medium">证据覆盖</th>
                        <th className="px-3 py-2 text-right font-medium">矩阵填充</th>
                        <th className="px-3 py-2 text-right font-medium">待补格</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.manifest.rounds.map((round) => (
                        <tr
                          key={round.round}
                          className="border-b border-[var(--color-border)] last:border-0"
                        >
                          <td className="px-3 py-2 tabular-nums">#{round.round}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{round.readers}</td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {round.new_fingerprints}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {formatPercent(round.evidence_fill_rate)}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {formatPercent(round.coverage_fill_rate)}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">{round.sparse_cells}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>

              <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
                <CoverageHeatmap matrix={result.coverage} />
                <Card className="flex flex-col">
                  <CardHeader
                    title="审计与开销"
                    hint="同一份代码同一份配置，可复现"
                    right={
                      <Button variant="ghost" onClick={() => void loadResult(result.run_id)}>
                        <RotateCcw size={12} />
                        重载
                      </Button>
                    }
                  />
                  <CardBody className="space-y-2 text-xs">
                    <AuditRow label="运行 ID" value={result.run_id} mono />
                    <AuditRow label="Reader 身份" value={result.manifest.reader_ids.join(', ')} mono />
                    <AuditRow label="随机种子" value={String(result.manifest.seed)} mono />
                    <AuditRow
                      label="高置信门槛"
                      value={`≥ ${result.manifest.support_threshold} 个独立来源`}
                    />
                    {Object.entries(result.usage).map(([key, value]) => (
                      <AuditRow key={key} label={`用量 · ${key}`} value={String(value)} mono />
                    ))}
                    <AuditRow
                      label="Reader 失败"
                      value={
                        result.readers_failed.length === 0
                          ? '无'
                          : `${result.readers_failed.length} 个（结果可能不完整）`
                      }
                    />
                  </CardBody>
                </Card>
              </div>

              <IndependencePanel result={result} />
            </>
          ) : activeRun?.status === 'done' || viewRunId === null ? null : (
            <Card>
              <CardBody>
                <EmptyState>
                  {activeRun?.status === 'running'
                    ? '运行中，结论将在收敛后出现在这里'
                    : '选择一条运行历史，或提交新任务'}
                </EmptyState>
              </CardBody>
            </Card>
          )}
        </div>

        {/* 右栏：账本 */}
        <div className="flex min-h-[420px] flex-col gap-4">
          {result ? (
            <ClaimLedger
              claims={result.claims}
              counts={result.counts}
              readerCount={result.manifest.reader_ids.length}
              selectedId={selectedClaim?.claim_id ?? null}
              onSelect={setSelectedClaim}
            />
          ) : (
            <Card className="flex-1">
              <CardHeader title="Claim 账本" hint="按规则而非投票聚合" />
              <CardBody>
                <EmptyState>暂无结论</EmptyState>
              </CardBody>
            </Card>
          )}

          {selectedClaim ? (
            <ClaimDetail claim={selectedClaim} provenance={result?.provenance} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function IndependencePanel({ result }: { result: RunResult }) {
  const profile = result.manifest.independence;
  return (
    <Card>
      <CardHeader
        title="独立性与证据血缘"
        hint="结构指标描述证据路径，不代表事实正确率"
      />
      <CardBody className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <Field label="有效通道 K* / N" value={`${profile.effective_channel_count.toFixed(2)} / ${profile.reader_count}`} />
        <Field label="归一化独立性" value={formatPercent(profile.normalized_independence)} />
        <Field label="证据重叠" value={formatPercent(profile.evidence_overlap_rate)} />
        <Field label="输出隔离" value={profile.isolation_status} />
        <Field label="独立支持 Claim" value={`${profile.claims_with_independent_support} / ${profile.claim_count}`} />
        <Field label="Receipt" value={String(result.manifest.receipts)} />
        <Field label="血缘节点" value={String(result.provenance.nodes.length)} />
        <Field label="血缘关系" value={String(result.provenance.edges.length)} />
      </CardBody>
    </Card>
  );
}

function AuditRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-[var(--color-border)] pb-1.5 last:border-0">
      <span className="shrink-0 text-[var(--color-muted)]">{label}</span>
      <span className={`min-w-0 break-all text-right ${mono ? 'mono' : ''}`}>{value}</span>
    </div>
  );
}

function ClaimDetail({
  claim,
  provenance,
}: {
  claim: ClaimRow;
  provenance?: ProvenanceGraph;
}) {
  const claimNodeId = `claim:${claim.claim_id}`;
  const lineageEdges = provenance?.edges.filter(
    (edge) => edge.source === claimNodeId || edge.target === claimNodeId,
  ) ?? [];
  const lineageNodeIds = new Set(
    lineageEdges.flatMap((edge) => [edge.source, edge.target]),
  );
  const lineageNodes = provenance?.nodes.filter((node) => lineageNodeIds.has(node.node_id)) ?? [];
  return (
    <Card>
      <CardHeader
        title="结论详情"
        hint="独立来源数与争议数决定它的处置方式"
        right={<Badge tone="neutral">{claim.claim_type}</Badge>}
      />
      <CardBody className="space-y-3 text-xs">
        <p className="leading-5 text-[var(--color-fg)]">{claim.statement}</p>

        {claim.rationale ? (
          <div>
            <div className="mb-1 text-[11px] text-[var(--color-muted)]">依据</div>
            <p className="leading-5 text-[var(--color-muted)]">{claim.rationale}</p>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-2">
          <Field label="定位" value={claim.locator ?? '—'} mono />
          <Field label="置信度" value={formatPercent(claim.confidence, 1)} />
          <Field label="独立来源" value={`${claim.verified_by.length} 个`} />
          <Field label="争议对手" value={`${claim.disputed_with.length} 条`} />
        </div>

        <div>
          <div className="mb-1 text-[11px] text-[var(--color-muted)]">指纹</div>
          <div className="mono break-all text-[10px] text-[var(--color-muted)]">
            {claim.fingerprint}
          </div>
        </div>

        <div>
          <div className="mb-1 text-[11px] text-[var(--color-muted)]">
            主张者（同一 Agent 重复主张不计入交叉验证）
          </div>
          <div className="flex flex-wrap gap-1">
            {claim.verified_by.length === 0 ? (
              <span className="text-[var(--color-muted)]">—</span>
            ) : (
              // 去重后展示：后端 verified_by 已按 Agent 去重，这里直接渲染
              [...new Set(claim.verified_by)].map((agent) => (
                <Badge key={agent} tone="accent" className="mono">
                  {agent}
                </Badge>
              ))
            )}
          </div>
        </div>

        {lineageEdges.length > 0 ? (
          <div>
            <div className="mb-1 text-[11px] text-[var(--color-muted)]">来源链</div>
            <div className="space-y-1 text-[10px]">
              {lineageEdges.map((edge) => (
                <div key={`${edge.source}-${edge.target}-${edge.relation}`} className="mono break-all">
                  {lineageNodes.find((node) => node.node_id === edge.source)?.label ?? edge.source}
                  <span className="mx-1 text-[var(--color-muted)]">—{edge.relation}→</span>
                  {lineageNodes.find((node) => node.node_id === edge.target)?.label ?? edge.target}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-canvas)] px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-muted)]">{label}</div>
      <div className={`mt-0.5 break-all ${mono ? 'mono' : ''}`}>{value}</div>
    </div>
  );
}
