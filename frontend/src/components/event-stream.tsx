'use client';

import { useEffect, useRef, useState } from 'react';
import { Radio, WifiOff } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { consumeEvents } from '@/lib/sse';
import type { ParallaxEvent } from '@/lib/types';
import { Badge, EmptyState, type BadgeTone } from '@/components/ui/primitives';
import { formatClock } from '@/lib/utils';

/** 事件类型 → 展示信息。颜色按"对结论的贡献"梯度给：
 *  绿色=产出结论，蓝色=结构信息，黄色=需要留意的异常，灰色=例行。 */
const EVENT_STYLE: Record<string, { label: string; tone: BadgeTone }> = {
  queued: { label: '已入队', tone: 'neutral' },
  started: { label: '开始', tone: 'accent' },
  ingest: { label: '加载证据', tone: 'accent' },
  partition: { label: '盲读分区', tone: 'purple' },
  reader: { label: 'Reader', tone: 'neutral' },
  collect: { label: '入账本', tone: 'neutral' },
  aggregate: { label: '聚合', tone: 'ok' },
  coverage: { label: '覆盖率', tone: 'purple' },
  finalize: { label: '收敛', tone: 'ok' },
  done: { label: '完成', tone: 'ok' },
  failed: { label: '失败', tone: 'danger' },
  canceled: { label: '已取消', tone: 'neutral' },
  verification: { label: '反证与复现', tone: 'purple' },
};

function renderDetail(event: ParallaxEvent): string {
  const p = event.payload as Record<string, unknown>;
  switch (event.type) {
    case 'queued':
      return `仓库 ${String(p.repo_path ?? '')}`;
    case 'ingest':
      return `${p.evidence_count} 个文件｜${p.module_count} 个模块｜${p.claim_type_count} 类缺陷`;
    case 'partition': {
      const readers = (p.readers as { reader_id: string; files: number; groups: string[] }[]) ?? [];
      const focus = (p.focus as string[]) ?? [];
      return `第 ${p.round} 轮｜${readers.length} 个 Reader｜${
        focus.length ? `定向补检 ${focus.join(', ')}` : '全域'
      }`;
    }
    case 'reader':
      return `${p.reader_id}｜${p.files} 个文件 → ${p.claims} 条 claim${
        p.ok ? '' : `｜⚠ ${String(p.error ?? '失败')}`
      }${Number(p.saw_prior_claims) > 0 ? `｜看到 ${p.saw_prior_claims} 条他人结论` : ''}`;
    case 'collect':
      return `本轮入账 ${p.admitted} 条｜账本累计 ${p.ledger_size}${
        Number(p.rejected) > 0 ? `｜拒收 ${p.rejected}` : ''
      }`;
    case 'aggregate': {
      const by = (p.by_status as Record<string, number>) ?? {};
      return `新增主体 ${p.new_fingerprints}｜高置信 ${by.high_confidence ?? 0}｜待验证 ${
        by.pending ?? 0
      }｜争议 ${by.disputed ?? 0}`;
    }
    case 'coverage':
      return `证据覆盖 ${((Number(p.evidence_fill_rate) || 0) * 100).toFixed(0)}%｜矩阵填充 ${(
        (Number(p.claim_cell_fill_rate) || 0) * 100
      ).toFixed(0)}%｜${p.should_retrieve ? `触发补检：${(p.focus_groups as string[])?.join(', ') ?? ''}` : `停止：${p.stop_reason}`}`;
    case 'finalize':
      return `高置信 ${p.high_confidence}｜待验证 ${p.pending}｜争议 ${p.disputed}｜共 ${p.rounds} 轮`;
    case 'done':
      return String(p.summary ?? '');
    case 'failed':
      return String(p.error ?? '');
    default:
      return JSON.stringify(p);
  }
}

export function EventStream({
  runId,
  onFinished,
}: {
  runId: string | null;
  onFinished: (runId: string) => void;
}) {
  /* 注意：组件自身的状态（事件列表、连接标志）不做「runId 变化时清空」，
     而是由父组件用 key={runId} 强制重挂载来完成重置——
     在 effect 里同步 setState 会触发级联渲染，React 官方明确不建议。 */
  const [events, setEvents] = useState<ParallaxEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  // 用 ref 保存回调，避免把它放进 effect 依赖导致的重复连接。
  // 赋值必须放在 effect 里：渲染期写 ref 会破坏 React 的纯渲染约定。
  const onFinishedRef = useRef(onFinished);
  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  useEffect(() => {
    if (!runId) return;

    const controller = new AbortController();
    let after = 0;
    let terminal = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function connect() {
      try {
        await consumeEvents(runId as string, after, controller.signal, (event) => {
          if (event.seq <= after) return;
          after = event.seq;
          setEvents((previous) => [...previous.slice(-1999), event]);
          if (['done', 'failed', 'canceled'].includes(event.type)) {
            terminal = true;
            controller.abort();
            onFinishedRef.current(runId as string);
          }
        }, () => { setConnected(true); setError(null); });
      } catch (err) {
        if (!controller.signal.aborted && err instanceof ApiError && err.status < 500) {
          terminal = true;
          setError(err.message);
        }
      } finally {
        setConnected(false);
        if (!terminal && !controller.signal.aborted) timer = setTimeout(() => void connect(), 1500);
      }
    }
    void connect();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [runId]);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight });
  }, [events.length]);

  return (
    <div className="flex h-full min-h-[260px] flex-col">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
        <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
          {runId ? (
            <>
              <Radio
                size={12}
                className={connected ? 'live-dot text-[var(--color-ok)]' : 'text-[var(--color-muted)]'}
              />
              <span className="mono">{runId}</span>
              <span>· {events.length} 条事件</span>
            </>
          ) : (
            <span>尚未提交任务</span>
          )}
        </div>
        {runId && !connected && events.length > 0 ? (
          <Badge tone="neutral">
            <WifiOff size={10} className="mr-1" />
            已结束
          </Badge>
        ) : null}
      </div>

      <div ref={boxRef} className="flex-1 overflow-y-auto px-4 py-2">
        {!runId ? (
          <EmptyState>提交一个审查任务后，这里会实时显示盲读与补检的全过程</EmptyState>
        ) : events.length === 0 ? (
          <EmptyState>等待服务端事件…</EmptyState>
        ) : (
          <ul className="space-y-1">
            {events.map((event) => {
              const style = EVENT_STYLE[event.type] ?? { label: event.type, tone: 'neutral' as const };
              return (
                <li key={`${event.seq}-${event.type}`} className="flex items-start gap-2 py-0.5 text-xs">
                  <span className="mono w-[62px] shrink-0 text-[var(--color-muted)]">
                    {formatClock(event.at)}
                  </span>
                  <span className="w-[86px] shrink-0">
                    <Badge tone={style.tone}>{style.label}</Badge>
                  </span>
                  <span className="min-w-0 flex-1 break-words text-[var(--color-fg)]/90">
                    {renderDetail(event)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {error ? (
        <div className="border-t border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-danger)]">
          {error}
        </div>
      ) : null}
    </div>
  );
}
